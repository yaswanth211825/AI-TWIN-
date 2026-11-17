"""
Step 5 of the AI Twin data pipeline: score baselines on the held-out test set.

Every system answers the same 222 test messages; its replies are scored against your real replies
with pipeline.metrics. Later steps (fine-tuned model, fine-tuned + RAG) are scored the same way.

Systems
    random_reply    a random past reply of yours                      (lower bound, no API)
    nearest_reply   your past reply to the most similar message (BM25)  (retrieval only, no API)
    prompt_only     LLM with the persona prompt                       (needs replies, see below)
    prompt_rag      LLM with persona + top-k past replies as examples (needs replies, see below)

LLM replies come from data/eval/replies_<system>.jsonl  ({"exchange_id": .., "reply": ..} per line).
Make them with either:
    python3 -m pipeline.step5_baseline --export-prompts     # writes data/eval/prompts_<system>.jsonl
    python3 -m pipeline.step5_baseline --openai MODEL       # calls OpenAI (needs OPENAI_API_KEY, costs money)

Run from the project root:
    python3 -m pipeline.step5_baseline
"""

from __future__ import annotations

import argparse
import json
import os
import random
import urllib.request
from pathlib import Path

from pipeline import config
from pipeline.metrics import StyleProfile, summarize
from pipeline.retrieval import BM25

EVAL_DIR = config.DATA_DIR / "eval"
LLM_SYSTEMS = ("prompt_only", "prompt_rag")
ROLE = {"friend": "user", "me": "assistant"}

STYLE_EXAMPLES = """{message}

(Style reference, not part of the chat. How Yaswanth replied to similar messages before:
{examples}
Use these only for tone and wording. Reply to the message above.)"""


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def last_friend_turn(exchange: dict) -> str:
    return [t["text"] for t in exchange["context"] if t["sender"] == "friend"][-1]


# ---------------------------------------------------------------------------
# Offline systems
# ---------------------------------------------------------------------------

def random_reply(test: list[dict], rag: list[dict], seed: int = 7) -> list[str]:
    rng = random.Random(seed)
    return [rng.choice(rag)["reply"] for _ in test]


def nearest_reply(test: list[dict], rag: list[dict], index: BM25) -> list[str]:
    replies = []
    for e in test:
        hits = index.search(last_friend_turn(e), k=1)
        replies.append(rag[hits[0][0]]["reply"] if hits else "haa")
    return replies


# ---------------------------------------------------------------------------
# LLM prompts (the same shape the Java app sends)
# ---------------------------------------------------------------------------

def build_messages(exchange: dict, examples: list[dict] | None) -> list[dict]:
    messages = [{"role": "system", "content": config.FINETUNE_SYSTEM_PROMPT + config.PERSONA_RULES}]
    for turn in exchange["context"]:
        role = ROLE[turn["sender"]]
        if messages[-1]["role"] == role:
            messages[-1]["content"] += "\n" + turn["text"]
        else:
            messages.append({"role": role, "content": turn["text"]})
    if examples:
        shown = "\n".join(f"- They said: {ex['embed_text']}\n  Yaswanth replied: {ex['reply']}" for ex in examples)
        messages[-1]["content"] = STYLE_EXAMPLES.format(message=messages[-1]["content"], examples=shown)
    return messages


def prompts_for(system: str, test: list[dict], rag: list[dict], index: BM25) -> list[dict]:
    rows = []
    for e in test:
        examples = None
        if system == "prompt_rag":
            examples = [rag[i] for i, _ in index.search(last_friend_turn(e), k=config.RAG_TOP_K)]
        rows.append({"exchange_id": e["exchange_id"], "messages": build_messages(e, examples)})
    return rows


def openai_reply(messages: list[dict], model: str, api_key: str) -> str:
    body = json.dumps({"model": model, "messages": messages, "max_completion_tokens": 400}).encode()
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)["choices"][0]["message"]["content"].strip()


def generate_with_openai(system: str, prompts: list[dict], model: str) -> Path:
    """Writes replies one per line; re-running skips ids already done, so it can resume."""
    api_key = os.environ["OPENAI_API_KEY"]
    out = EVAL_DIR / f"replies_{system}.jsonl"
    done = {r["exchange_id"] for r in load(out)} if out.exists() else set()
    with out.open("a", encoding="utf-8") as f:
        for p in prompts:
            if p["exchange_id"] in done:
                continue
            reply = openai_reply(p["messages"], model, api_key)
            f.write(json.dumps({"exchange_id": p["exchange_id"], "reply": reply, "model": model}, ensure_ascii=False) + "\n")
            f.flush()
    return out


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def replies_from_file(system: str, test: list[dict]) -> list[str] | None:
    path = EVAL_DIR / f"replies_{system}.jsonl"
    if not path.exists():
        return None
    by_id = {r["exchange_id"]: r["reply"] for r in load(path)}
    if any(e["exchange_id"] not in by_id for e in test):
        return None  # incomplete run: do not score a partial set
    return [by_id[e["exchange_id"]] for e in test]


def run(export_prompts: bool = False, openai_model: str | None = None) -> dict:
    rag = load(config.DATA_DIR / "rag.jsonl")
    test = load(config.DATA_DIR / "test.jsonl")
    refs = [e["reply"] for e in test]
    profile = StyleProfile([r["reply"] for r in rag])
    index = BM25([r["embed_text"] for r in rag])
    EVAL_DIR.mkdir(parents=True, exist_ok=True)

    if export_prompts or openai_model:
        for system in LLM_SYSTEMS:
            prompts = prompts_for(system, test, rag, index)
            path = EVAL_DIR / f"prompts_{system}.jsonl"
            path.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in prompts), encoding="utf-8")
            if openai_model:
                generate_with_openai(system, prompts, openai_model)

    systems = {
        "your real replies (target)": refs,
        "random_reply": random_reply(test, rag),
        "nearest_reply": nearest_reply(test, rag, index),
    }
    pending = []
    for system in LLM_SYSTEMS:
        replies = replies_from_file(system, test)
        if replies:
            systems[system] = replies
        else:
            pending.append(system)

    results = {name: summarize(preds, refs, profile) for name, preds in systems.items()}
    report = {"test_exchanges": len(test), "results": results, "not_scored_yet": pending}
    (EVAL_DIR / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def print_table(report: dict) -> None:
    rows = report["results"]
    cols = list(next(iter(rows.values())).keys())
    width = {c: max(len(c), 6) + 2 for c in cols}
    print(f"{'system':28}" + "".join(f"{c:>{width[c]}}" for c in cols))
    for name, r in rows.items():
        print(f"{name:28}" + "".join(f"{r[c]:>{width[c]}}" for c in cols))
    if report["not_scored_yet"]:
        print("\nNot scored yet (no complete replies file):", ", ".join(report["not_scored_yet"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 5: score baselines on the held-out test set.")
    parser.add_argument("--export-prompts", action="store_true", help="write LLM prompts to data/eval/")
    parser.add_argument("--openai", metavar="MODEL", help="generate LLM replies with OpenAI (uses OPENAI_API_KEY)")
    args = parser.parse_args()
    print_table(run(args.export_prompts, args.openai))


if __name__ == "__main__":
    main()
