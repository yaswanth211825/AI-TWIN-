# AI Twin 5

An AI twin that replies like Yaswanth, built from scratch with **fine-tuning + RAG**.
This repo starts with the data pipeline that turns a WhatsApp export into training and retrieval data.

Real chats and everything generated from them live in `data/`, which is git-ignored.
The raw export stays outside the project (`~/Downloads/Mustang_Chats/`).

## Pipeline

| Step | Script | Output | Status |
|---|---|---|---|
| 1 | `pipeline/step1_parse_clean.py` | `data/messages.jsonl`, `data/step1_report.json` | done |
| 2 | bursts and sessions | | next |
| 3 | build exchanges | | |
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

## Tests

Tests use made-up messages only.

```bash
python3 -m unittest discover -s tests -v
```

Needs Python 3.10+ and no extra packages.
