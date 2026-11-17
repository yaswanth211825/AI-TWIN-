package com.yaswanth.aitwin.chat;

import jakarta.validation.Valid;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ProblemDetail;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;

/**
 * Chat REST API. Any client (web page, Telegram bot, WhatsApp adapter) only needs these endpoints.
 * X-Client-Id identifies the browser or device that owns the chats.
 *
 *   POST   /api/conversations                 new chat
 *   GET    /api/conversations                 this client's chats, newest first
 *   GET    /api/conversations/{id}/messages   history
 *   POST   /api/conversations/{id}/messages   send {"text": ...}; reply streams as Server-Sent Events
 *   DELETE /api/conversations/{id}            delete chat and its memory
 */
@RestController
@RequestMapping("/api/conversations")
public class ChatController {

    private static final Logger log = LoggerFactory.getLogger(ChatController.class);
    private static final String CLIENT_HEADER = "X-Client-Id";

    private final ChatService chatService;

    public ChatController(ChatService chatService) {
        this.chatService = chatService;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Conversation create(@RequestHeader(CLIENT_HEADER) UUID clientId) {
        return chatService.create(clientId);
    }

    @GetMapping
    public List<Conversation> list(@RequestHeader(CLIENT_HEADER) UUID clientId) {
        return chatService.list(clientId);
    }

    @GetMapping("/{id}/messages")
    public List<ChatMessage> history(@PathVariable UUID id, @RequestHeader(CLIENT_HEADER) UUID clientId) {
        return chatService.history(id, clientId);
    }

    /** Server-Sent Events: one "token" event per chunk, then "done" (or "error"). */
    @PostMapping(value = "/{id}/messages", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<ServerSentEvent<Map<String, String>>> send(@PathVariable UUID id,
                                                           @RequestHeader(CLIENT_HEADER) UUID clientId,
                                                           @Valid @RequestBody SendMessageRequest request) {
        return chatService.send(id, clientId, request.text())
                .filter(chunk -> !chunk.isEmpty())
                .map(chunk -> ServerSentEvent.builder(Map.of("text", chunk)).event("token").build())
                .concatWith(Flux.just(ServerSentEvent.builder(Map.<String, String>of()).event("done").build()))
                .doOnError(error -> log.error("Reply failed for conversation {}", id, error))
                .onErrorResume(error -> Flux.just(ServerSentEvent
                        .builder(Map.of("message", "Reply failed, please try again."))
                        .event("error").build()));
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable UUID id, @RequestHeader(CLIENT_HEADER) UUID clientId) {
        chatService.delete(id, clientId);
    }

    @ExceptionHandler(ConversationNotFoundException.class)
    ProblemDetail notFound(ConversationNotFoundException e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, e.getMessage());
    }
}
