package com.yaswanth.aitwin.chat;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class ChatServiceTest {

    @Test
    void shortTitleKeptAsOneLine() {
        assertThat(ChatService.titleFrom("  bro\n free   aa? ")).isEqualTo("bro free aa?");
    }

    @Test
    void longTitleCutWithEllipsis() {
        String title = ChatService.titleFrom("a".repeat(100));
        assertThat(title).hasSize(40).endsWith("…");
    }
}
