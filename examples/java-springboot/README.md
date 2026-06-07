# Example: Java Spring Boot Service

Complete working example of a Spring Boot 3 / Java 21 service integrated with the Universal Platform.

## Structure

```
java-springboot/
├── src/
│   ├── main/
│   │   ├── java/com/platform/
│   │   │   ├── Application.java      # Main entry point
│   │   │   ├── HealthController.java # /actuator/health endpoints
│   │   │   ├── ApiController.java    # Business logic
│   │   │   └── config/               # Security, CORS, OTel config
│   │   └── resources/
│   │       ├── application.yml       # Main configuration
│   │       └── logback-spring.xml    # JSON logging (Loki-compatible)
│   └── test/
├── pom.xml                           # Dependencies
├── Dockerfile                        # → docker/Dockerfile.java
└── catalog-info.yaml
```

## Quick Start

```bash
# Build and run
./mvnw spring-boot:run

# Or with Docker
docker build -f ../../docker/Dockerfile.java -t java-api .
docker run -p 8080:8080 java-api

# Or with Docker Compose
docker-compose -f ../../docker/docker-compose.dev.yml up
```

## Health Endpoints (Spring Actuator)

| Endpoint | Purpose | K8s Probe |
|---|---|---|
| `GET /actuator/health/liveness` | Liveness | livenessProbe |
| `GET /actuator/health/readiness` | Readiness | readinessProbe |
| `GET /actuator/prometheus` | Prometheus metrics | — |
| `GET /actuator/info` | Build + version info | — |

## Prometheus Metrics (Micrometer)

Spring Boot auto-instruments with Micrometer. Key metrics:
- `http_server_requests_seconds` — Request latency by endpoint and status
- `jvm_memory_used_bytes` — Heap/non-heap usage
- `hikaricp_connections` — Database connection pool
- `process_cpu_usage` — JVM CPU utilization

## Structured Logging (JSON → Loki)

```xml
<!-- logback-spring.xml — production profile uses JSON -->
<springProfile name="production">
  <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
    <encoder class="net.logstash.logback.encoder.LogstashEncoder">
      <fieldNames>
        <timestamp>timestamp</timestamp>
        <level>level</level>
        <logger>logger</logger>
      </fieldNames>
      <includeContext>true</includeContext>
      <customFields>{"service":"${SERVICE_NAME}","environment":"${ENVIRONMENT}"}</customFields>
    </encoder>
  </appender>
</springProfile>
```

## Resilience4j Circuit Breaker

```java
@CircuitBreaker(name = "paymentGateway", fallbackMethod = "paymentFallback")
@Retry(name = "paymentGateway")
public PaymentResponse processPayment(PaymentRequest request) {
    return paymentGatewayClient.process(request);
}

public PaymentResponse paymentFallback(PaymentRequest request, Exception ex) {
    log.warn("Payment gateway circuit open — using fallback");
    return PaymentResponse.queued(request.getTransactionId());
}
```

## Platform Integration Checklist

- [ ] Actuator health endpoints configured
- [ ] Micrometer + Prometheus metrics exported at `/actuator/prometheus`
- [ ] JSON logging with logstash-logback-encoder
- [ ] OpenTelemetry tracing (micrometer-tracing-bridge-otel)
- [ ] Graceful shutdown (`spring.lifecycle.timeout-per-shutdown-phase: 30s`)
- [ ] Layered JAR in Dockerfile (fast rebuild, optimized cache)
- [ ] Non-root Docker user
- [ ] JVM tuned for containers (`-XX:+UseContainerSupport`)
- [ ] `catalog-info.yaml` in repo root
