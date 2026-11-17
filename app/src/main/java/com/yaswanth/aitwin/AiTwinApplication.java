package com.yaswanth.aitwin;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

/** Entry point. @ConfigurationPropertiesScan finds TwinProperties (the "ai-twin.*" settings). */
@SpringBootApplication
@ConfigurationPropertiesScan
public class AiTwinApplication {

    public static void main(String[] args) {
        SpringApplication.run(AiTwinApplication.class, args);
    }
}
