"""Step 9: is the real app better than the simpler systems, or is it chance?

Reads every reply file in data/eval/ that covers all test messages, then:

1. chrF per message for each system (beta=2 as in step 5, and beta=1, which does not reward longer replies).
2. Paired bootstrap 95% intervals: app minus each baseline, on the SAME messages. If an interval
   contains 0, the gap could be chance at this sample size.
3. A blind-test sheet for friends: N past conversations, the real reply and the app's reply as A/B in a
   random order, and a separate answer key. Both stay in the git-ignored data/blind_test/.

    python3 -m pipeline.step9_compare            # writes data/eval/step9_compare.json
    python3 -m pipeline.step9_compare --blind 20 # also writes the blind-test sheet
"""

from __future__ import annotations

import argparse
import json
import random

from pipeline import config
from pipeline.metrics import chrf, paired_bootstrap
from pipeline.retrieval import BM25
from pipeline.step5_baseline import EVAL_DIR, llm_replies, load, nearest_reply, random_reply, sample

APP = "app@" + config.GENERATION_MODEL
BLIND_DIR = config.DATA_DIR / "blind_test"
NAMES = {"friend": "Indu", "me": "Yaswanth"}


def per_item(preds: list[str], refs: list[str], beta: float) -> list[float]:
    return [chrf(p, r, beta=beta) for p, r in zip(preds, refs)]


def compare(systems: dict[str, list[str]], refs: list[str]) -> dict:
    """Mean chrF per system and app-minus-baseline intervals."""
    out = {"chrF_mean": {}, "app_minus_baseline": {}}
    for beta in (2.0, 1.0):
        key = f"beta{int(beta)}"
        scores = {name: per_item(preds, refs, beta) for name, preds in systems.items()}
        out["chrF_mean"][key] = {n: round(sum(s) / len(s), 2) for n, s in scores.items()}
        if APP in scores:
            out["app_minus_baseline"][key] = {
                n: [round(x, 2) for x in paired_bootstrap(scores[APP], s)]
                for n, s in scores.items() if n != APP}
    return out


def blind_sheet(test: list[dict], app: dict[str, str], n: int, seed: int = 9) -> tuple[str, list[dict]]:
    """Markdown sheet (A/B shuffled) and the answer key. Skips private or very short exchanges."""
    pool = [e for e in test if not e.get("private") and e["exchange_id"] in app and len(e["reply"]) >= 8]
    picked = sample(pool, n)
    rng = random.Random(seed)
    lines = ["# Which reply did Yaswanth really write?", "",
             "For each chat, read the last messages and pick A or B: the one you think Yaswanth sent.", ""]
    key = []
    for i, e in enumerate(picked, 1):
        real_first = rng.random() < 0.5
        a, b = (e["reply"], app[e["exchange_id"]]) if real_first else (app[e["exchange_id"]], e["reply"])
        lines.append(f"## {i}")
        lines += [f"> **{NAMES[t['sender']]}:** " + t["text"].replace("\n", " / ") for t in e["context"]]
        lines += ["", "**A:** " + a.replace("\n", " / "), "", "**B:** " + b.replace("\n", " / "), "",
                  "Your pick: ___", ""]
        key.append({"item": i, "exchange_id": e["exchange_id"], "real": "A" if real_first else "B"})
    return "\n".join(lines), key


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 9: compare the app with the baselines.")
    parser.add_argument("--blind", type=int, default=0, help="also write a blind-test sheet with this many items")
    args = parser.parse_args()

    rag = load(config.DATA_DIR / "rag.jsonl")
    test = load(config.DATA_DIR / "test.jsonl")
    refs = [e["reply"] for e in test]
    index = BM25([r["embed_text"] for r in rag])
    found = llm_replies(test)
    if APP not in found:
        raise SystemExit(f"replies_{APP}.jsonl does not cover all {len(test)} test messages yet")
    systems = {"random_reply": random_reply(test, rag), "nearest_reply": nearest_reply(test, rag, index), **found}

    report = {"test_exchanges": len(test), **compare(systems, refs)}
    (EVAL_DIR / "step9_compare.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))

    if args.blind:
        sheet, key = blind_sheet(test, dict(zip((e["exchange_id"] for e in test), found[APP])), args.blind)
        BLIND_DIR.mkdir(parents=True, exist_ok=True)
        (BLIND_DIR / "sheet.md").write_text(sheet, encoding="utf-8")
        (BLIND_DIR / "answer_key.json").write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"\nBlind test: {len(key)} items in {BLIND_DIR}/sheet.md (answer key kept separately)")


if __name__ == "__main__":
    main()
