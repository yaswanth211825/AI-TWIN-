package com.yaswanth.aitwin.chat;

import java.util.Objects;
import java.util.function.UnaryOperator;
import org.springframework.ai.chat.client.ChatClientRequest;
import org.springframework.ai.chat.client.ChatClientResponse;
import org.springframework.ai.chat.client.advisor.api.CallAdvisor;
import org.springframework.ai.chat.client.advisor.api.CallAdvisorChain;
import org.springframework.ai.chat.client.advisor.api.StreamAdvisor;
import org.springframework.ai.chat.client.advisor.api.StreamAdvisorChain;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.model.Generation;
import reactor.core.publisher.Flux;

/**
 * Applies EmojiFilter to the model's reply, chunk by chunk.
 *
 * Sits between the memory advisor and the model (order between them), so memory saves the
 * FILTERED reply. Otherwise the model would see its own emoji-heavy history and drift back.
 */
public class EmojiFilterAdvisor implements CallAdvisor, StreamAdvisor {

    private final double keepRate;
    private final int order;

    public EmojiFilterAdvisor(double keepRate, int order) {
        this.keepRate = keepRate;
        this.order = order;
    }

    @Override
    public ChatClientResponse adviseCall(ChatClientRequest request, CallAdvisorChain chain) {
        EmojiFilter filter = EmojiFilter.forReply(keep(request));
        return rewrite(chain.nextCall(request), filter::filter);
    }

    @Override
    public Flux<ChatClientResponse> adviseStream(ChatClientRequest request, StreamAdvisorChain chain) {
        EmojiFilter filter = EmojiFilter.forReply(keep(request));
        return chain.nextStream(request).map(response -> rewrite(response, filter::filter));
    }

    private boolean keep(ChatClientRequest request) {
        String seed = Objects.requireNonNullElse(request.prompt().getUserMessage().getText(), "");
        return EmojiFilter.shouldKeep(seed, keepRate);
    }

    /** Rebuilds the response with filtered text; metadata (finish reason, usage) is kept. */
    private static ChatClientResponse rewrite(ChatClientResponse response, UnaryOperator<String> filter) {
        ChatResponse chat = response.chatResponse();
        if (chat == null) {
            return response;
        }
        var generations = chat.getResults().stream()
                .map(g -> new Generation(
                        g.getOutput().mutate().content(filter.apply(g.getOutput().getText())).build(),
                        g.getMetadata()))
                .toList();
        return new ChatClientResponse(new ChatResponse(generations, chat.getMetadata()), response.context());
    }

    @Override
    public String getName() {
        return "EmojiFilterAdvisor";
    }

    @Override
    public int getOrder() {
        return order;
    }
}
