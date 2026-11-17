"""
Step 3 of the AI Twin data pipeline: build exchanges, the training and retrieval unit.

    turns.jsonl ──find your replies──▶ candidates ──filter──▶ exchanges.jsonl

An exchange is one reply of yours plus the turns just before it in the same session:

    context: friend "bro free aa?"  ->  me "ha cheppu"  ->  friend "TCS results vachaya?"
    reply  : me "ha vachayi\ndigital lo select ayya"

Rules
- A reply is a turn by "me" whose previous turn, in the same session, is by "friend".
- Context is up to CONTEXT_TURNS earlier turns from the same session (never across a session break).
- Filters: replies containing redaction placeholders, replies longer than MAX_REPLY_CHARS,
  and more than MAX_SAME_REPLY copies of the same reply text.
- Short filler replies ("ok", "hmm", emoji only) are kept but marked low_value, because they are
  part of how you talk; later steps can down-weight them.

Input : data/turns.jsonl         (from step 2)
Output: data/exchanges.jsonl     one exchange per line
        data/step3_report.json   counts only

Run from the project root:
    python3 -m pipeline.step3_exchanges
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from pipeline import config

PLACEHOLDER = re.compile(r"\[(?:PHONE|EMAIL|UPI|OTP|NUMBER|LINK)\]")
FILLER = re.compile(
    r"^(?:ok+|okay|k+|hm+|ha+|ah+|oh+|lol|(?:ha){2,}|ya+|yes|no|nope|s+|mm+|acha|achha|sare|sari"
    r"|ledu|avunu|nice|done|thanks|thx|ty|good|gn|gm)[.!?]*$"
)
NO_LETTERS = re.compile(r"^[\W\d_]+$")


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def is_low_value(text: str) -> bool:
    n = normalise(text)
    return bool(NO_LETTERS.match(n) or FILLER.match(n) or len(n) <= 3)


def stable_rank(turn_id: int) -> str:
    """Deterministic pseudo-random order, so re-running gives the same result."""
    return hashlib.sha1(str(turn_id).encode()).hexdigest()


def find_candidates(turns: list[dict], context_turns: int) -> list[dict]:
    candidates = []
    for i, turn in enumerate(turns):
        if i == 0 or turn["sender"] != "me":
            continue
        previous = turns[i - 1]
        if previous["sender"] != "friend" or previous["session_id"] != turn["session_id"]:
            continue

        context = []
        j = i - 1
        while j >= 0 and len(context) < context_turns and turns[j]["session_id"] == turn["session_id"]:
            context.insert(0, {"sender": turns[j]["sender"], "text": turns[j]["text"]})
            j -= 1

        latency = datetime.fromisoformat(turn["start"]) - datetime.fromisoformat(previous["end"])
        candidates.append({
            "turn_id": turn["turn_id"],
            "session_id": turn["session_id"],
            "ts": turn["start"],
            "context": context,
            "reply": turn["text"],
            "reply_n_messages": turn["n_messages"],
            "latency_seconds": int(latency.total_seconds()),
            "low_value": is_low_value(turn["text"]),
        })
    return candidates


def apply_filters(candidates: list[dict], max_same: int, max_chars: int) -> tuple[list[dict], Counter[str]]:
    dropped: Counter[str] = Counter()
    survivors = []
    for c in candidates:
        if PLACEHOLDER.search(c["reply"]):
            dropped["reply_has_placeholder"] += 1
        elif len(c["reply"]) > max_chars:
            dropped["reply_too_long"] += 1
        else:
            survivors.append(c)

    # Cap identical replies. Which copies stay is chosen by a stable hash, so they spread over time.
    by_reply: dict[str, list[dict]] = defaultdict(list)
    for c in survivors:
        by_reply[normalise(c["reply"])].append(c)
    keep_ids = set()
    for copies in by_reply.values():
        for c in sorted(copies, key=lambda c: stable_rank(c["turn_id"]))[:max_same]:
            keep_ids.add(c["turn_id"])
    dropped["repeated_reply"] = len(survivors) - len(keep_ids)

    kept = [c for c in survivors if c["turn_id"] in keep_ids]  # keeps time order
    return kept, dropped


def run(input_path: Path, out_dir: Path) -> dict:
    turns = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    candidates = find_candidates(turns, config.CONTEXT_TURNS)
    exchanges, dropped = apply_filters(candidates, config.MAX_SAME_REPLY, config.MAX_REPLY_CHARS)

    for n, e in enumerate(exchanges, start=1):
        e["exchange_id"] = n

    reply_chars = [len(e["reply"]) for e in exchanges]
    report = {
        "context_turns": config.CONTEXT_TURNS,
        "max_same_reply": config.MAX_SAME_REPLY,
        "max_reply_chars": config.MAX_REPLY_CHARS,
        "turns_in": len(turns),
        "candidates": len(candidates),
        "dropped": {k: v for k, v in dropped.most_common() if v},
        "exchanges": len(exchanges),
        "low_value": sum(e["low_value"] for e in exchanges),
        "sessions_covered": len({e["session_id"] for e in exchanges}),
        "context_size": dict(sorted(Counter(len(e["context"]) for e in exchanges).items())),
        "reply_chars": {
            "median": statistics.median(reply_chars) if reply_chars else 0,
            "max": max(reply_chars, default=0),
        },
        "multi_message_replies": sum(e["reply_n_messages"] > 1 for e in exchanges),
        "first": exchanges[0]["ts"] if exchanges else None,
        "last": exchanges[-1]["ts"] if exchanges else None,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    fields = ["exchange_id", "session_id", "ts", "context", "reply", "reply_n_messages", "latency_seconds", "low_value"]
    with (out_dir / "exchanges.jsonl").open("w", encoding="utf-8") as f:
        for e in exchanges:
            f.write(json.dumps({k: e[k] for k in fields}, ensure_ascii=False) + "\n")
    (out_dir / "step3_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 3: build exchanges (context -> your reply).")
    parser.add_argument("--input", type=Path, default=config.DATA_DIR / "turns.jsonl")
    parser.add_argument("--out", type=Path, default=config.DATA_DIR)
    args = parser.parse_args()

    report = run(args.input, args.out)
    print(json.dumps(report, indent=2))
    print(f"\nWrote {report['exchanges']} exchanges to {args.out / 'exchanges.jsonl'}")


if __name__ == "__main__":
    main()
