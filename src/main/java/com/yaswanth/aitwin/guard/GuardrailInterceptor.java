package com.yaswanth.aitwin.guard;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * Runs before every /api/conversations request. Protects the OpenAI bill and the demo:
 * 1. Access code      - optional shared password (APP_ACCESS_CODE). Unset = open.
 * 2. Per-IP limits     - messages per minute, messages per day, new chats per hour.
 * 3. Global daily cap  - hard ceiling on messages per day across everyone (cost kill switch).
 */
@Component
public class GuardrailInterceptor implements HandlerInterceptor {

    private static final String ACCESS_HEADER = "X-Access-Code";

    private final GuardProperties props;
    private final SlidingWindowLimiter perMinute = new SlidingWindowLimiter(Duration.ofMinutes(1));
    private final SlidingWindowLimiter perDay = new SlidingWindowLimiter(Duration.ofDays(1));
    private final SlidingWindowLimiter newChats = new SlidingWindowLimiter(Duration.ofHours(1));
    private final SlidingWindowLimiter global = new SlidingWindowLimiter(Duration.ofDays(1));

    public GuardrailInterceptor(GuardProperties props) {
        this.props = props;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        if (!accessCodeOk(request)) {
            return reject(response, HttpStatus.UNAUTHORIZED, "access_code", "Access code required.");
        }
        if (!"POST".equals(request.getMethod())) {
            return true; // reading chats is cheap; only POSTs cost money or storage
        }

        String ip = clientIp(request);
        boolean isMessage = request.getRequestURI().endsWith("/messages");

        if (isMessage) {
            if (!perMinute.tryAcquire(ip, props.messagesPerMinute())) {
                return reject(response, HttpStatus.TOO_MANY_REQUESTS, "rate_limit", "Slow down a little, try again in a minute.");
            }
            if (!perDay.tryAcquire(ip, props.messagesPerDay())) {
                return reject(response, HttpStatus.TOO_MANY_REQUESTS, "daily_limit", "You've reached today's message limit.");
            }
            if (!global.tryAcquire("all", props.globalMessagesPerDay())) {
                return reject(response, HttpStatus.SERVICE_UNAVAILABLE, "global_limit", "The twin is resting for today. Try again tomorrow.");
            }
        } else if (!newChats.tryAcquire(ip, props.newChatsPerHour())) {
            return reject(response, HttpStatus.TOO_MANY_REQUESTS, "chat_limit", "Too many new chats, try again later.");
        }
        return true;
    }

    private boolean accessCodeOk(HttpServletRequest request) {
        String expected = props.accessCode();
        if (expected == null || expected.isBlank()) {
            return true;
        }
        String given = request.getHeader(ACCESS_HEADER);
        // Constant-time comparison so the code can't be guessed by timing responses.
        return given != null && MessageDigest.isEqual(
                expected.getBytes(StandardCharsets.UTF_8), given.getBytes(StandardCharsets.UTF_8));
    }

    /** Behind Render's proxy the real client IP is the first entry of X-Forwarded-For. */
    private static String clientIp(HttpServletRequest request) {
        String forwarded = request.getHeader("X-Forwarded-For");
        if (forwarded != null && !forwarded.isBlank()) {
            return forwarded.split(",")[0].trim();
        }
        return request.getRemoteAddr();
    }

    private static boolean reject(HttpServletResponse response, HttpStatus status, String code, String message) throws Exception {
        response.setStatus(status.value());
        response.setContentType("application/json");
        if (status == HttpStatus.TOO_MANY_REQUESTS) {
            response.setHeader("Retry-After", "60");
        }
        response.getWriter().write("{\"code\":\"" + code + "\",\"message\":\"" + message + "\"}");
        return false;
    }
}
