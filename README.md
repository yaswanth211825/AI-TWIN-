# AI Twin 5

An AI twin that replies like Yaswanth, built from scratch with **RAG** (retrieval-augmented generation).
This repo starts with the data pipeline that turns WhatsApp exports into a retrieval index and a held-out test set.

Real chats and everything generated from them live in `data/`, which is git-ignored.
The raw exports stay outside the project (`~/Downloads/Mustang_Chats/`): the 2024 chat and the merged 2025-26 exports
with the same friend (`config.RAW_CHATS`).

**Why no fine-tuning:** OpenAI closed fine-tuning to new organisations on 2026-05-07 and its fine-tunable models
shut down on 2027-01-14. Fine-tuning an open model with LoRA is future scope; `step4_split.py --finetune` still
writes the training files for it.

## Pipeline

| Step | Script | Output | Status |
|---|---|---|---|
| 1 | `pipeline/step1_parse_clean.py` | `data/messages.jsonl`, `data/step1_report.json` | done |
| 2 | `pipeline/step2_turns_sessions.py` | `data/turns.jsonl`, `data/step2_report.json` | done |
| 3 | `pipeline/step3_exchanges.py` | `data/exchanges.jsonl`, `data/step3_report.json` | done |
| 3b | `pipeline/step3b_tags.py` | `data/exchanges_tagged.jsonl`, `data/step3b_report.json` | done |
| 4 | `pipeline/step4_split.py` | `data/rag.jsonl`, `data/test.jsonl` | done |
| 5 | `pipeline/step5_baseline.py` | `data/eval/results.json`, `data/eval/prompts_*.jsonl` | offline baselines done; LLM baselines need replies |
| 6 | choose the generation model (`step5_baseline.py --openai`) | `data/eval/results_sample40.json` | pilot ready; needs a run with your key |
| 7 | `app/` (`RagIndexer`, `RetrievalExporter`) + `pipeline/step7_retrieval_eval.py` | pgvector table `style_examples`, `data/eval/step7_retrieval.json` | done |
| 8 | wire into the Spring AI app | | next |
| 9 | compare and blind test | | |

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
- **Split (`SPLIT` in config):** oldest 90% becomes the retrieval index, newest 10% the test set, cutting only at session boundaries so neighbouring messages never land on both sides (no leakage).
- **Outputs:**

| File | Used for | Format |
|---|---|---|
| `rag.jsonl` | pgvector index (step 7) | `embed_text` = the friend's last turn; `reply` and context stored as the style example |
| `test.jsonl` | Scoring only (steps 5 and 9) | Never indexed |
| `finetune_*.jsonl` (only with `--finetune`) | Future LoRA fine-tuning | OpenAI chat format; earlier replies of yours in the context get `"weight": 0` |

## Step 5: baseline score

```bash
python3 -m pipeline.step5_baseline                  # score everything that has replies
python3 -m pipeline.step5_baseline --export-prompts # write LLM prompts to data/eval/
python3 -m pipeline.step5_baseline --openai MODEL   # generate LLM replies (uses OPENAI_API_KEY, costs money)
```

Every system answers the same held-out test messages and is scored against your real replies
(`pipeline/metrics.py`, standard library only):

| Metric | Meaning |
|---|---|
| `chrF` | character n-gram overlap with your real reply, 0 to 100; robust to Tenglish spelling variants |
| `length_ratio_median`, `length_error` | how close the reply length is to yours |
| `multiline`, `tenglish`, `your_vocabulary`, `emoji` | style; compare with the "your real replies" row |
| `assistant_speak` | share of replies that sound like a chatbot; should be 0 |

Systems: `random_reply` and `nearest_reply` (BM25, `pipeline/retrieval.py`) need no API;
`prompt_only` and `prompt_rag` are LLM baselines scored once `data/eval/replies_<system>.jsonl` exists.

## Tests

Tests use made-up messages only.

```bash
python3 -m unittest discover -s tests -v
```

Needs Python 3.10+ and no extra packages.

## Step 6: choose the generation model

Candidates and prices are in `config.MODEL_PRICES` (OpenAI pricing page, checked 2026-11-17).
`gpt-4o` shuts down on 2027-01-14; `gpt-6-luna` is OpenAI's listed replacement. Reasoning is switched
off (`config.REASONING_EFFORT`) because a chat reply does not need hidden "thinking" tokens.

```bash
python3 -m pipeline.step5_baseline --sample 40 --estimate gpt-6-luna,gpt-6.1-terra,gpt-4o   # cost only
python3 -m pipeline.step5_baseline --sample 40 --openai gpt-6-luna,gpt-6.1-terra,gpt-4o     # pilot (needs OPENAI_API_KEY)
```

All models answer the same 40 test messages (`--sample`), so the comparison is fair. The winner goes into
`config.GENERATION_MODEL`.

### Step 6 results (2026-11-17, 40 test messages, prompt + RAG)

| Model | chrF | Length vs yours | Multi-line | Emoji | Est. cost (both systems) |
|---|---|---|---|---|---|
| Your real replies | 100 | 1.00 | 0.85 | 0.10 | |
| `gpt-6-luna` | 14.0 | 0.88 | 0.72 | 0.90 | $0.004 |
| `gpt-6.1-terra` | 13.8 | 0.87 | 0.95 | 0.68 | $0.04 |
| `gpt-4o` | 16.0 | 1.13 | 0.82 | 0.70 | $0.10 |

- `gpt-4o` leads chrF by +2.0 (95% CI +0.6 to +3.5), but with balanced chrF (beta = 1) the lead is +0.8
  (CI -0.5 to +2.2), i.e. mostly from longer replies. Reading the replies, its Telugu is the least natural.
- **Chosen: `gpt-6-luna`.** Same quality within noise, 22x cheaper than `gpt-4o`, current (4o shuts down 2027-01-14).
- All models overuse emoji (you: 10%). "Do not use emoji" in the prompt cut luna from 90% to 35%; an output
  filter in the app (step 8) handles the rest.
- Significance checks use `metrics.paired_bootstrap`.

## Step 7: the RAG index (Spring AI + pgvector)

The Java app lives in `app/` (Spring Boot 4.1, Spring AI 2.0, Java 21). Its own database runs on port 5434,
separate from AI Twin 4.

```bash
cd app
docker compose up -d                                   # PostgreSQL + pgvector
set -a && source <your .env with OPENAI_API_KEY> && set +a
./mvnw spring-boot:run                                 # sync the index
./mvnw spring-boot:run -Dspring-boot.run.arguments=--ai-twin.eval.export-retrieval=true   # + evaluation export
cd .. && python3 -m pipeline.step7_retrieval_eval      # embedding vs BM25
```

| File | Role |
|---|---|
| `app/.../rag/RagRecord.java` | One line of `rag.jsonl`; turns it into a Spring AI `Document` (text = friend's message, metadata = your reply, context, topic, date) with a stable UUID |
| `app/.../rag/RagIndexer.java` | Syncs the table with `rag.jsonl` at startup: embeds only new records, deletes records no longer in the file |
| `app/.../rag/RetrievalExporter.java` | Evaluation only: searches every test message in pgvector and writes the hits |
| `app/.../TwinProperties.java` | Typed `ai-twin.*` settings |
| `pipeline/step7_retrieval_eval.py` | Compares embedding search with BM25 |

Chat data is read from `../data` at run time (`RAG_DATA_DIR`) and never packaged into the app.

### Step 7 results (2026-11-17, 338 test messages, top 4)

| Retrieval | Same topic, top 1 | Same topic, top 4 | Found something |
|---|---|---|---|
| Random (chance) | 0.17 | 0.17 | |
| BM25 keywords | 0.22 | 0.19 | 0.96 |
| **Embeddings (text-embedding-3-small, pgvector HNSW, cosine)** | **0.32** | **0.33** | **1.00** |

Embeddings find same-topic examples more often: +0.10 at top 1 (95% CI +0.04 to +0.16). BM25's top 4 is close
to random because romanized Telugu has no fixed spelling. Copying the top hit's reply scores the same chrF
either way (difference within noise): examples teach style, they are not answers.
Indexing 3,366 records took about a minute and cost about $0.001; a second run embeds nothing.
