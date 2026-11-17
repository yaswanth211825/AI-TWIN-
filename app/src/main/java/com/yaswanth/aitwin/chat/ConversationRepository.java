package com.yaswanth.aitwin.chat;

import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

/**
 * The sidebar list of chats, with plain SQL through JdbcTemplate.
 * Every read is filtered by client id, so one browser never sees another's chats.
 */
@Repository
class ConversationRepository {

    private static final RowMapper<Conversation> MAPPER = (rs, n) -> new Conversation(
            rs.getObject("id", UUID.class),
            rs.getString("title"),
            rs.getTimestamp("updated_at").toInstant());

    private final JdbcTemplate jdbc;

    ConversationRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    Conversation create(UUID clientId) {
        UUID id = UUID.randomUUID();
        jdbc.update("INSERT INTO conversations (id, client_id) VALUES (?, ?)", id, clientId);
        return findOwned(id, clientId).orElseThrow();
    }

    List<Conversation> findAllByClient(UUID clientId) {
        return jdbc.query(
                "SELECT id, title, updated_at FROM conversations WHERE client_id = ? ORDER BY updated_at DESC",
                MAPPER, clientId);
    }

    Optional<Conversation> findOwned(UUID id, UUID clientId) {
        return jdbc.query("SELECT id, title, updated_at FROM conversations WHERE id = ? AND client_id = ?",
                MAPPER, id, clientId).stream().findFirst();
    }

    /** Moves the chat to the top; the first message becomes the title. */
    void touch(UUID id, String firstMessageTitle) {
        jdbc.update("""
                UPDATE conversations
                SET updated_at = now(),
                    title = CASE WHEN title = 'New chat' THEN ? ELSE title END
                WHERE id = ?
                """, firstMessageTitle, id);
    }

    void delete(UUID id) {
        jdbc.update("DELETE FROM conversations WHERE id = ?", id);
    }
}
