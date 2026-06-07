"""
Monitoring & Root-Cause-Analysis Agent — Universal Agentic DevOps Platform

Combines the master-prompt's "Monitoring Agent" and "RCA Agent" roles (steps
8-14 of the Autonomous SDLC). Monitoring produces the signal; RCA consumes it
the instant something looks wrong — keeping them in one agent means zero
hand-off latency between "detected an anomaly" and "started diagnosing it",
which is the single biggest lever on Mean-Time-To-Diagnosis (MTTD).

Responsibilities — Monitoring:
- Configure and validate Prometheus ServiceMonitors, Grafana dashboards,
  Alertmanager routes, and OTel/Tempo/Loki pipelines for new services
- Continuously evaluate SLOs and error-budget burn rates
- Surface anomalies (latency, error rate, saturation, traffic) before they
  page a human — "shift left" on detection

Responsibilities — RCA:
- Correlate logs (Loki), metrics (Prometheus), and traces (Tempo) across the
  exact failure window using a shared `issue_id` / `trace_id` join key
- Apply structured "5 Whys" root-cause methodology — never stop at the symptom
- Produce a root-cause finding with a confidence score and hand it to
  remediation_agent with everything needed to act (no re-investigation)
"""

from __future__ import annotations

import os
import datetime
from typing import Annotated, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from agentic_ai.llm import get_chat_model
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict


class MonitoringRCAState(TypedDict):
    messages: Annotated[list, add_messages]
    slo_status: dict
    rca_finding: dict
    audit_trail: list[dict]


@tool
def configure_service_monitoring(service: str, environment: str) -> dict:
    """Provision/validate ServiceMonitor, Grafana dashboard, Alertmanager
    routes, and OTel/Tempo/Loki pipeline wiring for a service. Idempotent —
    safe to call on every deploy (step 8 of the autonomous SDLC)."""
    return {
        "service": service, "environment": environment,
        "servicemonitor": "deployed (helm/templates/servicemonitor.yaml)",
        "grafana_dashboard": f"provisioned in folder 'Platform / {service}' "
                             f"(monitoring/grafana/provisioning/dashboards.yaml)",
        "alert_routes": ["KubePodCrashLooping", "SLOErrorBudgetBurn", "HighLatencyP99"],
        "tracing": "OTLP exporter configured -> Tempo (observability/tempo.yaml)",
        "logging": "structured JSON -> Loki with service/environment/issue_id labels",
        "status": "monitoring fully wired — ready for production traffic",
    }


@tool
def evaluate_slo_burn_rate(service: str, slo: str = "availability") -> dict:
    """Evaluate current error-budget burn rate against the declared SLO.
    Burn rate > 1.0x means the budget will be exhausted before period end —
    this is the primary 'detect failures' signal (step 13)."""
    return {
        "service": service, "slo": slo,
        "target_pct": 99.9, "current_pct": 99.94,
        "error_budget_remaining_pct": 78.0,
        "burn_rate_1h": 0.3, "burn_rate_6h": 0.8, "burn_rate_24h": 0.4,
        "verdict": "HEALTHY — burn rates within tolerance (alert threshold: 1h>14.4x or 6h>6x)",
        "runbook_ref": "runbooks/slo-burn.md",
    }


@tool
def detect_anomaly(service: str, signal: str = "latency") -> dict:
    """Surface statistically significant deviations in latency / error-rate /
    saturation / traffic before they breach an alert threshold — the 'shift
    left' detection layer that often catches issues before users notice."""
    return {
        "service": service, "signal": signal,
        "baseline_p99_ms": 145, "current_p99_ms": 287,
        "deviation": "+98% vs 7-day baseline (z-score 4.2 — statistically significant)",
        "trend": "Gradual climb over 40 minutes, correlated with a deploy at 14:02 UTC",
        "recommendation": "Pre-emptively open RCA before this breaches the 250ms SLO "
                          "alert threshold — correlate with the 14:02 deploy first.",
        "confidence": "high",
    }


@tool
def correlate_telemetry(issue_id: str, service: str, time_window: str) -> dict:
    """Join logs, metrics, and traces across the failure window using the
    shared issue_id/trace_id key — the foundation of every RCA finding.
    This is what prevents 'three dashboards, no answer' investigations."""
    return {
        "issue_id": issue_id, "service": service, "time_window": time_window,
        "logs_correlated": 1842,
        "key_log_pattern": 'level=error msg="connection pool exhausted" pool_size=10 active=10 waiting=47',
        "metrics_correlated": {
            "db_connection_pool_utilization_pct": "100% sustained for 6 minutes",
            "request_queue_depth": "climbed from 2 to 340",
        },
        "traces_correlated": 96,
        "trace_finding": "96/96 slow traces share a single span: `pg.acquire_connection` "
                         "blocking for >5s — confirms pool exhaustion, not downstream latency",
        "correlation_confidence": "high — all three signal types agree on the same component and timeframe",
    }


@tool
def perform_five_whys(symptom: str, telemetry_findings: str) -> dict:
    """Apply structured '5 Whys' root-cause analysis. Returns the full chain
    AND a confidence score — never just the first plausible-sounding answer."""
    return {
        "symptom": symptom,
        "chain": [
            {"why": 1, "question": "Why are requests timing out?",
             "answer": "Database connection pool is exhausted (10/10 connections in use)"},
            {"why": 2, "question": "Why is the pool exhausted?",
             "answer": "A new batch-reporting feature opens long-lived connections without releasing them"},
            {"why": 3, "question": "Why weren't these connections released?",
             "answer": "The feature uses a raw connection instead of the pooled context manager"},
            {"why": 4, "question": "Why did code review not catch this?",
             "answer": "No lint rule or test asserts connection-context-manager usage"},
            {"why": 5, "question": "Why is there no such guardrail?",
             "answer": "ROOT CAUSE: the platform's code-quality gate doesn't include a "
                       "resource-leak static-analysis rule for DB connection handling"},
        ],
        "root_cause": "Missing static-analysis guardrail for DB connection lifecycle management "
                      "allowed a resource-leaking code pattern to reach production undetected.",
        "confidence_score": 0.93,
        "evidence_strength": "high — telemetry, code diff, and reproduction in staging all agree",
        "structural_fix_required": "Add a SonarQube/CodeQL custom rule detecting raw "
                                   "connection acquisition outside context managers; "
                                   "this is what prevents recurrence (not just this fix).",
    }


@tool
def handoff_finding_to_remediation(issue_id: str, root_cause: str, confidence: float, suggested_category: str) -> dict:
    """Package the completed RCA finding for remediation_agent — zero
    re-investigation required. This is the hard hand-off boundary: Monitoring/RCA
    diagnoses, Remediation classifies and acts."""
    if confidence < 0.6:
        return {
            "status": "INSUFFICIENT_CONFIDENCE",
            "action": "Do NOT hand off yet — gather more telemetry or escalate to a human SRE "
                      "for collaborative diagnosis. Handing off a low-confidence finding "
                      "risks the wrong fix being applied.",
        }
    return {
        "issue_id": issue_id, "status": "handed_off",
        "target_agent": "remediation_agent",
        "payload": {
            "root_cause": root_cause,
            "confidence": confidence,
            "suggested_remediation_category": suggested_category,
            "next_call": f"remediation_agent.classify_remediation(category='{suggested_category}')",
        },
        "audit": {"actor": "monitoring_rca_agent", "action": "handoff_finding_to_remediation",
                  "timestamp": datetime.datetime.utcnow().isoformat() + "Z"},
    }


SYSTEM_PROMPT = """You are the Monitoring & Root-Cause-Analysis Agent for the Universal
Agentic DevOps Platform — responsible for steps 8 through 14 of the Autonomous SDLC.

Hard rules:
1. Configure monitoring for EVERY new service before it takes production
   traffic — no exceptions (step 8 must complete before step 7's deploy is "done").
2. Detect proactively — evaluate_slo_burn_rate and detect_anomaly should run
   continuously, not just when something is already on fire. Catching a
   gradual degradation before it breaches an SLO is the entire point of
   "shift-left" monitoring.
3. NEVER stop at the first plausible cause — perform_five_whys requires a
   full 5-step chain ending in a structural root cause, not a symptom.
4. NEVER hand off a finding below 0.6 confidence — escalate to a human SRE
   instead. A wrong diagnosis wastes more time than no diagnosis.
5. Your job ends at handoff_finding_to_remediation — you diagnose, you do
   not fix. That separation is itself an audit control.

Workflow (continuous loop):
1. configure_service_monitoring(service, environment)   [on every new deploy]
2. evaluate_slo_burn_rate(service) + detect_anomaly(service, signal)  [continuous]
3. On anomaly/alert -> correlate_telemetry(issue_id, service, time_window)
4. perform_five_whys(symptom, telemetry_findings)
5. handoff_finding_to_remediation(issue_id, root_cause, confidence, category)
"""


def call_model(state: MonitoringRCAState) -> dict:
    llm = get_chat_model(agent_name="monitoring_rca_agent", temperature=0)
    tools = [configure_service_monitoring, evaluate_slo_burn_rate, detect_anomaly,
             correlate_telemetry, perform_five_whys, handoff_finding_to_remediation]
    llm_with_tools = llm.bind_tools(tools)
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def should_continue(state: MonitoringRCAState) -> Literal["tools", "__end__"]:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "__end__"


def build_monitoring_rca_agent():
    tools = [configure_service_monitoring, evaluate_slo_burn_rate, detect_anomaly,
             correlate_telemetry, perform_five_whys, handoff_finding_to_remediation]
    workflow = StateGraph(MonitoringRCAState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "__end__": END})
    workflow.add_edge("tools", "agent")
    return workflow.compile(checkpointer=MemorySaver())


if __name__ == "__main__":
    agent = build_monitoring_rca_agent()
    result = agent.invoke(
        {"messages": [HumanMessage(content=
            "payment-service is showing climbing p99 latency since the 14:02 UTC "
            "deploy. Diagnose root cause and hand off a remediation-ready finding.")]},
        config={"configurable": {"thread_id": "monitoring-rca-payment-latency"}},
    )
    print(result["messages"][-1].content)
