package com.yaswanth.aitwin.guard;

import java.time.Duration;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * In-memory sliding-window rate limiter: allows at most `limit` events per key within `window`.
 * Each key keeps the timestamps of its recent events; old ones are dropped on every check.
 *
 * Limits reset when the app restarts, and each app instance counts separately. That is fine
 * for a single instance; with several instances the counters would move to Redis.
 */
class SlidingWindowLimiter {

    private static final int MAX_KEYS = 50_000;

    private final long windowMillis;
    private final Map<String, Deque<Long>> events = new ConcurrentHashMap<>();

    SlidingWindowLimiter(Duration window) {
        this.windowMillis = window.toMillis();
    }

    boolean tryAcquire(String key, int limit) {
        if (limit <= 0) {
            return true; // 0 or negative = limit disabled
        }
        long now = System.currentTimeMillis();
        if (events.size() > MAX_KEYS) {
            events.values().removeIf(q -> {
                synchronized (q) {
                    return q.isEmpty() || q.peekLast() < now - windowMillis;
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
