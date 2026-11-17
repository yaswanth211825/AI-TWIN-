# AI Twin (Spring AI)

A ChatGPT-style chat with Yaswanth's AI twin. Each chat has its own memory; nothing leaks between chats.

**Stack:** Java 21 · Spring Boot 4.1 · Spring AI 2.0 · Spring Web · Spring JDBC · PostgreSQL + pgvector · OpenAI

## How a message flows

```
Browser ── POST /api/conversations/{id}/messages ──▶ ChatController
                                                       │
                                                  ChatService  (checks the chat belongs to this browser)
                                                       │
                                     ChatClient.prompt().user(text)
                                       .advisors(CONVERSATION_ID = id)
                                                       │
   1. MessageChatMemoryAdvisor ── loads last 20 messages of THIS chat (spring_ai_chat_memory)
   2. QuestionAnswerAdvisor    ── embeds the message, top-4 similar past replies from pgvector
                                  (similarity ≥ 0.45), appended as style examples
   3. OpenAI chat model        ── persona system prompt + history + message → streamed reply
   4. Memory advisor           ── saves the user message and the full reply under this chat id
                                                       │
Browser ◀── Server-Sent Events: token, token, …, done ─┘
```

## Code map

| File | Role |
|---|---|
| `config/AiConfig.java` | Builds the `ChatClient`: persona prompt, memory advisor, RAG advisor |
| `chat/ChatController.java` | REST API + SSE streaming |
| `chat/ChatService.java` | Ownership check, title, passes the conversation id to Spring AI |
| `chat/ConversationRepository.java` | Sidebar list of chats (JdbcTemplate) |
| `ingest/StyleExampleLoader.java` | RAG ingestion: `data.jsonl` → embeddings → pgvector, once |
| `resources/prompts/persona.st` | Who the twin is and how it talks |
| `resources/schema.sql` | `conversations` table |
| `resources/static/index.html` | The chat page |

## Tables

| Table | Created by | Holds |
|---|---|---|
| `conversations` | `schema.sql` | One row per chat: id, owner (client id), title |
| `spring_ai_chat_memory` | Spring AI | Every message, keyed by conversation id |
| `vector_store` | Spring AI | Style examples: text, metadata, 1536-dim embedding, HNSW index |

## Run locally

1. Start Postgres with pgvector (port 5433):
   ```bash
   docker compose up -d
   ```
2. Put your key in `.env` (git-ignored): `OPENAI_API_KEY=sk-...`
3. Start the app:
   ```bash
   set -a && source .env && set +a && ./mvnw spring-boot:run
   ```
4. Open http://localhost:8090

Optional environment variables: `OPENAI_MODEL` (default `gpt-5.4`), `OPENAI_REASONING_EFFORT` (default `low`; lower is faster), `PORT` (default 8090), `DB_URL`, `DB_USERNAME`, `DB_PASSWORD`.

## API

All requests send `X-Client-Id: <uuid>` (the page generates one per browser).

| Method | Path | Does |
|---|---|---|
| POST | `/api/conversations` | New chat |
| GET | `/api/conversations` | This browser's chats, newest first |
| GET | `/api/conversations/{id}/messages` | Chat history |
| POST | `/api/conversations/{id}/messages` | Send `{"text": "..."}`, reply streams as SSE |
| DELETE | `/api/conversations/{id}` | Delete chat and its memory |

## Guardrails

| Guardrail | Where | Default |
|---|---|---|
| Access code (shared password) | `GuardrailInterceptor`, `APP_ACCESS_CODE` | Off when empty |
| Messages per minute, per IP | `GuardrailInterceptor` | 8 |
| Messages per day, per IP | `GuardrailInterceptor` | 150 |
| New chats per hour, per IP | `GuardrailInterceptor` | 20 |
| Messages per day, everyone combined | `GuardrailInterceptor` | 500 (300 on Render) |
| Max message length | `SendMessageRequest` `@Size` | 2000 characters |
| Max reply length | `max-completion-tokens` | 2000 tokens |
| Chats isolated per browser | `ConversationRepository` SQL | Always |
| Prompt-injection rules | `persona.st` hard rules | Always |
| No error details sent to the browser | `server.error.*` | Always |

Limits are in memory: they reset when the app restarts and count per instance.
Also set a monthly **spend limit** in the OpenAI dashboard; it is the only hard cap on cost.

## Deploy to Render (app + database in one step)

1. Push this folder to GitHub. `src/main/resources/data.jsonl` (real chats) is git-ignored, so a build from git starts without style examples. To deploy with them, build the Docker image locally where the file exists, or push to a private repo with the file included.
2. Render dashboard → **New → Blueprint** → choose the repo. `render.yaml` creates the web service and a Postgres database and connects them.
3. Paste `OPENAI_API_KEY` and, optionally, `APP_ACCESS_CODE` when asked.
4. Wait for the first build (a few minutes). Open the service URL.

`docker-entrypoint.sh` converts Render's `DATABASE_URL` into the JDBC URL Spring needs. Spring AI enables pgvector and creates its tables on first start.

## Known limits

- `X-Client-Id` separates browsers but is not authentication; anyone with a chat id and client id can read that chat.
- Memory is a sliding window of 20 messages; older messages in a long chat are dropped from the prompt (not yet summarised).
- Style examples are embedded once at startup; changing `data.jsonl` needs the `vector_store` table cleared.
