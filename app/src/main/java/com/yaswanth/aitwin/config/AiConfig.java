package com.yaswanth.aitwin.config;

import com.yaswanth.aitwin.TwinProperties;
import com.yaswanth.aitwin.chat.EmojiFilterAdvisor;
import com.yaswanth.aitwin.chat.StyleExamplesAdvisor;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.MessageChatMemoryAdvisor;
import org.springframework.ai.chat.client.advisor.api.Advisor;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.memory.MessageWindowChatMemory;
import org.springframework.ai.chat.memory.repository.jdbc.JdbcChatMemoryRepository;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.core.io.Resource;

/**
 * Wires the chat pipeline. Each message passes through three advisors, in order:
 *
 *   1. MessageChatMemoryAdvisor  loads the last N messages of THIS conversation; after the reply, saves the turn
 *   2. EmojiFilterAdvisor        filters the reply on its way back, so memory stores the filtered text
 *   3. StyleExamplesAdvisor      adds your most similar past replies (pgvector) to the user message
 *   → gpt-6-luna                 generates the reply, streamed token by token
 *
 * Lower order runs first on the way in and last on the way out.
 *
 * A second client, "evalChatClient", is the same pipeline without memory: step 9 passes each test
 * conversation in directly, so evaluation never writes into anyone's chat history.
 */
@Configuration
public class AiConfig {

    private static final int MEMORY_ORDER = Advisor.DEFAULT_CHAT_MEMORY_PRECEDENCE_ORDER;

    /** Conversation memory in PostgreSQL (table spring_ai_chat_memory), keyed by conversation id. */
    @Bean
    ChatMemory chatMemory(JdbcChatMemoryRepository repository, TwinProperties props) {
        return MessageWindowChatMemory.builder()
                .chatMemoryRepository(repository)
                .maxMessages(props.chat().memoryWindow())
                .build();
    }

    /** The client the chat API uses. */
    @Bean
    @Primary
    ChatClient chatClient(ChatClient.Builder builder, ChatMemory chatMemory, VectorStore vectorStore,
                          TwinProperties props, @Value("classpath:prompts/persona.st") Resource persona)
            throws IOException {
        Advisor memory = MessageChatMemoryAdvisor.builder(chatMemory).order(MEMORY_ORDER).build();
        return build(builder, persona, props.chat().partner(), vectorStore, props, memory);
    }

    /** Same persona, emoji filter and style examples; no memory. Used only by eval.ReplyExporter. */
    @Bean
    ChatClient evalChatClient(ChatClient.Builder builder, VectorStore vectorStore, TwinProperties props,
                              @Value("classpath:prompts/persona.st") Resource persona) throws IOException {
        return build(builder, persona, props.eval().partner(), vectorStore, props, null);
    }

    private static ChatClient build(ChatClient.Builder builder, Resource persona, String partner,
                                    VectorStore vectorStore, TwinProperties props, Advisor memory)
            throws IOException {
        String systemPrompt = persona.getContentAsString(StandardCharsets.UTF_8).replace("{partner}", partner);

        List<Advisor> advisors = new ArrayList<>();
        if (memory != null) {
            advisors.add(memory);
        }
        advisors.add(new EmojiFilterAdvisor(props.chat().emojiKeepRate(), MEMORY_ORDER + 1));
        advisors.add(new StyleExamplesAdvisor(vectorStore, props.chat().topK(), MEMORY_ORDER + 2));

        return builder.defaultSystem(systemPrompt).defaultAdvisors(advisors).build();
    }
}
