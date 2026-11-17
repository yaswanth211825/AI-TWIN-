-- One row per chat in the sidebar. The id is also the Spring AI conversation id,
-- so each chat's memory is stored and loaded only under its own id.
CREATE TABLE IF NOT EXISTS conversations (
    id          UUID PRIMARY KEY,
    client_id   UUID        NOT NULL,              -- which browser owns the chat
    title       TEXT        NOT NULL DEFAULT 'New chat',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The sidebar query: this browser's chats, newest first.
CREATE INDEX IF NOT EXISTS idx_conversations_client_updated
    ON conversations (client_id, updated_at DESC);
