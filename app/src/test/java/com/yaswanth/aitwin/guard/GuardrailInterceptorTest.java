package com.yaswanth.aitwin.guard;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import tools.jackson.databind.json.JsonMapper;

class GuardrailInterceptorTest {

    private static MockHttpServletRequest request(String method, String uri) {
        var r = new MockHttpServletRequest(method, uri);
        r.setRemoteAddr("10.0.0.1");
        return r;
    }

    private static GuardrailInterceptor guard(String code, int perMinute, int global) {
        return new GuardrailInterceptor(new GuardProperties(code, perMinute, 1000, 1000, global, 0), JsonMapper.builder().build());
    }

    @Test
    void accessCodeRequiredWhenSet() throws Exception {
        var guard = guard("secret", 0, 0);
        var noCode = new MockHttpServletResponse();
        assertThat(guard.preHandle(request("GET", "/api/conversations"), noCode, null)).isFalse();
        assertThat(noCode.getStatus()).isEqualTo(401);
        assertThat(noCode.getContentAsString()).contains("access_code");

        var withCode = request("GET", "/api/conversations");
        withCode.addHeader(GuardrailInterceptor.ACCESS_HEADER, "secret");
        assertThat(guard.preHandle(withCode, new MockHttpServletResponse(), null)).isTrue();
    }

    @Test
    void perMinuteLimitReturns429WithRetryAfter() throws Exception {
        var guard = guard("", 2, 0);
        String uri = "/api/conversations/abc/messages";
        assertThat(guard.preHandle(request("POST", uri), new MockHttpServletResponse(), null)).isTrue();
        assertThat(guard.preHandle(request("POST", uri), new MockHttpServletResponse(), null)).isTrue();
        var third = new MockHttpServletResponse();
        assertThat(guard.preHandle(request("POST", uri), third, null)).isFalse();
        assertThat(third.getStatus()).isEqualTo(429);
        assertThat(third.getHeader("Retry-After")).isEqualTo("60");
    }

    @Test
    void globalCapReturns503() throws Exception {
        var guard = guard("", 0, 1);
        String uri = "/api/conversations/abc/messages";
        assertThat(guard.preHandle(request("POST", uri), new MockHttpServletResponse(), null)).isTrue();
        var second = new MockHttpServletResponse();
        assertThat(guard.preHandle(request("POST", uri), second, null)).isFalse();
        assertThat(second.getStatus()).isEqualTo(503);
    }

    @Test
    void readsAreNotRateLimited() throws Exception {
        var guard = guard("", 1, 1);
        for (int i = 0; i < 5; i++) {
            assertThat(guard.preHandle(request("GET", "/api/conversations"), new MockHttpServletResponse(), null)).isTrue();
        }
    }

    @Test
    void clientIpIgnoresSpoofedEntries() {
        var r = request("POST", "/x");
        r.addHeader("X-Forwarded-For", "6.6.6.6, 203.0.113.7");   // client typed 6.6.6.6; our proxy added 203.0.113.7
        assertThat(ClientIp.resolve(r, 1)).isEqualTo("203.0.113.7");
        assertThat(ClientIp.resolve(r, 0)).isEqualTo("10.0.0.1");      // no proxy: header not trusted at all
    }
}
