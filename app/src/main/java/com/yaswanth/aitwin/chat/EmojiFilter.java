package com.yaswanth.aitwin.chat;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Keeps the twin's emoji use close to yours.
 *
 * Measured (step 6): you put an emoji in ~10% of replies; gpt-6-luna does in ~35% even when the
 * prompt says not to. So: for a share of replies (emojiKeepRate) the first emoji is kept, every
 * other emoji is removed. Works on streamed chunks, so it keeps state for one reply.
 */
public final class EmojiFilter {

    // Same ranges as pipeline/metrics.py, so the app removes exactly what the evaluation counts.
    private static final Pattern EMOJI = Pattern.compile("[\\x{1F300}-\\x{1FAFF}\\x{2600}-\\x{27BF}]");
    // Invisible helpers that glue emoji together (variation selector, zero-width joiner).
    private static final Pattern JOINERS = Pattern.compile("[\\x{FE0F}\\x{200D}]");

    private final boolean keepOne;
    private boolean kept;

    private EmojiFilter(boolean keepOne) {
        this.keepOne = keepOne;
    }

    /** One filter per reply. keepOne: whether this reply may keep its first emoji. */
    public static EmojiFilter forReply(boolean keepOne) {
        return new EmojiFilter(keepOne);
    }

    /**
     * Same decision for the same message every time (no randomness in tests or retries):
     * a stable hash of the seed picks a number 0..99, kept if below rate * 100.
     */
    public static boolean shouldKeep(String seed, double rate) {
        return Math.floorMod(seed.hashCode(), 100) < Math.round(rate * 100);
    }

    /** Filters the next chunk of the reply. */
    public String filter(String chunk) {
        if (chunk == null || chunk.isEmpty()) {
            return chunk;
        }
        Matcher m = EMOJI.matcher(chunk);
        StringBuilder out = new StringBuilder();
        while (m.find()) {
            String replacement = (keepOne && !kept) ? m.group() : "";
            if (!replacement.isEmpty()) {
                kept = true;
            }
            m.appendReplacement(out, Matcher.quoteReplacement(replacement));
        }
        m.appendTail(out);
        return JOINERS.matcher(out).replaceAll("").replaceAll("[ \\t]+\\n", "\n").replaceAll(" {2,}", " ");
    }
}
