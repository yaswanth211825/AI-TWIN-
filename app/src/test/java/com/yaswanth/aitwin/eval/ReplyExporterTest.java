package com.yaswanth.aitwin.eval;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.MessageType;

class ReplyExporterTest {

    @Test
    void mapsTurnsToRolesAndMergesDoubleTexts() {
        List<Message> messages = ReplyExporter.toMessages(List.of(
                new ReplyExporter.Turn("friend", "bro free aa?"),
                new ReplyExporter.Turn("me", "ha cheppu"),
                new ReplyExporter.Turn("friend", "TCS results vachaya?"),
                new ReplyExporter.Turn("friend", "cheppu ra")));

        assertThat(messages).extracting(Message::getMessageType)
                .containsExactly(MessageType.USER, MessageType.ASSISTANT, MessageType.USER);
        assertThat(messages.getLast().getText()).isEqualTo("TCS results vachaya?\ncheppu ra");
    }
}
