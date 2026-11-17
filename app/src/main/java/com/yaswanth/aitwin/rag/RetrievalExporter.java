package com.yaswanth.aitwin.rag;

import com.yaswanth.aitwin.TwinProperties;
import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.document.Document;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import tools.jackson.databind.json.JsonMapper;

/**
 * Evaluation only (ai-twin.eval.export-retrieval=true): sends every held-out test message
 * through the same pgvector search the app will use and writes the hits to
 * data/eval/retrieved_embedding.jsonl. pipeline/step7_retrieval_eval.py scores them against BM25.
 */
@Component
@Order(2)
public class RetrievalExporter implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(RetrievalExporter.class);

    /** The fields of data/test.jsonl this class needs; Jackson ignores the rest. */
    record TestExchange(String exchange_id, List<RagRecord.Turn> context, String reply, String topic) {

        String lastFriendMessage() {
            return context.stream().filter(t -> "friend".equals(t.sender()))
                    .reduce((first, second) -> second).orElseThrow().text();
        }
    }

    private final VectorStore vectorStore;
    private final JsonMapper json;
    private final TwinProperties props;

    public RetrievalExporter(VectorStore vectorStore, JsonMapper json, TwinProperties props) {
        this.vectorStore = vectorStore;
        this.json = json;
        this.props = props;
    }

    @Override
    public void run(ApplicationArguments args) throws Exception {
        if (!props.eval().exportRetrieval()) {
            return;
        }
        Path dataDir = props.rag().path();
        List<TestExchange> tests = Jsonl.read(dataDir.resolve("test.jsonl"), TestExchange.class, json);
        Path out = dataDir.resolve("eval").resolve("retrieved_embedding.jsonl");
        Files.createDirectories(out.getParent());

        try (BufferedWriter writer = Files.newBufferedWriter(out, StandardCharsets.UTF_8)) {
            for (TestExchange test : tests) {
                List<Document> docs = vectorStore.similaritySearch(SearchRequest.builder()
                        .query(test.lastFriendMessage())
                        .topK(props.eval().topK())
                        .build());
                List<Map<String, Object>> hits = docs.stream().map(d -> Map.<String, Object>of(
                        "exchange_id", d.getMetadata().get("exchangeId"),
                        "score", d.getScore(),
                        "topic", d.getMetadata().get("topic"),
                        "reply", d.getMetadata().get("reply"))).toList();
                writer.write(json.writeValueAsString(Map.of("exchange_id", test.exchange_id(), "hits", hits)));
                writer.newLine();
            }
        }
        log.info("Wrote retrieval results for {} test messages to {}", tests.size(), out);
    }
}
