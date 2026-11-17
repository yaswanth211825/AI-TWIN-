package com.yaswanth.aitwin.chat;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.UUID;

/** A chat in the sidebar. */
record Conversation(UUID id, String title, Instant updatedAt) {
}

/** One message shown when reopening a chat. role is "user" or "assistant". */
record ChatMessage(String role, String text) {
}

/** Body of POST /api/conversations/{id}/messages. @Valid in the controller enforces the limits. */
record SendMessageRequest(@NotBlank @Size(max = 2000) String text) {
}

/** The chat does not exist or belongs to another browser. Mapped to 404, so ids cannot be probed. */
class ConversationNotFoundException extends RuntimeException {
    ConversationNotFoundException(UUID id) {
        super("No conversation " + id);
    }
}
