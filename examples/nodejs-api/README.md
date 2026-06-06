# Example: Node.js API Service

Complete working example of a Node.js Express API integrated with the Universal Platform.

## Structure

```
nodejs-api/
├── src/
│   ├── app.js              # Express app setup
│   ├── routes/             # API routes
│   ├── middleware/         # Auth, logging, error handling
│   └── health.js           # Health check endpoints
├── tests/
├── Dockerfile              # → docker/Dockerfile.node
├── catalog-info.yaml       # Backstage catalog entry
├── .github/workflows/      # → .github/workflows/ci-universal.yml
└── helm/                   # → helm/base-service/
```

## Quick Start

```bash
# Development
npm install
npm run dev

# Docker
docker build -f ../../docker/Dockerfile.node -t nodejs-api .
docker run -p 8080:8080 nodejs-api

# Kubernetes
helm upgrade --install nodejs-api ../../helm/base-service \
  --set image.repository=your-registry/nodejs-api \
  --set image.tag=latest \
  -n dev --create-namespace
```

## Health Endpoints (Required)

| Endpoint | Purpose |
|---|---|
| `GET /health/live` | Liveness probe — is the process running? |
| `GET /health/ready` | Readiness probe — is the service ready to serve traffic? |
| `GET /metrics` | Prometheus metrics (prom-client) |

## Catalog Entry

```yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: nodejs-api
  title: Node.js API Service
  description: Example Node.js API service
  tags: [nodejs, api, rest]
  annotations:
    github.com/project-slug: your-org/nodejs-api
    backstage.io/techdocs-ref: dir:.
    prometheus.io/scrape: "true"
spec:
  type: service
  lifecycle: production
  owner: platform-team
  system: platform
  providesApis:
    - nodejs-api
```

## Platform Integration Checklist

- [ ] Health endpoints (`/health/live`, `/health/ready`)
- [ ] Prometheus metrics endpoint (`/metrics`)
- [ ] OpenTelemetry instrumentation (`@opentelemetry/auto-instrumentations-node`)
- [ ] Structured JSON logging (`pino` or `winston`)
- [ ] Graceful shutdown handler (`SIGTERM`)
- [ ] Non-root Dockerfile
- [ ] Resource requests/limits set in Helm values
- [ ] `catalog-info.yaml` in repo root
- [ ] Security headers (helmet.js)
- [ ] CORS configured
