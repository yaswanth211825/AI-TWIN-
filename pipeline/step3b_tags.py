"""
Step 3b of the AI Twin data pipeline: add topic, reply type, quality and privacy tags to each exchange.

Tagging is done by an LLM reading compact batches, so it happens in two commands:

    export : exchanges.jsonl ──▶ data/tag_batches/batch_01.txt, batch_02.txt, ...
    (an LLM reads each batch and writes data/tags/batch_01.tsv, ...)
    merge  : exchanges.jsonl + data/tags/*.tsv ──▶ exchanges_tagged.jsonl + step3b_report.json

Tag file format, one line per exchange, tab-separated:
    exchange_id  topic  type  quality  private
    1            C      A     4        0

Run from the project root:
    python3 -m pipeline.step3b_tags export
    python3 -m pipeline.step3b_tags merge
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from pipeline import config

TOPICS = {
    "C": "career",      # jobs, placements, offers, interviews, salary
    "S": "studies",     # college, exams, courses, assignments
    "T": "tech",        # coding, DSA, projects, tools
    "P": "plans",       # meeting up, travel, timings, logistics
    "B": "banter",      # jokes, teasing, fun with no other subject
    "R": "personal",    # feelings, relationship, opinions about life
    "F": "family",
    "D": "daily",       # food, sleep, health, routine, what you are doing now
    "O": "other",
}
TYPES = {
    "A": "answer",      # gives information or a direct answer
    "Q": "question",    # mainly asks something back
    "J": "teasing",     # joke, sarcasm, teasing
    "S": "support",     # care, encouragement, reassurance
    "L": "plan",        # proposes or confirms a plan
    "R": "reaction",    # short acknowledgement or reaction
    "M": "smalltalk",   # greeting, check-in, sign-off
}
# quality: 1 = says nothing about your style ... 5 = very typical of how you write
# private: 1 = reply reveals something sensitive (money details, health, third-party secrets)

BATCH_SIZE = 300
CONTEXT_TURNS_SHOWN = 1   # the friend turn right before the reply is enough to judge topic and type
CONTEXT_CHARS = 140
REPLY_CHARS = 220


def clip(text: str, limit: int) -> str:
    text = text.replace("\n", " / ")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def load_exchanges(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def export(exchanges: list[dict], out_dir: Path) -> int:
    """Writes compact batches: the last context turn(s) and the reply, newlines shown as ' / '."""
    out_dir.mkdir(parents=True, exist_ok=True)
    batches = 0
    for start in range(0, len(exchanges), BATCH_SIZE):
        batches += 1
        lines = []
        for e in exchanges[start:start + BATCH_SIZE]:
            context = " | ".join(
                f"{'F' if t['sender'] == 'friend' else 'M'}: {clip(t['text'], CONTEXT_CHARS)}" for t in e["context"][-CONTEXT_TURNS_SHOWN:]
            )
            lines.append(f"#{e['exchange_id']} {context} >> {clip(e['reply'], REPLY_CHARS)}")
        (out_dir / f"batch_{batches:02d}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return batches


def read_tags(tag_dir: Path) -> tuple[dict[int, dict], list[str]]:
    tags: dict[int, dict] = {}
    errors: list[str] = []
    for file in sorted(tag_dir.glob("*.tsv")):
        for n, line in enumerate(file.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            parts = line.split("\t")
            where = f"{file.name}:{n}"
            if len(parts) != 5:
                errors.append(f"{where} expected 5 fields")
                continue
            ex_id, topic, kind, quality, private = (p.strip() for p in parts)
            if topic not in TOPICS or kind not in TYPES or quality not in "12345" or private not in ("0", "1"):
                errors.append(f"{where} invalid value")
                continue
            if int(ex_id) in tags:
                errors.append(f"{where} duplicate id {ex_id}")
            tags[int(ex_id)] = {
                "topic": TOPICS[topic], "type": TYPES[kind], "quality": int(quality), "private": private == "1",
            }
    return tags, errors


def merge(exchanges: list[dict], tag_dir: Path, out_dir: Path) -> dict:
    tags, errors = read_tags(tag_dir)
    ids = {e["exchange_id"] for e in exchanges}
    missing = sorted(ids - tags.keys())
    unknown = sorted(tags.keys() - ids)

    tagged = []
    for e in exchanges:
        if e["exchange_id"] in tags:
            tagged.append({**e, **tags[e["exchange_id"]]})

    report = {
        "exchanges": len(exchanges),
        "tagged": len(tagged),
        "missing_ids": missing[:50],
        "missing_count": len(missing),
        "unknown_ids": unknown[:50],
        "format_errors": errors[:50],
        "topic": dict(Counter(t["topic"] for t in tagged).most_common()),
        "type": dict(Counter(t["type"] for t in tagged).most_common()),
        "quality": dict(sorted(Counter(t["quality"] for t in tagged).items())),
        "private": sum(t["private"] for t in tagged),
        "quality_3_plus_not_private": sum(t["quality"] >= 3 and not t["private"] for t in tagged),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "exchanges_tagged.jsonl").open("w", encoding="utf-8") as f:
        for row in tagged:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out_dir / "step3b_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 3b: export batches for tagging, then merge the tags.")
    parser.add_argument("command", choices=["export", "merge"])
    parser.add_argument("--input", type=Path, default=config.DATA_DIR / "exchanges.jsonl")
    args = parser.parse_args()

    exchanges = load_exchanges(args.input)
    if args.command == "export":
        n = export(exchanges, config.DATA_DIR / "tag_batches")
        print(f"Wrote {n} batches of up to {BATCH_SIZE} to {config.DATA_DIR / 'tag_batches'}")
    else:
        report = merge(exchanges, config.DATA_DIR / "tags", config.DATA_DIR)
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
