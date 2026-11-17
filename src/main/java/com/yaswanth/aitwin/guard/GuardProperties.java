package com.yaswanth.aitwin.guard;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** Guardrail settings from application.yaml (ai-twin.guard.*). Set a limit to 0 to disable it. */
@ConfigurationProperties(prefix = "ai-twin.guard")
public record GuardProperties(
        String accessCode,
        int messagesPerMinute,
        int messagesPerDay,
        int newChatsPerHour,
        int globalMessagesPerDay) {
}
