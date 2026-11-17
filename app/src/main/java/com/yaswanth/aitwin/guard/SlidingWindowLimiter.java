package com.yaswanth.aitwin.guard;

import java.time.Clock;
import java.time.Duration;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Sliding-window rate limiter: at most `limit` events per key within `window`.
 * Each key keeps the timestamps of its recent events; expired ones are dropped on every check.
 *
 * In memory: limits reset on restart and each instance counts on its own. Fine for one instance;
 * with several instances the counters would move to Redis.
 */
class SlidingWindowLimiter {

    private static final int MAX_KEYS = 50_000;   // stops a flood of new IPs from filling memory

    private final long windowMillis;
    private final Clock clock;
    private final Map<String, Deque<Long>> events = new ConcurrentHashMap<>();

    SlidingWindowLimiter(Duration window) {
        this(window, Clock.systemUTC());
    }

    SlidingWindowLimiter(Duration window, Clock clock) {
        this.windowMillis = window.toMillis();
        this.clock = clock;
    }

    /** Records an event and returns true if it is within the limit; false (and not recorded) if over. */
    boolean tryAcquire(String key, int limit) {
        if (limit <= 0) {
            return true;
        }
        long now = clock.millis();
        if (events.size() > MAX_KEYS) {
            events.values().removeIf(q -> {
                synchronized (q) {
                    return q.isEmpty() || q.peekLast() <= now - windowMillis;
                }
            });
        }
        Deque<Long> queue = events.computeIfAbsent(key, k -> new ArrayDeque<>());
        synchronized (queue) {
            while (!queue.isEmpty() && queue.peekFirst() <= now - windowMillis) {
                queue.pollFirst();
            }
            if (queue.size() >= limit) {
                return false;
            }
            queue.addLast(now);
            return true;
        }
    }
}
