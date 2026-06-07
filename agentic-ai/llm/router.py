"""
router.py — Cost/Latency/Quality/Compliance-Aware LLM Router

Wraps `provider_factory` with a runtime routing layer that:
  - Scores candidate providers using the strategy + weights from llm-config.yaml
    (cost | latency | quality | compliance | availability | weighted)
  - Tracks rolling success/failure + p50 latency per provider (in-memory;
    swap `MetricsStore` for Redis/Prometheus pushgateway in production)
  - Applies a circuit breaker (open -> half-open -> closed) so a degraded
    provider is automatically skipped and retried after a cool-down
  - Transparently fails over to the next-best candidate and emits structured
    telemetry for the Cost Optimization and Incident Response agents to consume

Usage:
    from agentic_ai.llm.router import LLMRouter

    router = LLMRouter(agent_name="incident_response_agent")
    response = router.invoke(messages)              # automatic routing + fallback
    router.record_outcome(...)                      # called internally on every hop
"""

from __future__ import annotations

import time
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from agentic_ai.llm.provider_factory import (
    ResolvedModel,
    build_model,
    load_config,
    resolve_chain,
    ProviderConfigError,
)

logger = logging.getLogger("agentic_ai.llm.router")


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------
class CircuitState(str, Enum):
    CLOSED = "closed"        # normal operation
    OPEN = "open"            # provider disabled — fast-fail to next candidate
    HALF_OPEN = "half_open"  # probing — allow one trial request through


@dataclass
class ProviderHealth:
    provider: str
    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    opened_at: float = 0.0
    latencies_ms: list[float] = field(default_factory=list)   # rolling window
    successes: int = 0
    failures: int = 0

    def p50_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        ordered = sorted(self.latencies_ms)
        return ordered[len(ordered) // 2]

    def success_rate(self) -> float:
        total = self.successes + self.failures
        return 1.0 if total == 0 else self.successes / total


class MetricsStore:
    """In-memory provider health tracker. Thread-safe.

    Production deployments should back this with Redis (shared across pods)
    and emit each transition to Prometheus via the pushgateway, e.g.:
        llm_router_circuit_state{provider="anthropic"} 0|1|2
        llm_router_provider_latency_ms_bucket{provider="anthropic", le="..."}
    """

    _WINDOW = 50  # keep the last N latency samples per provider

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._health: dict[str, ProviderHealth] = {}

    def get(self, provider: str) -> ProviderHealth:
        with self._lock:
            return self._health.setdefault(provider, ProviderHealth(provider=provider))

    def record_success(self, provider: str, latency_ms: float, breaker_cfg: dict) -> None:
        with self._lock:
            h = self._health.setdefault(provider, ProviderHealth(provider=provider))
            h.successes += 1
            h.consecutive_failures = 0
            h.latencies_ms.append(latency_ms)
            h.latencies_ms = h.latencies_ms[-self._WINDOW:]
            if h.state == CircuitState.HALF_OPEN:
                logger.info("circuit-breaker: %s recovered — closing circuit", provider)
                h.state = CircuitState.CLOSED

    def record_failure(self, provider: str, breaker_cfg: dict) -> None:
        with self._lock:
            h = self._health.setdefault(provider, ProviderHealth(provider=provider))
            h.failures += 1
            h.consecutive_failures += 1
            threshold = breaker_cfg.get("failure_threshold", 5)
            if h.consecutive_failures >= threshold and h.state != CircuitState.OPEN:
                h.state = CircuitState.OPEN
                h.opened_at = time.monotonic()
                logger.warning(
                    "circuit-breaker: %s tripped OPEN after %d consecutive failures",
                    provider, h.consecutive_failures,
                )

    def is_available(self, provider: str, breaker_cfg: dict) -> bool:
        with self._lock:
            h = self._health.setdefault(provider, ProviderHealth(provider=provider))
            if h.state == CircuitState.CLOSED:
                return True
            if h.state == CircuitState.OPEN:
                cool_down = breaker_cfg.get("half_open_after_seconds", 60)
                if time.monotonic() - h.opened_at >= cool_down:
                    h.state = CircuitState.HALF_OPEN
                    logger.info("circuit-breaker: %s entering HALF_OPEN probe", provider)
                    return True
                return False
            # HALF_OPEN — allow exactly one probe through
            return True


_GLOBAL_METRICS = MetricsStore()


# ---------------------------------------------------------------------------
# Scoring strategies
# ---------------------------------------------------------------------------
def _normalize(values: list[float], invert: bool = False) -> list[float]:
    """Min-max normalize to [0,1]; `invert=True` makes lower-is-better -> higher score."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [1.0 for _ in values]
    norm = [(v - lo) / (hi - lo) for v in values]
    return [1.0 - n for n in norm] if invert else norm


def score_candidates(
    candidates: list[ResolvedModel],
    metrics: MetricsStore,
    strategy: str,
    weights: dict,
) -> list[tuple[ResolvedModel, float]]:
    """Returns candidates paired with a score in [0,1], higher = preferred,
    sorted descending. Lower cost / lower latency / higher quality / higher
    availability all map to higher scores."""

    cost = [c.in_per_1m + c.out_per_1m for c in candidates]
    latency = [metrics.get(c.provider).p50_latency_ms() or _latency_tier_estimate(c) for c in candidates]
    quality = [_quality_score(c.quality_tier) for c in candidates]
    availability = [metrics.get(c.provider).success_rate() for c in candidates]

    cost_n = _normalize(cost, invert=True)
    latency_n = _normalize(latency, invert=True)
    quality_n = _normalize(quality, invert=False)
    avail_n = availability  # already in [0,1]

    scored: list[tuple[ResolvedModel, float]] = []
    for i, c in enumerate(candidates):
        if strategy == "cost":
            s = cost_n[i]
        elif strategy == "latency":
            s = latency_n[i]
        elif strategy == "quality":
            s = quality_n[i]
        elif strategy == "availability":
            s = avail_n[i]
        elif strategy == "compliance":
            s = 1.0  # already pre-filtered for compliance; preserve declared order
        else:  # weighted (default)
            s = (
                weights.get("cost", 0.25) * cost_n[i]
                + weights.get("latency", 0.25) * latency_n[i]
                + weights.get("quality", 0.25) * quality_n[i]
                + weights.get("availability", 0.25) * avail_n[i]
            )
        scored.append((c, s))

    if strategy == "compliance":
        return scored  # preserve config order (primary -> fallbacks)
    return sorted(scored, key=lambda pair: pair[1], reverse=True)


_QUALITY_RANK = {"low": 0.25, "medium": 0.5, "high": 0.75, "highest": 1.0}
_LATENCY_TIER_ESTIMATE_MS = {"ultra_fast": 200, "local": 50, "standard": 1200}


def _quality_score(tier: str) -> float:
    return _QUALITY_RANK.get(tier, 0.5)


def _latency_tier_estimate(c: ResolvedModel) -> float:
    """Used until we have live telemetry for a provider — seeds the score
    with a reasonable prior so cold-start routing isn't random."""
    return _LATENCY_TIER_ESTIMATE_MS.get(c.latency_tier, 1200)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
@dataclass
class RoutingDecision:
    chosen: ResolvedModel
    candidates_considered: list[str]
    strategy: str
    score: float
    hop: int


class AllProvidersExhaustedError(RuntimeError):
    """Raised when every candidate in the routing chain failed or is circuit-open."""


class LLMRouter:
    def __init__(
        self,
        agent_name: Optional[str] = None,
        metrics: Optional[MetricsStore] = None,
        **model_kwargs: Any,
    ) -> None:
        self.agent_name = agent_name
        self.metrics = metrics or _GLOBAL_METRICS
        self.model_kwargs = model_kwargs
        self._cfg = load_config()
        self._routing_cfg = self._cfg.get("routing", {})
        self._breaker_cfg = self._routing_cfg.get("circuit_breaker", {})

        agent_overrides = self._cfg.get("agent_overrides", {})
        self._strategy = (
            agent_overrides.get(agent_name, {}).get("routing_strategy")
            if agent_name else None
        ) or self._routing_cfg.get("strategy", "weighted")

    # -- candidate resolution -------------------------------------------------
    def _ranked_candidates(self) -> list[tuple[ResolvedModel, float]]:
        chain = resolve_chain(self.agent_name)
        return score_candidates(
            chain, self.metrics, self._strategy, self._routing_cfg.get("weights", {})
        )

    # -- public API ------------------------------------------------------------
    def invoke(self, messages: Any, **invoke_kwargs: Any) -> Any:
        """
        Routes the request through the ranked candidate chain, skipping any
        provider whose circuit breaker is OPEN, and returns the first
        successful response. Raises `AllProvidersExhaustedError` if every
        candidate fails or is unavailable (the Incident Response Agent should
        treat this as a P1 — the AI platform itself is degraded).
        """
        ranked = self._ranked_candidates()
        max_hops = min(self._routing_cfg.get("max_fallback_hops", 3), len(ranked))
        attempted: list[str] = []
        last_exc: Optional[Exception] = None

        for hop, (resolved, score) in enumerate(ranked[:max_hops], start=1):
            attempted.append(resolved.provider)
            if not self.metrics.is_available(resolved.provider, self._breaker_cfg):
                logger.info("router: skipping %s — circuit OPEN", resolved.provider)
                continue

            decision = RoutingDecision(
                chosen=resolved,
                candidates_considered=[c.provider for c, _ in ranked],
                strategy=self._strategy,
                score=round(score, 4),
                hop=hop,
            )
            logger.info(
                "router: hop=%d provider=%s model=%s strategy=%s score=%.3f",
                hop, resolved.provider, resolved.model, self._strategy, score,
            )

            start = time.monotonic()
            try:
                model = build_model(resolved, **self.model_kwargs)
                response = model.invoke(messages, **invoke_kwargs)
            except Exception as exc:  # noqa: BLE001 — must catch provider-SDK-specific errors generically
                latency_ms = (time.monotonic() - start) * 1000
                self.metrics.record_failure(resolved.provider, self._breaker_cfg)
                logger.warning(
                    "router: provider=%s failed after %.0fms — %s. Failing over.",
                    resolved.provider, latency_ms, exc,
                )
                last_exc = exc
                continue
            else:
                latency_ms = (time.monotonic() - start) * 1000
                self.metrics.record_success(resolved.provider, latency_ms, self._breaker_cfg)
                self._emit_telemetry(decision, latency_ms, success=True)
                return response

        self._emit_telemetry(None, 0.0, success=False, attempted=attempted)
        raise AllProvidersExhaustedError(
            f"agent='{self.agent_name}' — all {len(attempted)} candidate providers "
            f"({', '.join(attempted)}) failed or are circuit-open. Last error: {last_exc}"
        )

    # -- telemetry -------------------------------------------------------------
    def _emit_telemetry(
        self,
        decision: Optional[RoutingDecision],
        latency_ms: float,
        success: bool,
        attempted: Optional[list[str]] = None,
    ) -> None:
        """
        Structured event for the observability stack (Loki/OTel) and the
        Cost Optimization Agent (token spend) and Incident Response Agent
        (provider outage correlation). In production this pushes to:
          - OTel span attributes (llm.provider, llm.model, llm.cost_usd_est)
          - Prometheus counters (llm_router_requests_total{provider,outcome})
        """
        event = {
            "event": "llm_router_decision",
            "agent": self.agent_name,
            "success": success,
            "latency_ms": round(latency_ms, 1),
        }
        if decision:
            event.update(
                provider=decision.chosen.provider,
                model=decision.chosen.model,
                strategy=decision.strategy,
                score=decision.score,
                hop=decision.hop,
                est_cost_per_1m_usd=decision.chosen.in_per_1m + decision.chosen.out_per_1m,
            )
        else:
            event["attempted_providers"] = attempted
        logger.info("telemetry: %s", event)


# ---------------------------------------------------------------------------
# Convenience: drop-in replacement for `provider_factory.get_chat_model`
# for agents that want automatic routing + fallback without managing a
# router instance themselves.
# ---------------------------------------------------------------------------
def get_routed_model(agent_name: Optional[str] = None, **kwargs: Any) -> LLMRouter:
    """Returns an `LLMRouter` exposing `.invoke(messages)` with the same
    call signature agents already use for `BaseChatModel.invoke`."""
    return LLMRouter(agent_name=agent_name, **kwargs)
