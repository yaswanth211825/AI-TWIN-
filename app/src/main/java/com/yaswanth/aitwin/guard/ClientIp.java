package com.yaswanth.aitwin.guard;

import jakarta.servlet.http.HttpServletRequest;

/**
 * Finds the real client IP for rate limiting.
 *
 * X-Forwarded-For is "client, proxy1, proxy2": each proxy APPENDS the address it received the
 * request from. Anything to the left can be typed by the client, so taking the first entry (as
 * AI Twin 4 did) lets a script send a fake IP each time and dodge per-IP limits. We trust only
 * the entries added by our own proxies: with N trusted proxies, the client is the N-th from the end.
 */
final class ClientIp {

    private ClientIp() {
    }

    static String resolve(HttpServletRequest request, int trustedProxyHops) {
        String forwarded = request.getHeader("X-Forwarded-For");
        if (trustedProxyHops <= 0 || forwarded == null || forwarded.isBlank()) {
            return request.getRemoteAddr();
        }
        String[] hops = forwarded.split(",");
        int index = hops.length - trustedProxyHops;
        return index >= 0 ? hops[index].trim() : request.getRemoteAddr();
    }
}
