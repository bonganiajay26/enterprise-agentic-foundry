"""
Python FastAPI Service Template — Universal Platform
Production-ready: structured logging, OTel tracing, Prometheus metrics, graceful shutdown
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.health import health_router
from app.config import Settings

# ─── Settings ─────────────────────────────────────────────────────────
settings = Settings()

# ─── Structured Logging ───────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if settings.debug else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        logging.DEBUG if settings.debug else logging.INFO
    ),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

# ─── OpenTelemetry ────────────────────────────────────────────────────
def setup_tracing() -> None:
    if not settings.otel_endpoint:
        return
    resource = Resource.create({
        "service.name": settings.service_name,
        "service.version": settings.service_version,
        "deployment.environment": settings.environment,
    })
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{settings.otel_endpoint}/v1/traces"))
    )
    trace.set_tracer_provider(provider)

# ─── Prometheus Metrics ───────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP request count",
    ["method", "endpoint", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
)

# ─── Lifespan ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and graceful shutdown."""
    log.info("Starting up", service=settings.service_name, version=settings.service_version)
    setup_tracing()
    # Database pool, cache connections, etc.
    # await database.connect()
    yield
    # Graceful shutdown
    log.info("Shutting down")
    # await database.disconnect()

# ─── Application ──────────────────────────────────────────────────────
app = FastAPI(
    title=settings.service_name,
    version=settings.service_version,
    description="Production FastAPI service — Universal Platform",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)

# ─── Middleware ───────────────────────────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def request_logging_middleware(request: Request, call_next) -> Response:
    """Log all requests with structured logging and collect Prometheus metrics."""
    start = time.perf_counter()
    request_id = request.headers.get("x-request-id", "")

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    response = await call_next(request)
    elapsed = time.perf_counter() - start

    # Skip logging for health probes to reduce noise
    if not request.url.path.startswith("/health"):
        log.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=round(elapsed * 1000, 2),
        )

    # Prometheus metrics
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status_code=response.status_code,
    ).inc()
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path,
    ).observe(elapsed)

    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# ─── Routers ──────────────────────────────────────────────────────────
app.include_router(health_router)

# ─── Metrics Endpoint ─────────────────────────────────────────────────
@app.get("/metrics", include_in_schema=False)
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# ─── Global Exception Handler ─────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("Unhandled exception", error=str(exc), path=request.url.path, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "request_id": request.headers.get("x-request-id")},
    )

# ─── OTel Instrumentation ─────────────────────────────────────────────
FastAPIInstrumentor.instrument_app(app, excluded_urls="health/live,health/ready,metrics")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        workers=int(os.getenv("WORKERS", "4")),
        log_config=None,  # Use structlog instead
        access_log=False,  # Handled by middleware
    )
