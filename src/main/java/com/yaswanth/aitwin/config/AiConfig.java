package com.yaswanth.aitwin.config;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.MessageChatMemoryAdvisor;
import org.springframework.ai.chat.client.advisor.vectorstore.QuestionAnswerAdvisor;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.memory.MessageWindowChatMemory;
import org.springframework.ai.chat.memory.repository.jdbc.JdbcChatMemoryRepository;
import org.springframework.ai.chat.prompt.PromptTemplate;
import org.springframework.ai.template.st.StTemplateRenderer;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.Resource;

/**
 * Wires the whole AI pipeline. Every chat request flows through:
 * 1. MessageChatMemoryAdvisor - loads the last N messages of THIS conversation only, saves the new turn.
 * 2. QuestionAnswerAdvisor    - embeds the user message, finds similar past replies in pgvector (RAG),
 *                               and appends them to the user message as style examples.
 * 3. OpenAI chat model        - generates the reply, streamed token by token.
 */
@Configuration
public class AiConfig {

    /**
     * Template the RAG advisor uses to augment the user message.
     * Placeholders use angle-bracket delimiters: query = what the user typed,
     * question_answer_context = the retrieved documents.
     */
    private static final String STYLE_EXAMPLES_TEMPLATE = """
            <query>

            (Style reference, not part of the chat. How Yaswanth replied to similar messages before:
            <question_answer_context>
            Use these only for tone and wording. Reply to the message above.)
            """;

    /** Conversation memory persisted in Postgres (table spring_ai_chat_memory), keyed by conversation id. */
    @Bean
    ChatMemory chatMemory(JdbcChatMemoryRepository repository,
                          @Value("${ai-twin.memory-window}") int memoryWindow) {
        return MessageWindowChatMemory.builder()
                .chatMemoryRepository(repository)
                .maxMessages(memoryWindow)
                .build();
    }

    @Bean
    ChatClient chatClient(ChatClient.Builder builder,
                          ChatMemory chatMemory,
                          VectorStore vectorStore,
                          @Value("classpath:prompts/persona.st") Resource persona,
                          @Value("${ai-twin.retrieval.top-k}") int topK,
                          @Value("${ai-twin.retrieval.similarity-threshold}") double threshold) {

        var styleTemplate = PromptTemplate.builder()
                .renderer(StTemplateRenderer.builder().startDelimiterToken('<').endDelimiterToken('>').build())
                .template(STYLE_EXAMPLES_TEMPLATE)
                .build();

        var ragAdvisor = QuestionAnswerAdvisor.builder(vectorStore)
                .searchRequest(SearchRequest.builder().topK(topK).similarityThreshold(threshold).build())
                .promptTemplate(styleTemplate)
                .build();

        // Memory runs before RAG (lower order = earlier), so the ORIGINAL user text is what gets stored,
        // not the version with style examples appended.
        var memoryAdvisor = MessageChatMemoryAdvisor.builder(chatMemory).build();

        return builder
                .defaultSystem(persona)
                .defaultAdvisors(memoryAdvisor, ragAdvisor)
                .build();
    }
}
