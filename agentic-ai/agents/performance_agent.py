"""
Performance Agent — Universal Agentic DevOps Platform

Responsibilities:
- Analyze p95/p99 latency trends and identify bottlenecks
- Review database query performance
- Detect N+1 queries and missing indexes
- Analyze JVM/Node.js/Python runtime performance
- Recommend caching strategies
- Profile memory usage patterns
- Generate load test recommendations
"""

from __future__ import annotations

import os
from typing import Annotated, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import AzureChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict


class PerformanceState(TypedDict):
    messages: Annotated[list, add_messages]
    bottlenecks_identified: list[dict]
    optimizations_recommended: list[dict]
    audit_trail: list[dict]


@tool
def get_latency_percentiles(
    service: str,
    endpoint: str = "",
    window_hours: int = 24,
) -> dict:
    """Get p50/p95/p99/p999 latency percentiles for a service or specific endpoint."""
    return {
        "service": service,
        "endpoint": endpoint or "all",
        "window_hours": window_hours,
        "percentiles": {
            "p50_ms": 45,
            "p95_ms": 320,
            "p99_ms": 890,
            "p999_ms": 4200,
        },
        "slo_p95_target_ms": 200,
        "slo_breached": True,
        "slow_endpoints": [
            {"endpoint": "GET /api/orders", "p95_ms": 1240, "call_count_per_min": 450},
            {"endpoint": "POST /api/reports/generate", "p95_ms": 8900, "call_count_per_min": 12},
        ],
        "trend": "degrading",
        "degradation_start": "2026-06-05T18:00:00Z",
    }


@tool
def analyze_database_performance(
    database_type: Literal["postgresql", "mysql", "mongodb", "redis"],
    service: str = "",
) -> dict:
    """Analyze slow queries, missing indexes, connection pool stats."""
    return {
        "database_type": database_type,
        "slow_queries": [
            {
                "query": "SELECT * FROM orders o JOIN order_items oi ON o.id = oi.order_id WHERE o.customer_id = $1",
                "avg_duration_ms": 1240,
                "execution_count_per_min": 450,
                "issue": "Missing index on order_items.order_id — full table scan",
                "fix": "CREATE INDEX CONCURRENTLY idx_order_items_order_id ON order_items(order_id)",
                "estimated_improvement_pct": 95,
            },
            {
                "query": "SELECT COUNT(*) FROM products WHERE category = $1 AND status = 'active'",
                "avg_duration_ms": 340,
                "execution_count_per_min": 2100,
                "issue": "Missing composite index on (category, status)",
                "fix": "CREATE INDEX CONCURRENTLY idx_products_category_status ON products(category, status)",
                "estimated_improvement_pct": 90,
            },
        ],
        "connection_pool": {
            "pool_size": 10,
            "active_connections": 10,
            "waiting_requests": 23,
            "recommendation": "Increase pool size to 25 — pool exhausted under load",
        },
        "n_plus_1_queries_detected": 2,
        "total_monthly_db_cost_savings_potential_usd": 280.00,
    }


@tool
def analyze_cache_effectiveness(service: str) -> dict:
    """Analyze cache hit rates and recommend caching improvements."""
    return {
        "service": service,
        "redis_stats": {
            "hit_rate_pct": 42.0,
            "target_hit_rate_pct": 80.0,
            "miss_rate_pct": 58.0,
            "eviction_rate": 0.12,
        },
        "uncached_hot_queries": [
            {
                "query_pattern": "user profile lookups by ID",
                "queries_per_min": 3400,
                "avg_db_latency_ms": 8,
                "recommendation": "Cache with TTL=300s — same user accessed ~12x/minute",
                "expected_latency_reduction_pct": 94,
            }
        ],
        "over_cached_patterns": [
            {
                "pattern": "product inventory levels",
                "current_ttl_s": 3600,
                "recommendation": "Reduce TTL to 30s — stale inventory causes overselling",
            }
        ],
    }


@tool
def analyze_memory_usage(
    service: str,
    runtime: Literal["nodejs", "python", "jvm", "dotnet", "go"],
) -> dict:
    """Analyze memory usage patterns, detect leaks and excessive GC pressure."""
    return {
        "service": service,
        "runtime": runtime,
        "heap_usage_mb": 1840,
        "heap_limit_mb": 2048,
        "heap_utilization_pct": 89.8,
        "gc_metrics": {
            "major_gc_count_per_hour": 48,
            "avg_gc_pause_ms": 180,
            "time_in_gc_pct": 14.4,
            "concern": "Excessive major GC — memory pressure likely causing latency spikes",
        },
        "memory_leak_indicators": [
            {
                "indicator": "Heap grows 50MB/hour without releasing",
                "suspected_cause": "EventEmitter listeners not being removed",
                "recommendation": "Audit all EventEmitter subscriptions, ensure removeListener() called on cleanup",
            }
        ],
        "recommended_heap_limit_mb": 3072,
    }


@tool
def get_throughput_capacity(
    service: str,
    current_rps: float = 0,
) -> dict:
    """Estimate maximum throughput capacity and recommend scaling thresholds."""
    return {
        "service": service,
        "current_rps": current_rps or 847,
        "max_capacity_rps": 1200,
        "headroom_pct": 29.4,
        "cpu_bottleneck_rps": 1150,
        "memory_bottleneck_rps": 2000,
        "io_bottleneck_rps": 1200,
        "recommendations": [
            "Scale at 70% capacity (~840 RPS) — add HPA trigger at 70% CPU",
            "IO-bound bottleneck: consider adding read replicas or connection pooling (PgBouncer)",
            "With DB index fixes, capacity should increase to ~3000 RPS",
        ],
    }


SYSTEM_PROMPT = """You are the Performance Agent for the Universal Agentic DevOps Platform.

Your responsibilities:
1. Analyze service latency percentiles and identify which endpoints are slowest
2. Find database performance issues: slow queries, missing indexes, N+1 patterns
3. Optimize caching: identify what should be cached and correct TTLs
4. Detect memory leaks and GC pressure
5. Estimate service capacity and recommend scaling thresholds

Performance targets:
- p95 latency < 200ms for synchronous API calls
- p99 latency < 500ms
- Cache hit rate > 80% for hot data
- Database query time < 10ms for indexed queries
- GC time < 5% of total execution time

When presenting findings, always:
1. Quantify the impact (latency saved, RPS gained, cost reduced)
2. Prioritize by user impact (p95 latency improvements first)
3. Estimate implementation effort (Quick Win < 1 day, Medium 1-5 days, Complex 5+ days)
4. Provide the exact code/config fix, not just the concept
"""


def call_model(state: PerformanceState) -> dict:
    llm = AzureChatOpenAI(
        azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version="2025-01-01-preview",
        temperature=0,
    )
    tools = [get_latency_percentiles, analyze_database_performance,
             analyze_cache_effectiveness, analyze_memory_usage, get_throughput_capacity]
    response = llm.bind_tools(tools).invoke([SystemMessage(content=SYSTEM_PROMPT)] + state["messages"])
    return {"messages": [response]}


def should_continue(state: PerformanceState) -> Literal["tools", END]:
    last = state["messages"][-1]
    return "tools" if isinstance(last, AIMessage) and last.tool_calls else END


def build_performance_agent() -> StateGraph:
    tools = [get_latency_percentiles, analyze_database_performance,
             analyze_cache_effectiveness, analyze_memory_usage, get_throughput_capacity]
    graph = StateGraph(PerformanceState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=MemorySaver())
