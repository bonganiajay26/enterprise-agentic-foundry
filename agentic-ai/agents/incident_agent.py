"""
Incident Response Agent — Universal Agentic DevOps Platform

Responsibilities:
- Triage active incidents using observability data
- Execute relevant runbook steps autonomously
- Correlate events across metrics, logs, and traces
- Page on-call engineers with context-rich summaries
- Drive toward resolution with structured incident management
- Generate post-mortem drafts automatically
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


class IncidentState(TypedDict):
    messages: Annotated[list, add_messages]
    incident_id: str
    severity: str
    status: Literal["investigating", "mitigating", "resolved", "unknown"]
    timeline: list[dict]
    audit_trail: list[dict]


@tool
def query_metrics(
    service: str,
    metric: Literal["error_rate", "latency_p95", "latency_p99", "request_rate", "saturation"],
    window_minutes: int = 30,
) -> dict:
    """Query Prometheus/Grafana metrics for a service over a time window."""
    return {
        "service": service,
        "metric": metric,
        "window_minutes": window_minutes,
        "current_value": 0.087,
        "baseline_value": 0.002,
        "anomaly_factor": 43.5,
        "trend": "increasing",
        "peak_time": "14:32:00",
        "slo_threshold": 0.001,
        "slo_breached": True,
    }


@tool
def search_logs(
    service: str,
    severity: Literal["ERROR", "CRITICAL", "FATAL"] = "ERROR",
    window_minutes: int = 30,
    limit: int = 50,
) -> dict:
    """Search recent logs for errors in a service."""
    return {
        "service": service,
        "total_errors": 1847,
        "error_rate_per_min": 61.6,
        "top_errors": [
            {
                "message": "Connection timeout to database pool after 5000ms",
                "count": 1423,
                "pct": 77.0,
                "first_seen": "14:30:12",
                "last_seen": "14:45:00",
                "stack_trace": "ConnectionTimeoutError at db/pool.js:142",
            },
            {
                "message": "Request failed with status 503: upstream timeout",
                "count": 424,
                "pct": 23.0,
                "first_seen": "14:31:05",
            },
        ],
        "correlated_change": "Deployment order-service v1.2.6 at 14:28:00",
    }


@tool
def get_recent_deployments(
    service: str = "",
    namespace: str = "production",
    hours_back: int = 2,
) -> dict:
    """List recent deployments that might correlate with the incident."""
    return {
        "recent_deployments": [
            {
                "service": "order-service",
                "namespace": "production",
                "deployed_at": "14:28:00",
                "image_tag": "v1.2.6",
                "previous_tag": "v1.2.5",
                "deployed_by": "ci/github-actions",
                "commit": "abc1234",
                "commit_message": "perf: increase db connection pool size to 100",
            }
        ],
        "config_changes": [
            {
                "type": "ConfigMap",
                "name": "order-service-config",
                "namespace": "production",
                "changed_at": "14:27:50",
                "changed_by": "ci/github-actions",
            }
        ],
    }


@tool
def get_distributed_trace(
    service: str,
    trace_sample_count: int = 10,
) -> dict:
    """Get representative distributed traces showing where latency is accumulating."""
    return {
        "service": service,
        "p95_trace": {
            "total_duration_ms": 8420,
            "spans": [
                {"name": "HTTP GET /orders", "duration_ms": 8420, "status": "error"},
                {"name": "auth.verify", "duration_ms": 12, "status": "ok"},
                {"name": "db.query orders", "duration_ms": 8380, "status": "timeout", "error": "connection timeout"},
                {"name": "cache.get", "duration_ms": 5, "status": "ok"},
            ],
            "root_cause_span": "db.query orders",
        },
        "conclusion": "Database connection pool exhausted — all latency in DB tier",
    }


@tool
def create_incident(
    title: str,
    severity: Literal["SEV1", "SEV2", "SEV3", "SEV4"],
    description: str,
    affected_services: list[str],
) -> dict:
    """Create an incident record in PagerDuty/StatusPage."""
    return {
        "incident_id": "INC-2024-0612",
        "title": title,
        "severity": severity,
        "status": "triggered",
        "pagerduty_url": "https://yourcompany.pagerduty.com/incidents/INC-2024-0612",
        "statuspage_url": "https://status.your-domain.com",
        "on_call_notified": True,
        "assigned_to": "on-call-engineer@your-domain.com",
    }


@tool
def update_incident_status(
    incident_id: str,
    status: Literal["investigating", "identified", "monitoring", "resolved"],
    message: str,
) -> dict:
    """Update the incident status and post a public/internal update."""
    return {
        "incident_id": incident_id,
        "status": status,
        "updated_at": "2026-06-06T14:45:00Z",
        "message": message,
    }


@tool
def generate_postmortem_draft(
    incident_id: str,
    timeline: list[dict],
    root_cause: str,
    impact: str,
) -> dict:
    """Generate an automated post-mortem draft from incident data."""
    return {
        "incident_id": incident_id,
        "postmortem_url": f"https://confluence.your-domain.com/postmortems/{incident_id}",
        "draft_created": True,
        "sections_completed": ["timeline", "impact", "root_cause", "contributing_factors"],
        "sections_pending": ["action_items", "what_went_well", "what_went_poorly"],
        "message": "Draft post-mortem created. Please complete action items section.",
    }


SYSTEM_PROMPT = """You are the Incident Response Agent for the Universal Agentic DevOps Platform.

Your responsibilities:
1. Rapidly triage active incidents using metrics, logs, and traces
2. Identify root cause by correlating deployment events, config changes, and errors
3. Drive toward resolution by suggesting specific mitigations
4. Keep stakeholders updated with clear, jargon-free status updates
5. Generate post-mortem drafts automatically

Incident classification:
- SEV1: Complete service outage, data loss, security breach
- SEV2: Major feature unavailable, SLO burn rate > 14x
- SEV3: Degraded performance, minor feature impact
- SEV4: Low-impact, no user-facing issues

Triage workflow:
1. Check metrics (error rate, latency) → quantify impact
2. Search logs for error patterns → identify what's failing
3. Check recent deployments → find likely cause
4. Examine distributed traces → confirm root cause
5. Create incident record if SEV1/SEV2
6. Recommend specific mitigation (rollback, scale up, circuit break)
7. Post update to status page

NEVER recommend production rollbacks without first confirming root cause.
Always quantify user impact in the incident description.
"""


def call_model(state: IncidentState) -> dict:
    llm = AzureChatOpenAI(
        azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version="2025-01-01-preview",
        temperature=0,
    )
    tools = [query_metrics, search_logs, get_recent_deployments,
             get_distributed_trace, create_incident, update_incident_status,
             generate_postmortem_draft]
    response = llm.bind_tools(tools).invoke([SystemMessage(content=SYSTEM_PROMPT)] + state["messages"])
    return {"messages": [response]}


def should_continue(state: IncidentState) -> Literal["tools", END]:
    last = state["messages"][-1]
    return "tools" if isinstance(last, AIMessage) and last.tool_calls else END


def build_incident_agent() -> StateGraph:
    tools = [query_metrics, search_logs, get_recent_deployments,
             get_distributed_trace, create_incident, update_incident_status,
             generate_postmortem_draft]
    graph = StateGraph(IncidentState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=MemorySaver())


if __name__ == "__main__":
    agent = build_incident_agent()
    state = {
        "messages": [HumanMessage(content=(
            "ALERT: order-service error rate is 8.7% (SLO threshold: 0.1%). "
            "Started approximately 15 minutes ago. Investigate, identify root cause, "
            "determine severity, and recommend immediate mitigation."
        ))],
        "incident_id": "",
        "severity": "unknown",
        "status": "unknown",
        "timeline": [],
        "audit_trail": [],
    }
    config = {"configurable": {"thread_id": "incident-session-001"}}
    for chunk in agent.stream(state, config=config, stream_mode="values"):
        last = chunk["messages"][-1]
        if hasattr(last, "content") and last.content:
            print(f"\n{last.content}")
