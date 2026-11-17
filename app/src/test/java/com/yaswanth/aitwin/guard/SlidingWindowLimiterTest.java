package com.yaswanth.aitwin.guard;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import org.junit.jupiter.api.Test;

class SlidingWindowLimiterTest {

    /** A clock the test can move forward, so no real waiting. */
    static final class TestClock extends Clock {
        Instant now = Instant.parse("2026-11-17T10:00:00Z");

        @Override public ZoneOffset getZone() { return ZoneOffset.UTC; }
        @Override public Clock withZone(java.time.ZoneId zone) { return this; }
        @Override public Instant instant() { return now; }
    }

    @Test
    void allowsUpToLimitThenBlocks() {
        var limiter = new SlidingWindowLimiter(Duration.ofMinutes(1), new TestClock());
        assertThat(limiter.tryAcquire("ip", 3)).isTrue();
        assertThat(limiter.tryAcquire("ip", 3)).isTrue();
        assertThat(limiter.tryAcquire("ip", 3)).isTrue();
        assertThat(limiter.tryAcquire("ip", 3)).isFalse();
        assertThat(limiter.tryAcquire("other-ip", 3)).isTrue();
    }

    @Test
    void windowSlides() {
        var clock = new TestClock();
        var limiter = new SlidingWindowLimiter(Duration.ofMinutes(1), clock);
        limiter.tryAcquire("ip", 1);
        assertThat(limiter.tryAcquire("ip", 1)).isFalse();
        clock.now = clock.now.plusSeconds(61);
        assertThat(limiter.tryAcquire("ip", 1)).isTrue();
    }

    @Test
    void zeroMeansNoLimit() {
        var limiter = new SlidingWindowLimiter(Duration.ofMinutes(1), new TestClock());
        for (int i = 0; i < 100; i++) {
            assertThat(limiter.tryAcquire("ip", 0)).isTrue();
        }
    }
}
