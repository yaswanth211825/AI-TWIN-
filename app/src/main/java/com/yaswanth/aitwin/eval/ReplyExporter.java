package com.yaswanth.aitwin.eval;

import com.yaswanth.aitwin.TwinProperties;
import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import tools.jackson.databind.json.JsonMapper;

/**
 * Step 9 only (ai-twin.eval.export-replies=true): answers every held-out test message with the
 * REAL chat pipeline (persona, emoji filter, pgvector style examples, gpt-6-luna) and writes
 * data/eval/replies_app@MODEL.jsonl, which pipeline/step5_baseline.py scores like any other system.
 *
 * The test conversation is passed in as messages (friend = user, you = assistant) instead of
 * chat memory, so nothing is written to the chat tables. Re-running resumes where it stopped.
 */
@Component
@Order(3)
public class ReplyExporter implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(ReplyExporter.class);

    record Turn(String sender, String text) {
    }

    record TestExchange(String exchange_id, List<Turn> context) {
    }

    private final ChatClient evalChatClient;
    private final JsonMapper json;
    private final TwinProperties props;
    private final String model;

    public ReplyExporter(@Qualifier("evalChatClient") ChatClient evalChatClient, JsonMapper json,
                         TwinProperties props, @Value("${spring.ai.openai.chat.options.model}") String model) {
        this.evalChatClient = evalChatClient;
        this.json = json;
        this.props = props;
        this.model = model;
    }

    @Override
    public void run(ApplicationArguments args) throws Exception {
        if (!props.eval().exportReplies()) {
            return;
        }
        Path dataDir = props.rag().path();
        List<TestExchange> tests = new ArrayList<>();
        try (var lines = Files.lines(dataDir.resolve("test.jsonl"), StandardCharsets.UTF_8)) {
            lines.filter(l -> !l.isBlank()).forEach(l -> tests.add(json.readValue(l, TestExchange.class)));
        }
        List<TestExchange> todo = props.eval().limit() > 0 ? tests.subList(0, Math.min(props.eval().limit(), tests.size())) : tests;

        Path out = dataDir.resolve("eval").resolve("replies_app@" + model + ".jsonl");
        Files.createDirectories(out.getParent());
        Set<String> done = new HashSet<>();
        if (Files.exists(out)) {
            try (var lines = Files.lines(out, StandardCharsets.UTF_8)) {
                lines.filter(l -> !l.isBlank()).forEach(l -> done.add((String) json.readValue(l, Map.class).get("exchange_id")));
            }
        }

        int written = 0;
        try (BufferedWriter writer = Files.newBufferedWriter(out, StandardCharsets.UTF_8,
                StandardOpenOption.CREATE, StandardOpenOption.APPEND)) {
            for (TestExchange test : todo) {
                if (done.contains(test.exchange_id())) {
                    continue;
                }
                List<Message> history = toMessages(test.context());
                Message last = history.removeLast();   // the friend's latest message
                String reply = evalChatClient.prompt().messages(history).user(last.getText()).call().content();
                writer.write(json.writeValueAsString(Map.of("exchange_id", test.exchange_id(), "reply", reply == null ? "" : reply)));
                writer.newLine();
                writer.flush();
                written++;
            }
        }
        log.info("Wrote {} new replies ({} already done) to {}", written, done.size(), out);
    }

    /** Friend turns become user messages, your turns assistant messages; back-to-back turns are merged. */
    static List<Message> toMessages(List<Turn> context) {
        List<Message> messages = new ArrayList<>();
        String sender = null;
        StringBuilder text = new StringBuilder();
        for (Turn turn : context) {
            if (turn.sender().equals(sender)) {
                text.append('\n').append(turn.text());
                continue;
            }
            if (sender != null) {
                messages.add(toMessage(sender, text.toString()));
            }
            sender = turn.sender();
            text = new StringBuilder(turn.text());
        }
        if (sender != null) {
            messages.add(toMessage(sender, text.toString()));
        }
        return messages;
    }

    private static Message toMessage(String sender, String text) {
        return "me".equals(sender) ? new AssistantMessage(text) : new UserMessage(text);
    }
}
