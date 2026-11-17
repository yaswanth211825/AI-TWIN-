package com.yaswanth.aitwin.rag;

import static java.nio.charset.StandardCharsets.UTF_8;
import static java.util.stream.Collectors.joining;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.ai.document.Document;

/**
 * One line of data/rag.jsonl (written by pipeline/step4_split.py).
 * Field names match the JSON keys, so Jackson maps them without annotations.
 *
 * @param id         stable exchange id from the pipeline (hash of your reply)
 * @param embed_text the friend's last message: the only text that gets embedded
 * @param context    up to 3 turns before your reply
 * @param reply      your real reply, shown to the model as a style example
 */
public record RagRecord(String id, String embed_text, List<Turn> context, String reply,
                        String topic, String type, String date, int session_id) {

    public record Turn(String sender, String text) {
    }

    /** Same exchange gives the same UUID on every run, so re-indexing updates instead of duplicating. */
    public String documentId() {
        return UUID.nameUUIDFromBytes(id.getBytes(UTF_8)).toString();
    }

    /**
     * Spring AI Document: the text is what gets embedded and searched (the friend's message);
     * everything needed to build a style example travels in the metadata.
     */
    public Document toDocument() {
        String contextText = context.stream()
                .map(t -> ("me".equals(t.sender()) ? "Yaswanth" : "Friend") + ": " + t.text())
                .collect(joining("\n"));
        return new Document(documentId(), embed_text, Map.of(
                "exchangeId", id,
                "reply", reply,
                "context", contextText,
                "topic", topic,
                "type", type,
                "date", date,
                "sessionId", session_id));
    }
}
