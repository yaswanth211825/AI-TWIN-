package com.yaswanth.aitwin.rag;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import tools.jackson.databind.json.JsonMapper;

/** JSON Lines: one JSON object per line. Blank lines are skipped. */
final class Jsonl {

    private Jsonl() {
    }

    static <T> List<T> read(Path file, Class<T> type, JsonMapper json) throws IOException {
        try (var lines = Files.lines(file, StandardCharsets.UTF_8)) {
            return lines.filter(line -> !line.isBlank())
                    .map(line -> json.readValue(line, type))
                    .toList();
        }
    }
}
