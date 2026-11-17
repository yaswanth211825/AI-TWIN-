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
| 3 | `pipeline/step3_exchanges.py` | `data/exchanges.jsonl`, `data/step3_report.json` | done |
| 3b | `pipeline/step3b_tags.py` | `data/exchanges_tagged.jsonl`, `data/step3b_report.json` | done |
| 4 | `pipeline/step4_split.py` | `data/finetune_train.jsonl`, `finetune_val.jsonl`, `rag.jsonl`, `test.jsonl` | done |
| 5 | baseline score | | next |
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

## Step 3: exchanges

```bash
python3 -m pipeline.step3_exchanges
```

An exchange is the training and retrieval unit: one of your replies plus up to `CONTEXT_TURNS` (3) turns before it in the same session.

- **Reply:** a turn by `me` whose previous turn in the same session is by `friend`.
- **Dropped:** replies with redaction placeholders, replies over `MAX_REPLY_CHARS`, and copies of the same reply beyond `MAX_SAME_REPLY` (chosen by a stable hash, so re-runs match).
- **Kept but marked `low_value`:** fillers like "ok", "hmm" or emoji only.

Output row:

```json
{"exchange_id": 1, "session_id": 1, "ts": "...", "context": [{"sender": "friend", "text": "..."}],
 "reply": "...", "reply_n_messages": 2, "latency_seconds": 42, "low_value": false}
```

## Step 3b: tags

```bash
python3 -m pipeline.step3b_tags export   # compact batches in data/tag_batches/
python3 -m pipeline.step3b_tags merge    # validates data/tags/*.tsv and writes exchanges_tagged.jsonl
```

Each exchange gets four tags, written by an LLM reading the exported batches and checked on merge:

| Tag | Values |
|---|---|
| `topic` | career, studies, tech, plans, banter, personal, family, daily, other |
| `type` | answer, question, teasing, support, plan, reaction, smalltalk |
| `quality` | 1 (says nothing about your style) to 5 (very typical) |
| `private` | true when the reply or its context holds secrets, third-party sensitive details or content the twin should never repeat |

Later steps keep exchanges with `quality >= 3` and `private == false`.

## Step 4: filter and split

```bash
python3 -m pipeline.step4_split
```

- **Filter:** keep exchanges with `quality >= MIN_QUALITY` (3) that are not `private`.
- **Split:** oldest 80% train, next 10% validation, newest 10% test, cutting only at session boundaries so neighbouring messages never land on both sides (no leakage).
- **Outputs:**

| File | Used for | Format |
|---|---|---|
| `finetune_train.jsonl`, `finetune_val.jsonl` | Fine-tuning (step 6) | OpenAI chat format; earlier replies of yours in the context get `"weight": 0` so only the final reply is learned |
| `rag.jsonl` | pgvector index (step 7) | `embed_text` = the friend's last turn; `reply` stored as the style example |
| `test.jsonl` | Scoring only (steps 5 and 9) | Never trained on or indexed |

## Tests

Tests use made-up messages only.

```bash
python3 -m unittest discover -s tests -v
```

Needs Python 3.10+ and no extra packages.
