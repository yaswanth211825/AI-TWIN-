package com.yaswanth.aitwin.chat;

import java.util.List;
import java.util.Objects;
import org.springframework.ai.chat.client.ChatClientRequest;
import org.springframework.ai.chat.client.ChatClientResponse;
import org.springframework.ai.chat.client.advisor.api.AdvisorChain;
import org.springframework.ai.chat.client.advisor.api.BaseAdvisor;
import org.springframework.ai.document.Document;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.ai.vectorstore.VectorStore;

/**
 * RAG step: finds your past replies to messages like this one and adds them to the user message.
 *
 * Why not Spring AI's QuestionAnswerAdvisor? It only pastes each Document's text into the prompt.
 * Our Document text is the friend's message (that is what we search on); your reply lives in the
 * metadata. This advisor formats both: "They said: ... / Yaswanth replied: ...".
 *
 * Runs after the memory advisor (higher order number), so chat memory stores the message
 * exactly as the person typed it, without the examples.
 */
public class StyleExamplesAdvisor implements BaseAdvisor {

    /** Context key: the retrieved documents, for logging or evaluation. */
    public static final String RETRIEVED_EXAMPLES = "style_examples";

    private static final String TEMPLATE = """
            %s

            (Style reference, not part of the chat. How Yaswanth replied to similar messages before:
            %s
            Use these only for tone and wording. Reply to the message above.)""";

    private final VectorStore vectorStore;
    private final int topK;
    private final int order;

    public StyleExamplesAdvisor(VectorStore vectorStore, int topK, int order) {
        this.vectorStore = vectorStore;
        this.topK = topK;
        this.order = order;
    }

    @Override
    public ChatClientRequest before(ChatClientRequest request, AdvisorChain chain) {
        String message = Objects.requireNonNullElse(request.prompt().getUserMessage().getText(), "");
        List<Document> examples = vectorStore.similaritySearch(
                SearchRequest.builder().query(message).topK(topK).build());
        if (examples.isEmpty()) {
            return request;
        }
        return request.mutate()
                .prompt(request.prompt().augmentUserMessage(augment(message, examples)))
                .context(RETRIEVED_EXAMPLES, examples)
                .build();
    }

    @Override
    public ChatClientResponse after(ChatClientResponse response, AdvisorChain chain) {
        return response;
    }

    @Override
    public int getOrder() {
        return order;
    }

    /** The exact text the model sees; static so it can be unit tested without a vector store. */
    static String augment(String message, List<Document> examples) {
        StringBuilder shown = new StringBuilder();
        for (Document doc : examples) {
            shown.append("- They said: ").append(doc.getText()).append('\n')
                    .append("  Yaswanth replied: ").append(doc.getMetadata().get("reply")).append('\n');
        }
        return TEMPLATE.formatted(message, shown.toString().stripTrailing());
    }
}
