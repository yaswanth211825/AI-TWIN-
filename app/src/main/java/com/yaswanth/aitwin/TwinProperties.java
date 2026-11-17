package com.yaswanth.aitwin;

import java.nio.file.Path;
import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Typed view of the "ai-twin.*" block in application.yaml.
 * Spring binds the YAML into these records at startup, so the code never reads raw strings.
 */
@ConfigurationProperties(prefix = "ai-twin")
public record TwinProperties(Rag rag, Eval eval) {

    /** dataDir: folder with rag.jsonl and test.jsonl from the Python pipeline. */
    public record Rag(Path dataDir) {
    }

    /** exportRetrieval: search every test message and write the hits for evaluation. */
    public record Eval(boolean exportRetrieval, int topK) {
    }
}
