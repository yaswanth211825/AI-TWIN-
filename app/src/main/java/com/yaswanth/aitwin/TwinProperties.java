package com.yaswanth.aitwin;

import java.nio.file.Path;
import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Typed view of the "ai-twin.*" block in application.yaml.
 * Spring binds the YAML into these records at startup, so the code never reads raw strings.
 */
@ConfigurationProperties(prefix = "ai-twin")
public record TwinProperties(Rag rag, Chat chat, Eval eval) {

    /**
     * dataDir: folder with rag.jsonl and test.jsonl from the Python pipeline.
     * Bound as text: in a web app Spring would try to read "../data" as a servlet resource.
     */
    public record Rag(String dataDir) {

        public Path path() {
            return Path.of(dataDir).toAbsolutePath().normalize();
        }
    }

    /**
     * partner: who the twin is talking to (goes into the system prompt).
     * memoryWindow: how many past messages of this chat the model sees.
     * topK: style examples retrieved per message.
     * emojiKeepRate: share of emoji-containing replies that keep (one) emoji.
     */
    public record Chat(String partner, int memoryWindow, int topK, double emojiKeepRate) {
    }

    /** exportRetrieval: search every test message and write the hits for evaluation. */
    public record Eval(boolean exportRetrieval, int topK) {
    }
}
