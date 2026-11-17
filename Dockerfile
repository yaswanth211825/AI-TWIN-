# --- Build stage: compile and package the jar ---
FROM eclipse-temurin:21-jdk AS build
WORKDIR /app
COPY .mvn .mvn
COPY mvnw pom.xml ./
RUN ./mvnw -q -B dependency:go-offline
COPY src src
RUN ./mvnw -q -B -DskipTests package && cp target/*.jar app.jar

# --- Run stage: only the JRE and the jar (smaller, no build tools) ---
FROM eclipse-temurin:21-jre
WORKDIR /app
RUN useradd --system --uid 1001 app
COPY --from=build /app/app.jar app.jar
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh
USER app
# Use at most 75% of the container's memory for the heap (free hosting tiers have ~512 MB).
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75 -XX:+UseSerialGC"
EXPOSE 8090
ENTRYPOINT ["./docker-entrypoint.sh"]
