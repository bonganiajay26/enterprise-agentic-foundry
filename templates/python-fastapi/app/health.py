"""Health check endpoints — required for Kubernetes probes."""

from __future__ import annotations

import time
from typing import Literal

from fastapi import APIRouter, status
from pydantic import BaseModel

health_router = APIRouter(prefix="/health", tags=["health"])

_startup_time = time.time()
_ready = False


class HealthResponse(BaseModel):
    status: Literal["alive", "ready", "degraded", "starting"]
    timestamp: str
    uptime_seconds: float | None = None
    checks: list[dict] | None = None


@health_router.get(
    "/live",
    response_model=HealthResponse,
    summary="Liveness probe",
    description="Returns 200 if the process is alive. Kubernetes restarts pod if this fails.",
)
async def liveness() -> HealthResponse:
    return HealthResponse(
        status="alive",
        timestamp=_now(),
        uptime_seconds=round(time.time() - _startup_time, 1),
    )


@health_router.get(
    "/ready",
    response_model=HealthResponse,
    summary="Readiness probe",
    description="Returns 200 if service is ready for traffic.",
)
async def readiness() -> HealthResponse:
    checks = await _run_checks()
    all_ok = all(c["healthy"] for c in checks)
    return HealthResponse(
        status="ready" if all_ok else "degraded",
        timestamp=_now(),
        checks=checks,
    )


@health_router.get("/startup", summary="Startup probe")
async def startup() -> dict:
    return {"status": "started", "timestamp": _now()}


async def _run_checks() -> list[dict]:
    checks = []
    # Add dependency checks here:
    # checks.append(await check_database())
    # checks.append(await check_redis())
    return checks


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
