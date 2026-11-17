"""
Steps 5 and 6 of the AI Twin pipeline: score systems on the held-out test set and compare generation models.

Every system answers the same test messages; replies are scored against your real replies with
pipeline.metrics.

Systems
    random_reply          a random past reply of yours                        (lower bound, no API)
    nearest_reply         your past reply to the most similar message (BM25)   (retrieval only, no API)
    prompt_only@MODEL     LLM with the persona prompt
    prompt_rag@MODEL      LLM with persona + top-k past replies as style examples

LLM replies live in data/eval/replies_<system>@<model>.jsonl and are made with:
    python3 -m pipeline.step5_baseline --estimate gpt-6-luna,gpt-4o           # cost only, no calls
    python3 -m pipeline.step5_baseline --openai gpt-6-luna,gpt-4o --sample 40 # calls OpenAI (OPENAI_API_KEY)

--sample N scores every system on the same N test messages (a fixed, time-spread sample),
so models are compared on identical inputs. Without it, the whole test set is used.

Run from the project root:
    python3 -m pipeline.step5_baseline
"""

from __future__ import annotations

import argparse
import hashlib
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
EXPECTED_OUTPUT_TOKENS = 60  # your median reply is ~60 characters; generous for estimates

STYLE_EXAMPLES = """{message}

(Style reference, not part of the chat. How Yaswanth replied to similar messages before:
{examples}
Use these only for tone and wording. Reply to the message above.)"""


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def last_friend_turn(exchange: dict) -> str:
    return [t["text"] for t in exchange["context"] if t["sender"] == "friend"][-1]


def sample(test: list[dict], n: int | None) -> list[dict]:
    """Same n exchanges every run, spread over time (ordered by a hash of the id, then by time)."""
    if not n or n >= len(test):
        return test
    picked = sorted(test, key=lambda e: hashlib.sha1(e["exchange_id"].encode()).hexdigest())[:n]
    return sorted(picked, key=lambda e: e["ts"])


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
    messages = [{"role": "system", "content": config.SYSTEM_PROMPT + config.PERSONA_RULES}]
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


def estimate_cost(prompts: list[dict], model: str) -> float:
    """Dollars, using ~4 characters per token. An estimate, not a bill."""
    price_in, price_out = config.MODEL_PRICES[model]
    tokens_in = sum(len(m["content"]) for p in prompts for m in p["messages"]) / 4
    tokens_out = EXPECTED_OUTPUT_TOKENS * len(prompts)
    return (tokens_in * price_in + tokens_out * price_out) / 1_000_000


def openai_reply(messages: list[dict], model: str, api_key: str) -> str:
    body = {"model": model, "messages": messages, "max_completion_tokens": 400}
    if model in config.REASONING_EFFORT:
        body["reasoning_effort"] = config.REASONING_EFFORT[model]
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions", data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)["choices"][0]["message"]["content"].strip()


def replies_path(system: str, model: str) -> Path:
    return EVAL_DIR / f"replies_{system}@{model}.jsonl"


def generate_with_openai(system: str, prompts: list[dict], model: str) -> None:
    """Appends replies one per line; re-running skips ids already done, so it can resume."""
    api_key = os.environ["OPENAI_API_KEY"]
    out = replies_path(system, model)
    done = {r["exchange_id"] for r in load(out)} if out.exists() else set()
    with out.open("a", encoding="utf-8") as f:
        for p in prompts:
            if p["exchange_id"] in done:
                continue
            reply = openai_reply(p["messages"], model, api_key)
            f.write(json.dumps({"exchange_id": p["exchange_id"], "reply": reply}, ensure_ascii=False) + "\n")
            f.flush()


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def llm_replies(test: list[dict]) -> dict[str, list[str]]:
    """Every replies_<system>@<model>.jsonl that covers all of `test`."""
    found = {}
    for path in sorted(EVAL_DIR.glob("replies_*@*.jsonl")):
        name = path.stem.removeprefix("replies_")
        by_id = {r["exchange_id"]: r["reply"] for r in load(path)}
        if all(e["exchange_id"] in by_id for e in test):
            found[name] = [by_id[e["exchange_id"]] for e in test]
    return found


def run(sample_size: int | None = None, export_prompts: bool = False,
        models: list[str] | None = None, estimate_only: bool = False) -> dict:
    rag = load(config.DATA_DIR / "rag.jsonl")
    test = sample(load(config.DATA_DIR / "test.jsonl"), sample_size)
    refs = [e["reply"] for e in test]
    profile = StyleProfile([r["reply"] for r in rag])
    index = BM25([r["embed_text"] for r in rag])
    EVAL_DIR.mkdir(parents=True, exist_ok=True)

    prompts = {s: prompts_for(s, test, rag, index) for s in LLM_SYSTEMS}
    if export_prompts:
        for system, rows in prompts.items():
            (EVAL_DIR / f"prompts_{system}.jsonl").write_text(
                "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in rows), encoding="utf-8")

    estimates = {m: round(sum(estimate_cost(prompts[s], m) for s in LLM_SYSTEMS), 4) for m in (models or [])}
    if models and not estimate_only:
        for model in models:
            for system in LLM_SYSTEMS:
                generate_with_openai(system, prompts[system], model)

    systems = {
        "your real replies (target)": refs,
        "random_reply": random_reply(test, rag),
        "nearest_reply": nearest_reply(test, rag, index),
        **llm_replies(test),
    }
    results = {name: summarize(preds, refs, profile) for name, preds in systems.items()}
    report = {"test_exchanges": len(test), "estimated_cost_usd": estimates, "results": results}
    suffix = f"_sample{len(test)}" if sample_size else ""
    (EVAL_DIR / f"results{suffix}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def print_table(report: dict) -> None:
    rows = report["results"]
    cols = list(next(iter(rows.values())).keys())
    width = {c: max(len(c), 6) + 2 for c in cols}
    print(f"{report['test_exchanges']} test messages")
    print(f"{'system':32}" + "".join(f"{c:>{width[c]}}" for c in cols))
    for name, r in rows.items():
        print(f"{name:32}" + "".join(f"{r[c]:>{width[c]}}" for c in cols))
    for model, dollars in report["estimated_cost_usd"].items():
        print(f"\nEstimated cost for {model} (both LLM systems): ${dollars}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Steps 5-6: score systems and compare generation models.")
    parser.add_argument("--sample", type=int, help="score on this many test messages (same ones every run)")
    parser.add_argument("--export-prompts", action="store_true", help="write LLM prompts to data/eval/")
    parser.add_argument("--estimate", metavar="MODELS", help="comma-separated models: print cost, call nothing")
    parser.add_argument("--openai", metavar="MODELS", help="comma-separated models: generate replies (costs money)")
    args = parser.parse_args()
    models = (args.openai or args.estimate or "").split(",") if (args.openai or args.estimate) else None
    print_table(run(args.sample, args.export_prompts, models, estimate_only=bool(args.estimate)))


if __name__ == "__main__":
    main()
