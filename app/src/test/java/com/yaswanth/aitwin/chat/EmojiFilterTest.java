package com.yaswanth.aitwin.chat;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class EmojiFilterTest {

    @Test
    void removesAllEmojiWhenNotKeeping() {
        assertThat(EmojiFilter.forReply(false).filter("ha vachayi 😎 super 🔥🔥")).isEqualTo("ha vachayi super ");
    }

    @Test
    void keepsOnlyTheFirstEmojiAcrossChunks() {
        EmojiFilter filter = EmojiFilter.forReply(true);
        assertThat(filter.filter("ha 😂")).isEqualTo("ha 😂");
        assertThat(filter.filter(" chudu 😭🙏")).isEqualTo(" chudu ");
    }

    @Test
    void removesJoinersAndKeepsLineBreaks() {
        assertThat(EmojiFilter.forReply(false).filter("ok 👍🏻\nbye ❤️")).isEqualTo("ok\nbye ");
    }

    @Test
    void sameMessageSameDecision() {
        assertThat(EmojiFilter.shouldKeep("bro free aa?", 0.3)).isEqualTo(EmojiFilter.shouldKeep("bro free aa?", 0.3));
        assertThat(EmojiFilter.shouldKeep("anything", 0.0)).isFalse();
        assertThat(EmojiFilter.shouldKeep("anything", 1.0)).isTrue();
    }

    @Test
    void keepRateIsRoughlyRespected() {
        long kept = java.util.stream.IntStream.range(0, 10_000)
                .filter(i -> EmojiFilter.shouldKeep("message " + i, 0.3)).count();
        assertThat(kept).isBetween(2_500L, 3_500L);
    }
}
