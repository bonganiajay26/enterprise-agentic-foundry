# Example: Python FastAPI Service

Complete working example of a Python FastAPI service integrated with the Universal Platform.

## Structure

```
python-fastapi/
├── app/
│   ├── main.py             # FastAPI app
│   ├── routers/            # API routes
│   ├── models/             # Pydantic models
│   ├── dependencies.py     # Dependency injection
│   └── health.py           # Health endpoints
├── tests/
├── requirements.txt
├── Dockerfile              # → docker/Dockerfile.python
├── catalog-info.yaml
└── helm/
```

## Quick Start

```bash
# Development
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080

# Docker
docker build -f ../../docker/Dockerfile.python -t python-fastapi .
docker run -p 8080:8080 python-fastapi
```

## Required Dependencies

```txt
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pydantic>=2.5.0
prometheus-fastapi-instrumentator>=6.4.0
opentelemetry-distro>=0.43b0
opentelemetry-exporter-otlp>=1.22.0
structlog>=24.0.0
```

## Health Endpoints

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/health/live")
async def liveness():
    return {"status": "alive"}

@app.get("/health/ready")
async def readiness():
    # Check DB, cache, etc.
    return {"status": "ready"}
```

## Prometheus Instrumentation

```python
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
```

## OpenTelemetry

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

tracer = trace.get_tracer(__name__)

@app.get("/api/orders/{order_id}")
async def get_order(order_id: str):
    with tracer.start_as_current_span("get-order") as span:
        span.set_attribute("order.id", order_id)
        # ... business logic
```

## Platform Integration Checklist

- [ ] `/health/live` and `/health/ready` endpoints
- [ ] Prometheus metrics via `prometheus-fastapi-instrumentator`
- [ ] Structured logging with `structlog`
- [ ] OpenTelemetry tracing configured
- [ ] Graceful shutdown (lifespan context manager)
- [ ] Non-root Docker user (`mluser:mlgroup`)
- [ ] `catalog-info.yaml` in repo root
