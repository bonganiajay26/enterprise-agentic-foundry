# Example: Go API Service

Complete working example of a Go API integrated with the Universal Platform.
Uses: net/http + chi router, OpenTelemetry, Prometheus, structured logging (zerolog).

## Structure

```
go-api/
├── cmd/
│   └── server/
│       └── main.go         # Entry point, graceful shutdown
├── internal/
│   ├── api/
│   │   ├── handler.go      # HTTP handlers
│   │   └── health.go       # Health endpoints
│   ├── middleware/
│   │   ├── logging.go      # Structured request logging
│   │   ├── metrics.go      # Prometheus instrumentation
│   │   └── tracing.go      # OpenTelemetry spans
│   └── config/
│       └── config.go       # Configuration (env vars)
├── go.mod
├── go.sum
├── Dockerfile              # → docker/Dockerfile.go (scratch image)
└── catalog-info.yaml
```

## Quick Start

```bash
go mod download
go run cmd/server/main.go

# Docker (scratch image — < 20MB)
docker build -f ../../docker/Dockerfile.go -t go-api .
docker run -p 8080:8080 go-api
```

## Key Dependencies

```go
// go.mod
require (
    github.com/go-chi/chi/v5      v5.0.11  // HTTP router
    github.com/rs/zerolog          v1.32.0  // Structured logging
    github.com/prometheus/client_golang v1.18.0  // Prometheus metrics
    go.opentelemetry.io/otel       v1.23.0  // Tracing
    go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp v0.48.0
    github.com/kelseyhightower/envconfig v1.4.0  // Config from env
)
```

## Health Endpoints

```go
// /health/live — liveness probe
func (h *Handler) Liveness(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(map[string]string{
        "status": "alive",
        "uptime": time.Since(startTime).String(),
    })
}

// /health/ready — readiness probe (checks dependencies)
func (h *Handler) Readiness(w http.ResponseWriter, r *http.Request) {
    if err := h.db.PingContext(r.Context()); err != nil {
        http.Error(w, `{"status":"degraded","reason":"db"}`, http.StatusServiceUnavailable)
        return
    }
    w.WriteHeader(http.StatusOK)
    json.NewEncoder(w).Encode(map[string]string{"status": "ready"})
}
```

## Graceful Shutdown

```go
srv := &http.Server{Addr: addr, Handler: router}
go srv.ListenAndServe()

quit := make(chan os.Signal, 1)
signal.Notify(quit, syscall.SIGTERM, syscall.SIGINT)
<-quit

ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
defer cancel()
srv.Shutdown(ctx)  // Waits for in-flight requests to complete
```

## Platform Integration Checklist

- [ ] `/health/live` and `/health/ready` endpoints
- [ ] Prometheus metrics via `prom-client` at `/metrics`
- [ ] OpenTelemetry tracing with OTLP export
- [ ] Structured JSON logging (zerolog)
- [ ] Graceful shutdown on SIGTERM (30s timeout)
- [ ] Static binary in scratch Docker image
- [ ] Non-root UID 65532 in container
- [ ] `catalog-info.yaml` in repo root
