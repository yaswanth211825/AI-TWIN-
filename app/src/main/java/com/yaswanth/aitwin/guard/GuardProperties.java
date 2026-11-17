package com.yaswanth.aitwin.guard;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Guardrail settings (ai-twin.guard.*). A limit of 0 disables it.
 *
 * @param accessCode           shared password for the demo; empty = open to anyone with the link
 * @param messagesPerMinute    per client IP
 * @param messagesPerDay       per client IP
 * @param newChatsPerHour      per client IP
 * @param globalMessagesPerDay everyone combined: the hard ceiling on the OpenAI bill
 * @param trustedProxyHops     proxies in front of the app that append to X-Forwarded-For (Render: 1, local: 0)
 */
@ConfigurationProperties(prefix = "ai-twin.guard")
public record GuardProperties(String accessCode, int messagesPerMinute, int messagesPerDay,
                              int newChatsPerHour, int globalMessagesPerDay, int trustedProxyHops) {
}
