package com.yaswanth.aitwin.chat;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.ai.document.Document;

class StyleExamplesAdvisorTest {

    @Test
    void showsTheFriendsMessageAndYourReplyFromMetadata() {
        List<Document> examples = List.of(
                new Document("TCS results vachaya?", Map.of("reply", "ha vachayi\ndigital")),
                new Document("java or python?", Map.of("reply", "java, DSA ki best")));

        String text = StyleExamplesAdvisor.augment("results eppudu?", examples);

        assertThat(text).startsWith("results eppudu?\n\n(Style reference")
                .contains("- They said: TCS results vachaya?\n  Yaswanth replied: ha vachayi\ndigital")
                .contains("- They said: java or python?\n  Yaswanth replied: java, DSA ki best")
                .endsWith("Reply to the message above.)");
    }
}
