# Multi-stage Java / Spring Boot production Dockerfile
# Supports: Spring Boot 3.x, Java 21 (LTS), Gradle or Maven

# ─── Stage 1: Build (Maven) ───────────────────────────────────────────
FROM eclipse-temurin:21-jdk-alpine AS builder
WORKDIR /app

# Layer caching: copy POM/Gradle files first
COPY pom.xml ./
COPY .mvn/ .mvn/
COPY mvnw ./
RUN chmod +x mvnw

# Download dependencies (cached layer)
RUN ./mvnw dependency:go-offline -B

# Copy source and build
COPY src ./src
RUN ./mvnw package -DskipTests -B --no-transfer-progress

# Extract Spring Boot layers for optimized Docker caching
RUN java -Djarmode=layertools -jar target/*.jar extract --destination /extracted

# ─── Stage 2: JRE Runtime ─────────────────────────────────────────────
FROM eclipse-temurin:21-jre-alpine AS runner
WORKDIR /app

ENV JAVA_OPTS="-XX:+UseContainerSupport -XX:MaxRAMPercentage=75 -XX:+ExitOnOutOfMemoryError -Djava.security.egd=file:/dev/./urandom"
ENV SPRING_PROFILES_ACTIVE=production
ENV PORT=8080

# Security: non-root user
RUN addgroup --system --gid 1001 javagroup \
    && adduser --system --uid 1001 --ingroup javagroup appuser

# Spring Boot layered JAR for fast startup and optimized caching
COPY --from=builder --chown=appuser:javagroup /extracted/dependencies/ ./
COPY --from=builder --chown=appuser:javagroup /extracted/spring-boot-loader/ ./
COPY --from=builder --chown=appuser:javagroup /extracted/snapshot-dependencies/ ./
COPY --from=builder --chown=appuser:javagroup /extracted/application/ ./

LABEL org.opencontainers.image.title="Spring Boot Application" \
      org.opencontainers.image.vendor="Your Org" \
      org.opencontainers.image.licenses="Apache-2.0"

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:8080/actuator/health || exit 1

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS org.springframework.boot.loader.launch.JarLauncher"]
