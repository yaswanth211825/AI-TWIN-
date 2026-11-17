"""
Step 4 of the AI Twin data pipeline: filter the tagged exchanges, split them by time, and write the datasets.

    exchanges_tagged.jsonl ──filter (quality, private)──▶ usable
                           ──split by time at session boundaries──▶ train │ val │ test
                           ──write──▶ finetune_train.jsonl, finetune_val.jsonl   (OpenAI chat format)
                                      rag.jsonl                                  (train + val, for pgvector)
                                      test.jsonl                                 (held out, only for scoring)

Why split by time and by whole sessions?
Exchanges next to each other in a chat share context. If one landed in training and its neighbour in
the test set, the test would be too easy (data leakage). Training on the past and testing on the newest
sessions matches real use: the twin always answers messages it has never seen.

Run from the project root:
    python3 -m pipeline.step4_split
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from pipeline import config

ROLE = {"friend": "user", "me": "assistant"}


def usable(exchanges: list[dict], min_quality: int) -> tuple[list[dict], Counter[str]]:
    dropped: Counter[str] = Counter()
    kept = []
    for e in exchanges:
        if e["private"]:
            dropped["private"] += 1
        elif e["quality"] < min_quality:
            dropped["low_quality"] += 1
        else:
            kept.append(e)
    return kept, dropped


def split_by_session(exchanges: list[dict], fractions: tuple[float, float, float]) -> tuple[list, list, list]:
    """Whole sessions go to one split, oldest first. A session is placed by where its first exchange falls."""
    ordered = sorted(exchanges, key=lambda e: e["ts"])
    sessions: dict[int, list[dict]] = {}
    for e in ordered:
        sessions.setdefault(e["session_id"], []).append(e)

    total = len(ordered)
    train_end = fractions[0] * total
    val_end = (fractions[0] + fractions[1]) * total
    train, val, test = [], [], []
    seen = 0
    for group in sessions.values():  # dicts keep insertion order = time order of first exchange
        target = train if seen < train_end else val if seen < val_end else test
        target.extend(group)
        seen += len(group)
    return train, val, test


def to_chat(exchange: dict, system_prompt: str) -> dict:
    """OpenAI fine-tuning record. Earlier replies of yours get weight 0, so only the final reply is learned."""
    messages = [{"role": "system", "content": system_prompt}]
    for turn in exchange["context"]:
        role = ROLE[turn["sender"]]
        if messages[-1]["role"] == role:  # double text: merge into one message of the same role
            messages[-1]["content"] += "\n" + turn["text"]
        else:
            messages.append({"role": role, "content": turn["text"]})
            if role == "assistant":
                messages[-1]["weight"] = 0
    if messages[-1]["role"] == "assistant":  # cannot happen (last context turn is the friend's), kept as a guard
        raise ValueError(f"exchange {exchange['exchange_id']}: context ends with your own turn")
    messages.append({"role": "assistant", "content": exchange["reply"]})
    return {"messages": messages}


def to_rag(exchange: dict) -> dict:
    """pgvector record: only the friend's side is embedded; your reply is stored as the style example."""
    friend_turns = [t["text"] for t in exchange["context"] if t["sender"] == "friend"]
    return {
        "id": exchange["exchange_id"],
        "embed_text": friend_turns[-1],
        "context": exchange["context"],
        "reply": exchange["reply"],
        "topic": exchange["topic"],
        "type": exchange["type"],
        "date": exchange["ts"][:10],
        "session_id": exchange["session_id"],
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def approx_tokens(records: list[dict]) -> int:
    """Rough count: about 4 characters per token for romanized chat text."""
    return sum(len(m["content"]) for r in records for m in r["messages"]) // 4


def describe(rows: list[dict]) -> dict:
    return {
        "exchanges": len(rows),
        "sessions": len({r["session_id"] for r in rows}),
        "first": rows[0]["ts"][:10] if rows else None,
        "last": rows[-1]["ts"][:10] if rows else None,
        "topics": dict(Counter(r["topic"] for r in rows).most_common(4)),
    }


def run(input_path: Path, out_dir: Path) -> dict:
    exchanges = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    kept, dropped = usable(exchanges, config.MIN_QUALITY)
    train, val, test = split_by_session(kept, config.SPLIT)

    ft_train = [to_chat(e, config.FINETUNE_SYSTEM_PROMPT) for e in train]
    ft_val = [to_chat(e, config.FINETUNE_SYSTEM_PROMPT) for e in val]

    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / "finetune_train.jsonl", ft_train)
    write_jsonl(out_dir / "finetune_val.jsonl", ft_val)
    write_jsonl(out_dir / "rag.jsonl", [to_rag(e) for e in train + val])
    write_jsonl(out_dir / "test.jsonl", test)

    report = {
        "min_quality": config.MIN_QUALITY,
        "split": config.SPLIT,
        "exchanges_in": len(exchanges),
        "dropped": dict(dropped),
        "usable": len(kept),
        "train": describe(train),
        "val": describe(val),
        "test": describe(test),
        "shared_sessions": len({e["session_id"] for e in train + val} & {e["session_id"] for e in test}),
        "finetune_tokens_approx": {"train": approx_tokens(ft_train), "val": approx_tokens(ft_val)},
        "rag_records": len(train) + len(val),
    }
    (out_dir / "step4_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 4: filter, split by time, write fine-tune / RAG / test files.")
    parser.add_argument("--input", type=Path, default=config.DATA_DIR / "exchanges_tagged.jsonl")
    parser.add_argument("--out", type=Path, default=config.DATA_DIR)
    args = parser.parse_args()
    print(json.dumps(run(args.input, args.out), indent=2))


if __name__ == "__main__":
    main()
