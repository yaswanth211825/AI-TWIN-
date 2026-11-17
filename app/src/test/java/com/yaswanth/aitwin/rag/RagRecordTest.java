package com.yaswanth.aitwin.rag;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.ai.document.Document;

/** Plain unit test: no Spring context, no database, no API calls. Uses made-up text. */
class RagRecordTest {

    private final RagRecord record = new RagRecord(
            "abc123", "TCS results vachaya?",
            List.of(new RagRecord.Turn("friend", "bro free aa?"),
                    new RagRecord.Turn("me", "ha cheppu"),
                    new RagRecord.Turn("friend", "TCS results vachaya?")),
            "ha vachayi\ndigital lo select ayya", "career", "answer", "2026-03-14", 7);

    @Test
    void embedsOnlyTheFriendsMessage() {
        assertThat(record.toDocument().getText()).isEqualTo("TCS results vachaya?");
    }

    @Test
    void keepsReplyAndContextInMetadata() {
        Document doc = record.toDocument();
        assertThat(doc.getMetadata())
                .containsEntry("reply", "ha vachayi\ndigital lo select ayya")
                .containsEntry("topic", "career")
                .containsEntry("exchangeId", "abc123");
        assertThat((String) doc.getMetadata().get("context"))
                .isEqualTo("Friend: bro free aa?\nYaswanth: ha cheppu\nFriend: TCS results vachaya?");
    }

    @Test
    void sameExchangeAlwaysGetsTheSameId() {
        assertThat(record.documentId()).isEqualTo(record.documentId()).hasSize(36);
        assertThat(record.toDocument().getId()).isEqualTo(record.documentId());
    }
}
