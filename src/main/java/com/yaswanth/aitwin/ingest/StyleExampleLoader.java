package com.yaswanth.aitwin.ingest;

import tools.jackson.databind.json.JsonMapper;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.document.Document;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.io.Resource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/**
 * Ingestion step of the RAG pipeline, run once at startup when the vector store is empty.
 *
 * Chunking strategy: one chunk = one conversational exchange (what the other person said
 * + how Yaswanth replied). Chat messages are short, so splitting by token count would cut a
 * message away from its reply; the exchange is the natural unit of meaning.
 */
@Component
public class StyleExampleLoader implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(StyleExampleLoader.class);

    private final VectorStore vectorStore;
    private final JdbcTemplate jdbcTemplate;
    private final JsonMapper jsonMapper;
    private final Resource dataFile;

    public StyleExampleLoader(VectorStore vectorStore,
                              JdbcTemplate jdbcTemplate,
                              JsonMapper jsonMapper,
                              @Value("classpath:data.jsonl") Resource dataFile) {
        this.vectorStore = vectorStore;
        this.jdbcTemplate = jdbcTemplate;
        this.jsonMapper = jsonMapper;
        this.dataFile = dataFile;
    }

    @Override
    public void run(ApplicationArguments args) throws Exception {
        Integer existing = jdbcTemplate.queryForObject("SELECT count(*) FROM vector_store", Integer.class);
        if (existing != null && existing > 0) {
            log.info("Vector store already has {} style examples, skipping ingestion", existing);
            return;
        }
        // data.jsonl holds real chats, so it is git-ignored. A build from git has no file:
        // start anyway, chat still works, just without style examples.
        if (!dataFile.exists()) {
            log.warn("No data.jsonl on the classpath, starting without style examples");
            return;
        }

        List<Document> documents = new ArrayList<>();
        try (var reader = new BufferedReader(new InputStreamReader(dataFile.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.isBlank()) continue;
                var turn = jsonMapper.readValue(line, ChatTurn.class);
                documents.add(toDocument(turn));
            }
        }

        // One call: Spring AI batches the texts to the embeddings API and inserts rows into pgvector.
        // If OpenAI is unreachable, start anyway (chat still works, just without style examples);
        // ingestion retries on the next startup because the table is still empty.
        try {
            vectorStore.add(documents);
            log.info("Embedded and stored {} style examples", documents.size());
        } catch (RuntimeException e) {
            log.warn("Could not embed style examples, starting without them: {}", e.getMessage());
        }
    }

    private static Document toDocument(ChatTurn turn) {
        String theySaid = turn.context().stream()
                .map(ChatTurn.Message::text)
                .collect(Collectors.joining("\n"));
        String text = "They said: " + theySaid + "\nYaswanth replied: " + turn.response();
        return new Document(text, Map.of(
                "turnId", turn.turn_id(),
                "topic", turn.topic(),
                "type", turn.type()));
    }

    /** Shape of one line in data.jsonl. */
    record ChatTurn(String turn_id, String contact, String date, boolean session_break,
                    List<Message> context, String response, String type, String topic) {
        record Message(String sender, String text) {
        }
    }
}
