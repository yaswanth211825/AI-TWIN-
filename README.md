# AI Twin 5

An AI twin that replies like Yaswanth, built from scratch with **fine-tuning + RAG**.
This repo starts with the data pipeline that turns a WhatsApp export into training and retrieval data.

Real chats and everything generated from them live in `data/`, which is git-ignored.
The raw export stays outside the project (`~/Downloads/Mustang_Chats/`).

## Pipeline

| Step | Script | Output | Status |
|---|---|---|---|
| 1 | `pipeline/step1_parse_clean.py` | `data/messages.jsonl`, `data/step1_report.json` | done |
| 2 | `pipeline/step2_turns_sessions.py` | `data/turns.jsonl`, `data/step2_report.json` | done |
| 3 | build exchanges | | next |
| 4 | time split: train / test | | |
| 5 | baseline score | | |
| 6 | fine-tune | | |
| 7 | rebuild RAG index | | |
| 8 | wire into the app | | |
| 9 | compare | | |

## Step 1: parse and clean

```bash
python3 -m pipeline.step1_parse_clean
```

- **Parse:** a line starting with `[dd/mm/yy, h:mm:ss PM] Name:` starts a message; other lines continue the previous one.
- **Clean:** drops media, deleted messages, calls, system notices and link-only messages; removes the `<This message was edited>` marker; keeps photo captions; keeps line breaks.
- **Redact:** links, emails, UPI ids, phone numbers, OTPs and long ID/card numbers become placeholders like `[PHONE]`.
- **Report:** prints counts only, never message text.

Output row:

```json
{"id": 1, "ts": "2025-05-06T23:46:48", "sender": "friend", "text": "..."}
```

## Step 2: turns and sessions

```bash
python3 -m pipeline.step2_turns_sessions
```

- **Session:** a silence longer than `SESSION_GAP_MINUTES` (60) starts a new conversation.
- **Turn:** messages from the same sender, each within `BURST_GAP_MINUTES` (2) of the previous one, become one turn joined by line breaks. A turn never crosses a session.
- Both thresholds live in `pipeline/config.py` and were chosen from the gap histogram of the real chat.

Output row:

```json
{"turn_id": 1, "session_id": 1, "sender": "me", "start": "...", "end": "...", "n_messages": 2, "text": "line one\nline two"}
```

## Tests

Tests use made-up messages only.

```bash
python3 -m unittest discover -s tests -v
```

Needs Python 3.10+ and no extra packages.
