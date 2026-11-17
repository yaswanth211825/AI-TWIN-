package com.yaswanth.aitwin.guard;

import java.util.Map;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/** Puts the guardrails in front of the chat API and adds a health check. */
@Configuration
@EnableConfigurationProperties(GuardProperties.class)
public class WebConfig implements WebMvcConfigurer {

    private final GuardrailInterceptor guardrailInterceptor;

    public WebConfig(GuardrailInterceptor guardrailInterceptor) {
        this.guardrailInterceptor = guardrailInterceptor;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(guardrailInterceptor)
                .addPathPatterns("/api/conversations", "/api/conversations/**");
    }

    /** For the hosting platform's health check. Not guarded; touches no database and no OpenAI. */
    @RestController
    static class HealthController {

        @GetMapping("/api/health")
        Map<String, String> health() {
            return Map.of("status", "ok");
        }
    }
}
