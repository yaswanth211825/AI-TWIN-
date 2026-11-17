"""
Step 1 of the AI Twin data pipeline: parse and clean a WhatsApp export.

    raw _chat.txt  ──parse──▶  messages  ──clean──▶  kept / dropped  ──redact──▶  data/messages.jsonl

Input : a WhatsApp chat export in the iPhone format, one message starts with
        [06/05/25, 11:46:48 PM] Name: text
Output: data/messages.jsonl   one clean message per line {id, ts, sender, text}
        data/step1_report.json counts of what was kept, dropped and redacted

This script never prints message text, only counts.

Run from the project root:
    python3 -m pipeline.step1_parse_clean
    python3 -m pipeline.step1_parse_clean --input path/to/_chat.txt
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pipeline import config

# ---------------------------------------------------------------------------
# 1. PARSE: text file -> list of RawMessage
# ---------------------------------------------------------------------------

# A line that starts a new message. WhatsApp may put an invisible left-to-right
# mark (‎) before the bracket, and a narrow no-break space ( ) before AM/PM.
HEADER = re.compile(
    r"^‎?\[(?P<date>\d{1,2}/\d{1,2}/\d{2,4}), "
    r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?[\s  ]?[AaPp][Mm])\] "
    r"(?P<sender>[^:]+): ?(?P<text>.*)$"
)


@dataclass
class RawMessage:
    ts: datetime
    sender: str
    text: str


def parse_timestamp(date: str, time: str) -> datetime:
    time = time.replace(" ", " ").replace(" ", " ").upper()
    if " " not in time:  # "11:46PM" -> "11:46 PM"
        time = time[:-2] + " " + time[-2:]
    time_formats = ("%I:%M:%S %p", "%I:%M %p")
    for date_format in config.DATE_FORMATS:
        for time_format in time_formats:
            try:
                return datetime.strptime(f"{date} {time}", f"{date_format} {time_format}")
            except ValueError:
                continue
    raise ValueError(f"Unrecognised timestamp: {date} {time}")


def parse(lines: list[str]) -> tuple[list[RawMessage], int]:
    """Groups lines into messages. A line without a header continues the previous message.

    Returns the messages and the number of lines that came before any message (orphans).
    """
    messages: list[RawMessage] = []
    orphans = 0
    for line in lines:
        match = HEADER.match(line)
        if match:
            messages.append(RawMessage(
                ts=parse_timestamp(match["date"], match["time"]),
                sender=match["sender"].strip(),
                text=match["text"],
            ))
        elif messages:
            messages[-1].text += "\n" + line
        elif line.strip():
            orphans += 1
    return messages, orphans


# ---------------------------------------------------------------------------
# 2. CLEAN: decide what to drop, strip WhatsApp markers
# ---------------------------------------------------------------------------

INVISIBLE = re.compile(r"[‎‏﻿]")
EDITED_MARKER = re.compile(r"\s*<This message was edited>\s*$")
URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)

# A photo/video/GIF sent with a caption is exported as "caption image omitted".
# The caption is real writing, so we keep it and remove only the marker.
CAPTION_MEDIA = re.compile(r"\s*\b(?:image|video|audio|sticker|GIF) omitted$", re.IGNORECASE)

# Checked in order; the first pattern that matches the whole message is the drop reason.
DROP_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("media", re.compile(r"^(?:image|video|audio|sticker|GIF|Contact card) omitted$", re.IGNORECASE)),
    ("media", re.compile(r"^.*\bdocument omitted$", re.IGNORECASE)),  # text before it is only the file name
    ("media", re.compile(r"^<attached: [^>]+>$")),
    ("deleted", re.compile(r"^(?:This message was deleted|You deleted this message)\.?$")),
    ("call", re.compile(r"^(?:Missed )?(?:voice|video) call\b", re.IGNORECASE)),
    ("system", re.compile(
        r"^(?:Messages and calls are end-to-end encrypted"
        r"|.*changed their phone number"
        r"|.*security code (?:with .* )?changed"
        r"|.*turned (?:on|off) disappearing messages"
        r"|.*(?:created|added|removed|left|joined)\b.*group)",
        re.IGNORECASE)),
]


@dataclass
class Cleaned:
    text: str | None          # None when the message is dropped
    drop_reason: str | None   # why it was dropped
    was_edited: bool = False  # had "<This message was edited>"
    was_caption: bool = False # text kept from a photo/video caption


def tidy(text: str) -> str:
    """Trims each line but keeps line breaks: they are part of how you write."""
    lines = [line.rstrip() for line in text.strip().split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines))


def clean(text: str) -> Cleaned:
    text = INVISIBLE.sub("", text)
    was_edited = bool(EDITED_MARKER.search(text))
    text = tidy(EDITED_MARKER.sub("", text))

    if not text:
        return Cleaned(None, "empty", was_edited)
    for reason, pattern in DROP_RULES:
        if pattern.search(text):
            return Cleaned(None, reason, was_edited)

    was_caption = bool(CAPTION_MEDIA.search(text))
    text = tidy(CAPTION_MEDIA.sub("", text))

    if not URL.sub("", text).strip():
        return Cleaned(None, "link_only", was_edited)
    return Cleaned(text, None, was_edited, was_caption)


# ---------------------------------------------------------------------------
# 3. REDACT: replace private data with placeholders
# ---------------------------------------------------------------------------

# Order matters: links first (they contain @ and digits), then emails before UPI ids,
# phone numbers before generic long numbers.
REDACTIONS: list[tuple[str, re.Pattern[str], str]] = [
    ("link", URL, "[LINK]"),
    ("email", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[EMAIL]"),
    ("upi", re.compile(r"\b[\w.-]+@(?:ok\w+|ybl|paytm|upi|ibl|axl|apl)\b", re.IGNORECASE), "[UPI]"),
    ("phone", re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)"), "[PHONE]"),
    ("otp", re.compile(r"(?i)\b(otp|code|pin)\b(\D{0,15}?)\d{4,8}\b"), r"\1\2[OTP]"),
    ("long_number", re.compile(r"(?<!\d)\d(?:[\s-]?\d){11,18}(?!\d)"), "[NUMBER]"),
]


def redact(text: str, counts: Counter[str]) -> str:
    for name, pattern, replacement in REDACTIONS:
        text, n = pattern.subn(replacement, text)
        counts[name] += n
    return text


# ---------------------------------------------------------------------------
# Run all three and write the outputs
# ---------------------------------------------------------------------------

TELUGU_SCRIPT = re.compile(r"[ఀ-౿]")


def run(input_path: Path, out_dir: Path) -> dict:
    lines = input_path.read_text(encoding="utf-8").split("\n")
    raw, orphans = parse(lines)

    dropped: Counter[str] = Counter()
    redacted: Counter[str] = Counter()
    senders_raw: Counter[str] = Counter()
    kept_by_sender: Counter[str] = Counter()
    edited = captions = multiline = telugu = 0
    kept: list[dict] = []

    for message in raw:
        senders_raw[message.sender] += 1
        result = clean(message.text)
        edited += result.was_edited
        if result.text is None:
            dropped[result.drop_reason] += 1
            continue
        captions += result.was_caption
        text = redact(result.text, redacted)
        sender = "me" if message.sender in config.ME_NAMES else "friend"
        kept_by_sender[sender] += 1
        multiline += "\n" in text
        telugu += bool(TELUGU_SCRIPT.search(text))
        kept.append({"id": len(kept) + 1, "ts": message.ts.isoformat(), "sender": sender, "text": text})

    out_of_order = sum(1 for a, b in zip(raw, raw[1:]) if b.ts < a.ts)
    report = {
        "input": input_path.name,
        "parsed_messages": len(raw),
        "orphan_lines": orphans,
        "out_of_order": out_of_order,
        "senders_in_export": dict(senders_raw),
        "dropped": dict(dropped.most_common()),
        "dropped_total": sum(dropped.values()),
        "kept": len(kept),
        "kept_by_sender": dict(kept_by_sender),
        "edited_markers_removed": edited,
        "captions_kept": captions,
        "redacted": {k: v for k, v in redacted.items() if v},
        "multiline_messages": multiline,
        "telugu_script_messages": telugu,
        "first": kept[0]["ts"] if kept else None,
        "last": kept[-1]["ts"] if kept else None,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "messages.jsonl").open("w", encoding="utf-8") as f:
        for row in kept:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out_dir / "step1_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 1: parse and clean a WhatsApp export.")
    parser.add_argument("--input", type=Path, default=config.RAW_CHAT, help="WhatsApp export (.txt)")
    parser.add_argument("--out", type=Path, default=config.DATA_DIR, help="output folder")
    args = parser.parse_args()

    report = run(args.input, args.out)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nWrote {report['kept']} messages to {args.out / 'messages.jsonl'}")


if __name__ == "__main__":
    main()
