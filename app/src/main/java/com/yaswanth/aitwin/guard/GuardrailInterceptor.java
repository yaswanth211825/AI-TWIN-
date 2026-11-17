package com.yaswanth.aitwin.guard;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;
import tools.jackson.databind.json.JsonMapper;

/**
 * Runs before every /api/conversations request and protects the OpenAI bill and the demo:
 *
 *   1. Access code     optional shared password (header X-Access-Code)               → 401
 *   2. Per-IP limits   messages per minute and per day, new chats per hour            → 429
 *   3. Global cap      messages per day for everyone combined (the cost kill switch)  → 503
 *
 * Reads (GET) are cheap and only need the access code. Only POSTs cost money or storage.
 */
@Component
public class GuardrailInterceptor implements HandlerInterceptor {

    static final String ACCESS_HEADER = "X-Access-Code";

    private final GuardProperties props;
    private final JsonMapper json;
    private final SlidingWindowLimiter perMinute = new SlidingWindowLimiter(Duration.ofMinutes(1));
    private final SlidingWindowLimiter perDay = new SlidingWindowLimiter(Duration.ofDays(1));
    private final SlidingWindowLimiter newChats = new SlidingWindowLimiter(Duration.ofHours(1));
    private final SlidingWindowLimiter global = new SlidingWindowLimiter(Duration.ofDays(1));

    public GuardrailInterceptor(GuardProperties props, JsonMapper json) {
        this.props = props;
        this.json = json;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        if (!accessCodeOk(request)) {
            return reject(response, HttpStatus.UNAUTHORIZED, "access_code", "Access code required.", null);
        }
        if (!"POST".equals(request.getMethod())) {
            return true;
        }
        String ip = ClientIp.resolve(request, props.trustedProxyHops());
        if (request.getRequestURI().endsWith("/messages")) {
            if (!perMinute.tryAcquire(ip, props.messagesPerMinute())) {
                return reject(response, HttpStatus.TOO_MANY_REQUESTS, "rate_limit", "Slow down a little, try again in a minute.", 60);
            }
            if (!perDay.tryAcquire(ip, props.messagesPerDay())) {
                return reject(response, HttpStatus.TOO_MANY_REQUESTS, "daily_limit", "You've reached today's message limit.", 3600);
            }
            if (!global.tryAcquire("everyone", props.globalMessagesPerDay())) {
                return reject(response, HttpStatus.SERVICE_UNAVAILABLE, "global_limit", "The twin is resting for today. Try again tomorrow.", 3600);
            }
        } else if (!newChats.tryAcquire(ip, props.newChatsPerHour())) {
            return reject(response, HttpStatus.TOO_MANY_REQUESTS, "chat_limit", "Too many new chats, try again later.", 600);
        }
        return true;
    }

    private boolean accessCodeOk(HttpServletRequest request) {
        String expected = props.accessCode();
        if (expected == null || expected.isBlank()) {
            return true;
        }
        String given = request.getHeader(ACCESS_HEADER);
        // Constant-time comparison: the response time does not reveal how many characters matched.
        return given != null && MessageDigest.isEqual(
                expected.getBytes(StandardCharsets.UTF_8), given.getBytes(StandardCharsets.UTF_8));
    }

    private boolean reject(HttpServletResponse response, HttpStatus status, String code, String message,
                           Integer retryAfterSeconds) throws Exception {
        response.setStatus(status.value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        if (retryAfterSeconds != null) {
            response.setHeader("Retry-After", retryAfterSeconds.toString());
        }
        response.getWriter().write(json.writeValueAsString(Map.of("code", code, "message", message)));
        return false;
    }
}
