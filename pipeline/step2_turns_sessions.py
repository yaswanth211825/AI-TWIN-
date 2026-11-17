"""
Step 2 of the AI Twin data pipeline: merge bursts into turns and cut the chat into sessions.

    messages.jsonl ──session cut (> 60 min)──▶ sessions ──burst merge (< 2 min, same sender)──▶ turns.jsonl

A "turn" is everything one person says before the other person replies, e.g.
    me: "ha vachayi"  + me: "digital lo select ayya"   ->  one turn "ha vachayi\ndigital lo select ayya"

A "session" is one conversation: a silence longer than SESSION_GAP_MINUTES starts a new one.
A turn never crosses a session boundary.

Input : data/messages.jsonl      (from step 1)
Output: data/turns.jsonl         {turn_id, session_id, sender, start, end, n_messages, text}
        data/step2_report.json   counts only

Run from the project root:
    python3 -m pipeline.step2_turns_sessions
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from pipeline import config


@dataclass
class Turn:
    turn_id: int
    session_id: int
    sender: str
    start: str
    end: str
    n_messages: int
    text: str


def build_turns(messages: list[dict], burst_gap: timedelta, session_gap: timedelta) -> list[Turn]:
    """Messages must be in time order. Returns turns in time order."""
    turns: list[Turn] = []
    session_id = 0
    previous_ts: datetime | None = None

    for message in messages:
        ts = datetime.fromisoformat(message["ts"])
        gap = ts - previous_ts if previous_ts else None
        previous_ts = ts

        if gap is None or gap > session_gap:
            session_id += 1
            new_session = True
        else:
            new_session = False

        last = turns[-1] if turns else None
        same_burst = (
            last is not None
            and not new_session
            and last.sender == message["sender"]
            and gap <= burst_gap
        )
        if same_burst:
            last.text += "\n" + message["text"]
            last.end = message["ts"]
            last.n_messages += 1
        else:
            turns.append(Turn(
                turn_id=len(turns) + 1,
                session_id=session_id,
                sender=message["sender"],
                start=message["ts"],
                end=message["ts"],
                n_messages=1,
                text=message["text"],
            ))
    return turns


def report_for(messages: list[dict], turns: list[Turn]) -> dict:
    sessions: dict[int, list[Turn]] = {}
    for turn in turns:
        sessions.setdefault(turn.session_id, []).append(turn)

    turns_per_session = [len(t) for t in sessions.values()]
    one_sided = sum(1 for t in sessions.values() if len({x.sender for x in t}) == 1)
    by_sender = Counter(t.sender for t in turns)

    def avg_messages(sender: str) -> float:
        counts = [t.n_messages for t in turns if t.sender == sender]
        return round(statistics.mean(counts), 2) if counts else 0.0

    return {
        "burst_gap_minutes": config.BURST_GAP_MINUTES,
        "session_gap_minutes": config.SESSION_GAP_MINUTES,
        "messages_in": len(messages),
        "turns": len(turns),
        "turns_by_sender": dict(by_sender),
        "avg_messages_per_turn": {s: avg_messages(s) for s in by_sender},
        "sessions": len(sessions),
        "one_sided_sessions": one_sided,
        "turns_per_session": {
            "median": statistics.median(turns_per_session) if turns else 0,
            "max": max(turns_per_session, default=0),
            "sessions_with_1_turn": sum(1 for n in turns_per_session if n == 1),
        },
        # Every place where you reply to the friend inside a session. Step 3 turns these into exchanges.
        "my_replies_in_session": sum(
            1 for a, b in zip(turns, turns[1:])
            if b.sender == "me" and a.sender != "me" and a.session_id == b.session_id
        ),
    }


def run(input_path: Path, out_dir: Path) -> dict:
    messages = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(b["ts"] < a["ts"] for a, b in zip(messages, messages[1:])):
        raise ValueError("messages.jsonl is not in time order; re-run step 1")

    turns = build_turns(
        messages,
        burst_gap=timedelta(minutes=config.BURST_GAP_MINUTES),
        session_gap=timedelta(minutes=config.SESSION_GAP_MINUTES),
    )
    report = report_for(messages, turns)

    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "turns.jsonl").open("w", encoding="utf-8") as f:
        for turn in turns:
            f.write(json.dumps(asdict(turn), ensure_ascii=False) + "\n")
    (out_dir / "step2_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 2: merge bursts into turns and cut sessions.")
    parser.add_argument("--input", type=Path, default=config.DATA_DIR / "messages.jsonl")
    parser.add_argument("--out", type=Path, default=config.DATA_DIR)
    args = parser.parse_args()

    report = run(args.input, args.out)
    print(json.dumps(report, indent=2))
    print(f"\nWrote {report['turns']} turns in {report['sessions']} sessions to {args.out / 'turns.jsonl'}")


if __name__ == "__main__":
    main()
