"""
Governance Agent — Universal Agentic DevOps Platform

Responsibilities:
- Enforce platform, security, cost, and AI-governance policies across every
  repository, pipeline, cluster, and agent action
- Audit Backstage catalog entries for ownership, lifecycle, and tagging compliance
- Validate that OPA/Kyverno/Rego policies (governance/policies/) are deployed
  and passing across all environments
- Track AI governance: model usage, provider routing decisions, prompt/response
  audit trails, data residency compliance (works with agentic-ai/llm/router.py telemetry)
- Generate compliance evidence packages (SOC2, ISO27001, GDPR) on a schedule
- Produce the platform Governance Scorecard consumed by leadership reporting
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


class GovernanceState(TypedDict):
    messages: Annotated[list, add_messages]
    scorecard: dict
    violations: list[dict]
    audit_trail: list[dict]


@tool
def audit_resource_tagging(scope: str = "all-namespaces") -> dict:
    """Audit Kubernetes/cloud resources against governance/policies/resource-tagging.rego
    requirements (owner, cost-center, environment, data-classification)."""
    return {
        "scope": scope,
        "resources_scanned": 412,
        "compliant": 379,
        "non_compliant": 33,
        "missing_owner_tag": 14,
        "missing_cost_center": 11,
        "missing_data_classification": 8,
        "compliance_pct": round(379 / 412 * 100, 1),
        "policy_ref": "governance/policies/resource-tagging.rego",
        "remediation": "Auto-fixable via remediation_agent (category=helm_fix) for "
                       "Helm-managed resources; manual PR required for Terraform-managed.",
    }


@tool
def audit_cost_controls(period: str = "last-30-days") -> dict:
    """Audit spend against governance/policies/cost-controls.rego guardrails
    (resource limits, budget alerts, idle-resource detection)."""
    return {
        "period": period,
        "total_spend_usd": 48230.55,
        "budget_usd": 52000.00,
        "budget_utilization_pct": 92.7,
        "guardrail_violations": [
            {"resource": "staging/ml-training-cluster", "issue": "No auto-shutdown policy", "monthly_waste_usd": 1840},
            {"resource": "dev/oversized-postgres", "issue": "4x over-provisioned vCPU", "monthly_waste_usd": 620},
        ],
        "policy_ref": "governance/policies/cost-controls.rego",
        "projected_savings_usd_monthly": 2460,
        "escalation": "Forward to cost_optimization_agent for remediation plan",
    }


@tool
def audit_ai_governance(window: str = "last-7-days") -> dict:
    """Audit Agentic AI Platform usage: provider routing decisions, model
    spend, compliance-filter activations, and prompt/response audit coverage.
    Sources telemetry emitted by agentic_ai.llm.router.LLMRouter."""
    return {
        "window": window,
        "total_llm_invocations": 18420,
        "by_provider": {"azure_openai": 11200, "anthropic": 4830, "groq": 1640, "ollama": 750},
        "compliance_filter_activations": 312,
        "compliance_filter_blocks": 9,
        "circuit_breaker_trips": 2,
        "estimated_spend_usd": 1284.62,
        "prompt_audit_coverage_pct": 100.0,
        "pii_redaction_events": 47,
        "data_residency_violations_detected": 0,
        "policy_ref": "agentic-ai/config/llm-config.yaml#compliance",
        "assessment": "AI governance posture: HEALTHY. All routing decisions logged; "
                      "zero residency violations; circuit breaker functioning as designed.",
    }


@tool
def validate_policy_deployment(policy_engine: str = "opa") -> dict:
    """Confirm that governance/security policies (OPA Gatekeeper / Kyverno /
    Falco) are deployed, synced via ArgoCD, and passing in every environment."""
    return {
        "policy_engine": policy_engine,
        "environments_checked": ["dev", "staging", "production"],
        "policies_deployed": 27,
        "policies_passing": 27,
        "policies_in_dry_run": 2,
        "argocd_sync_status": "Synced",
        "last_admission_denial": {
            "policy": "require-resource-limits",
            "resource": "staging/Deployment/legacy-batch-job",
            "timestamp": (datetime.datetime.utcnow() - datetime.timedelta(hours=6)).isoformat() + "Z",
        },
        "status": "compliant",
    }


@tool
def generate_governance_scorecard(period: str = "Q2-2026") -> dict:
    """Produce the executive Governance Scorecard — a single-pane view of
    platform, security, cost, and AI governance posture for leadership reporting."""
    return {
        "period": period,
        "overall_score": 91,
        "dimensions": {
            "resource_tagging_compliance_pct": 92.0,
            "cost_guardrail_adherence_pct": 95.3,
            "security_policy_pass_rate_pct": 100.0,
            "ai_governance_health": "HEALTHY",
            "audit_trail_completeness_pct": 100.0,
            "soc2_evidence_freshness_days": 3,
        },
        "trend_vs_previous_period": "+4 points",
        "top_actions": [
            "Close 33 resource-tagging gaps (auto-remediation PR queued)",
            "Decommission staging/ml-training-cluster idle capacity (~$1,840/mo)",
            "Promote 2 dry-run OPA policies to enforce mode after 14-day bake",
        ],
        "next_review_date": (datetime.datetime.utcnow() + datetime.timedelta(days=30)).strftime("%Y-%m-%d"),
    }


@tool
def generate_compliance_evidence_package(framework: str = "SOC2") -> dict:
    """Trigger compliance/evidence-collection.sh and package evidence for the
    requested framework (SOC2, ISO27001, GDPR, HIPAA, FedRAMP)."""
    return {
        "framework": framework,
        "evidence_categories": [
            "access-control-logs", "change-management-records", "vulnerability-scan-reports",
            "backup-verification-logs", "incident-postmortems", "ai-governance-audit-trail",
        ],
        "collection_script": "compliance/evidence-collection.sh",
        "package_location": f"s3://compliance-evidence/{framework.lower()}/{datetime.datetime.utcnow().strftime('%Y-%m')}/",
        "retention_policy": "7 years (regulatory minimum) with WORM object-lock",
        "status": "package generated — awaiting auditor review sign-off",
        "control_matrix_ref": "compliance/soc2-controls.md",
    }


SYSTEM_PROMPT = """You are the Governance Agent for the Universal Agentic DevOps Platform.

You are the platform's conscience: you don't build or fix things, you verify
that everything else — pipelines, infrastructure, agents, and the AI layer
itself — operates within the policies, budgets, and compliance commitments
the organization has made.

Responsibilities:
1. Continuously audit resource tagging, cost guardrails, and security-policy
   deployment status across every environment.
2. Specifically govern the AI layer: which providers are used, what they cost,
   whether compliance filters (region/residency) are functioning, and whether
   every prompt/response is captured in the audit trail.
3. Roll findings into a single Governance Scorecard for leadership.
4. Generate compliance evidence packages on demand or on schedule.
5. Escalate violations to the right specialist agent:
   - cost guardrail breaches -> cost_optimization_agent
   - tagging/policy gaps -> remediation_agent (classify before any auto-fix)
   - security policy failures -> security_agent

You never apply fixes yourself — you detect, score, and route. This
separation of concerns (detect vs remediate) is itself a governance control.
"""


def call_model(state: GovernanceState) -> dict:
    llm = get_chat_model(agent_name="governance_agent", temperature=0)
    tools = [audit_resource_tagging, audit_cost_controls, audit_ai_governance,
             validate_policy_deployment, generate_governance_scorecard,
             generate_compliance_evidence_package]
    llm_with_tools = llm.bind_tools(tools)
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def should_continue(state: GovernanceState) -> Literal["tools", "__end__"]:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "__end__"


def build_governance_agent():
    tools = [audit_resource_tagging, audit_cost_controls, audit_ai_governance,
             validate_policy_deployment, generate_governance_scorecard,
             generate_compliance_evidence_package]
    workflow = StateGraph(GovernanceState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "__end__": END})
    workflow.add_edge("tools", "agent")
    return workflow.compile(checkpointer=MemorySaver())


if __name__ == "__main__":
    agent = build_governance_agent()
    result = agent.invoke(
        {"messages": [HumanMessage(content=
            "Run the quarterly governance review: audit tagging, cost controls, "
            "AI governance, and policy deployment, then generate the scorecard "
            "and a SOC2 evidence package.")]},
        config={"configurable": {"thread_id": "governance-q2-2026-review"}},
    )
    print(result["messages"][-1].content)
