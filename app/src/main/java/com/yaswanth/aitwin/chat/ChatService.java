package com.yaswanth.aitwin.chat;

import java.util.List;
import java.util.UUID;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.messages.MessageType;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

/** Chat use cases. Every call first checks that the chat belongs to the calling browser. */
@Service
public class ChatService {

    private static final int TITLE_LENGTH = 40;

    private final ChatClient chatClient;
    private final ChatMemory chatMemory;
    private final ConversationRepository conversations;

    public ChatService(ChatClient chatClient, ChatMemory chatMemory, ConversationRepository conversations) {
        this.chatClient = chatClient;
        this.chatMemory = chatMemory;
        this.conversations = conversations;
    }

    public Conversation create(UUID clientId) {
        return conversations.create(clientId);
    }

    public List<Conversation> list(UUID clientId) {
        return conversations.findAllByClient(clientId);
    }

    /**
     * Streams the reply chunk by chunk. The conversation id is the ONLY key the memory advisor
     * uses, so the model sees this chat's history and nothing from any other chat.
     */
    public Flux<String> send(UUID conversationId, UUID clientId, String text) {
        requireOwned(conversationId, clientId);
        conversations.touch(conversationId, titleFrom(text));
        return chatClient.prompt()
                .user(text)
                .advisors(a -> a.param(ChatMemory.CONVERSATION_ID, conversationId.toString()))
                .stream()
                .content();
    }

    public List<ChatMessage> history(UUID conversationId, UUID clientId) {
        requireOwned(conversationId, clientId);
        return chatMemory.get(conversationId.toString()).stream()
                .filter(m -> m.getMessageType() == MessageType.USER || m.getMessageType() == MessageType.ASSISTANT)
                .map(m -> new ChatMessage(m.getMessageType() == MessageType.USER ? "user" : "assistant", m.getText()))
                .toList();
    }

    public void delete(UUID conversationId, UUID clientId) {
        requireOwned(conversationId, clientId);
        chatMemory.clear(conversationId.toString());
        conversations.delete(conversationId);
    }

    private void requireOwned(UUID conversationId, UUID clientId) {
        conversations.findOwned(conversationId, clientId)
                .orElseThrow(() -> new ConversationNotFoundException(conversationId));
    }

    static String titleFrom(String text) {
        String oneLine = text.strip().replaceAll("\\s+", " ");
        return oneLine.length() <= TITLE_LENGTH ? oneLine : oneLine.substring(0, TITLE_LENGTH - 1) + "…";
    }
}
