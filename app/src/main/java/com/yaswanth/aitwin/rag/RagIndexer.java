package com.yaswanth.aitwin.rag;

import com.yaswanth.aitwin.TwinProperties;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.document.Document;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.annotation.Order;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import tools.jackson.databind.json.JsonMapper;

/**
 * Keeps the pgvector table in sync with data/rag.jsonl at startup.
 *
 *   rag.jsonl ──▶ wanted ids ─┬─ not in table  ──▶ embed + insert   (only new records cost money)
 *                             └─ in table, gone from file ──▶ delete (e.g. later flagged private)
 *
 * Spring AI does the embedding: vectorStore.add() sends each Document's text to the
 * EmbeddingModel (OpenAI text-embedding-3-small) and stores the vector with its metadata.
 */
@Component
@Order(1)
public class RagIndexer implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(RagIndexer.class);
    private static final int BATCH = 500;

    private final VectorStore vectorStore;
    private final JdbcTemplate jdbc;
    private final JsonMapper json;
    private final TwinProperties props;
    private final String table;

    public RagIndexer(VectorStore vectorStore, JdbcTemplate jdbc, JsonMapper json, TwinProperties props,
                      @Value("${spring.ai.vectorstore.pgvector.table-name}") String table) {
        this.vectorStore = vectorStore;
        this.jdbc = jdbc;
        this.json = json;
        this.props = props;
        this.table = table;
    }

    @Override
    public void run(ApplicationArguments args) throws Exception {
        Path file = props.rag().path().resolve("rag.jsonl");
        if (!Files.exists(file)) {
            log.warn("{} not found; run the Python pipeline first. Starting with the existing index.", file);
            return;
        }

        Map<String, RagRecord> wanted = new LinkedHashMap<>();
        for (RagRecord record : Jsonl.read(file, RagRecord.class, json)) {
            wanted.put(record.documentId(), record);
        }
        // Table name comes from our own configuration, not from user input.
        Set<String> existing = new HashSet<>(jdbc.queryForList("SELECT id::text FROM " + table, String.class));

        List<String> stale = existing.stream().filter(id -> !wanted.containsKey(id)).toList();
        if (!stale.isEmpty()) {
            vectorStore.delete(stale);
        }

        List<Document> toAdd = wanted.entrySet().stream()
                .filter(e -> !existing.contains(e.getKey()))
                .map(e -> e.getValue().toDocument())
                .toList();
        for (int i = 0; i < toAdd.size(); i += BATCH) {
            vectorStore.add(toAdd.subList(i, Math.min(i + BATCH, toAdd.size())));
            log.info("Embedded {}/{}", Math.min(i + BATCH, toAdd.size()), toAdd.size());
        }

        log.info("RAG index in sync: {} records ({} added, {} removed, {} unchanged)",
                wanted.size(), toAdd.size(), stale.size(), wanted.size() - toAdd.size());
    }
}
