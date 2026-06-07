"""
Infrastructure & Deployment Agent — Universal Agentic DevOps Platform

Combines the master-prompt's "Infrastructure Agent" and "Deployment Agent"
responsibilities (steps 6-7 of the Autonomous SDLC). They share a single
contract — "take validated artifacts and a target environment, converge
infrastructure to the desired state, then release the application onto it
with zero downtime" — so unifying them keeps plan/apply/deploy atomic and
prevents drift between "what we provisioned" and "what we deployed onto".

Responsibilities — Infrastructure:
- Run Terraform/OpenTofu/Bicep/CloudFormation plan & apply with mandatory
  human approval for any destructive change (`infra_deletion` — see
  remediation_agent's APPROVAL_REQUIRED matrix)
- Detect drift between desired (Git) and actual (cloud) state
- Validate against Checkov/Trivy IaC scanning before any apply

Responsibilities — Deployment:
- Execute GitOps-driven releases (ArgoCD sync) using blue-green / canary /
  rolling strategies appropriate to the service's risk profile
- Monitor rollout health in real time and trigger automatic rollback on
  SLO/error-rate regression
- Coordinate zero-downtime cutover (readiness gates, connection draining,
  PodDisruptionBudgets)
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


class InfraDeployState(TypedDict):
    messages: Annotated[list, add_messages]
    plan: dict
    deployment: dict
    audit_trail: list[dict]


@tool
def scan_iac_before_apply(module_path: str, tooling: str = "checkov") -> dict:
    """Run Checkov/Trivy against an IaC module BEFORE any plan/apply. A
    failing scan blocks the pipeline — this is a hard gate, not advisory."""
    return {
        "module_path": module_path, "tooling": tooling,
        "checks_passed": 142, "checks_failed": 1,
        "failed_checks": [
            {"id": "CKV_AZURE_109", "severity": "MEDIUM",
             "description": "Key Vault should have purge protection enabled",
             "resource": "azurerm_key_vault.platform"},
        ],
        "gate_status": "BLOCKED — 1 medium finding must be resolved or formally risk-accepted "
                       "by security_lead before apply proceeds",
        "remediation_route": "remediation_agent.classify_remediation(category='security_policy_change')",
    }


@tool
def plan_infrastructure_change(module_path: str, environment: str, backend: str = "terraform") -> dict:
    """Produce a Terraform/OpenTofu/Bicep/CloudFormation plan and classify
    its risk level (additive / mutating / destructive)."""
    return {
        "module_path": module_path, "environment": environment, "backend": backend,
        "resources_to_add": 3, "resources_to_change": 1, "resources_to_destroy": 0,
        "risk_classification": "additive",
        "plan_summary": "+3 to add (node pool, NSG rule, diagnostic setting), "
                        "~1 to change (tag update on resource group), 0 to destroy",
        "approval_required": False,
        "policy_note": "0 destroys -> auto-applyable per remediation_agent matrix "
                       "(category != infra_deletion). Any destroy count > 0 forces "
                       "APPROVAL_REQUIRED regardless of overall plan size.",
    }


@tool
def apply_infrastructure_change(plan_id: str, environment: str, destroy_count: int = 0) -> dict:
    """Apply a previously generated plan. REFUSES outright if destroy_count > 0
    and no `approval_reference` is supplied — infra deletion is ALWAYS gated,
    no exceptions, regardless of how the plan was classified upstream."""
    if destroy_count > 0:
        return {
            "status": "REFUSED",
            "reason": "Plan includes resource destruction. This requires a human-approved "
                      "change request via remediation_agent.open_change_request("
                      "category='infra_deletion'). Re-invoke with an approval_reference.",
        }
    return {
        "plan_id": plan_id, "environment": environment, "status": "applied",
        "duration_seconds": 94,
        "state_backend": "azurerm storage account (versioned, locked during apply)",
        "drift_check_post_apply": "clean — actual state matches new desired state",
        "audit": {"actor": "infrastructure_deployment_agent", "action": "apply",
                  "timestamp": datetime.datetime.utcnow().isoformat() + "Z"},
    }


@tool
def detect_infrastructure_drift(environment: str) -> dict:
    """Compare live cloud state against the Git-declared desired state and
    report any drift — the #1 cause of 'works in staging, fails in prod'."""
    return {
        "environment": environment,
        "drift_detected": True,
        "drifted_resources": [
            {"resource": "azurerm_kubernetes_cluster.platform", "field": "default_node_pool.node_count",
             "declared": 3, "actual": 5, "likely_cause": "manual scale-out during an incident, never reconciled"},
        ],
        "recommendation": "Reconcile via PR updating the declared value to match operational reality "
                          "(if intentional) OR re-apply to restore declared state (if accidental). "
                          "Route through remediation_agent for classification either way.",
        "drift_check_frequency": "every 6 hours via scheduled pipeline + on every apply",
    }


@tool
def execute_deployment(service: str, version: str, environment: str, strategy: str = "canary") -> dict:
    """Execute a GitOps-driven release using blue-green / canary / rolling.
    Strategy is chosen by the service's declared risk tier in catalog-info.yaml."""
    return {
        "service": service, "version": version, "environment": environment, "strategy": strategy,
        "stages": [
            {"stage": "sync to ArgoCD desired revision", "status": "complete"},
            {"stage": "canary 10% traffic shift", "status": "complete", "duration_s": 300,
             "slo_check": "p99 latency 142ms (budget 250ms) — PASS"},
            {"stage": "canary 50% traffic shift", "status": "complete", "duration_s": 300,
             "slo_check": "error rate 0.02% (budget 0.5%) — PASS"},
            {"stage": "full rollout 100%", "status": "complete", "duration_s": 180},
        ],
        "zero_downtime_controls": ["readinessProbe gating", "PodDisruptionBudget minAvailable=2",
                                    "connection draining 30s", "preStop hook"],
        "overall_status": "success",
        "rollback_ready": True,
    }


@tool
def monitor_rollout_and_auto_rollback(service: str, environment: str, watch_minutes: int = 30) -> dict:
    """Watch SLO burn-rate and error budgets post-deploy; trigger automatic
    rollback to the previous ArgoCD revision on regression."""
    return {
        "service": service, "environment": environment, "watch_window_minutes": watch_minutes,
        "slo_burn_rate": "0.04x (budget: 1.0x) — well within tolerance",
        "error_rate_trend": "stable at 0.018%",
        "decision": "NO ROLLBACK NEEDED — deployment confirmed healthy",
        "rollback_procedure_if_needed": "argocd app rollback <app> <prev-revision> "
                                        "&& kubectl rollout status deploy/<service> -n <environment>",
    }


SYSTEM_PROMPT = """You are the Infrastructure & Deployment Agent for the Universal
Agentic DevOps Platform — responsible for steps 6 and 7 of the Autonomous SDLC.

Hard rules:
1. ALWAYS run scan_iac_before_apply() before plan_infrastructure_change() —
   a failing IaC scan is a hard gate, never advisory.
2. ANY plan with destroy_count > 0 is APPROVAL_REQUIRED — apply_infrastructure_change
   will refuse outright without an approval_reference. No exceptions, ever —
   this mirrors remediation_agent's `infra_deletion` classification exactly.
3. ALWAYS check for drift before trusting "desired state" — detect_infrastructure_drift()
   first on any environment you haven't touched in the last 6 hours.
4. ALWAYS deploy with a strategy proportional to risk — canary for production,
   rolling for staging, direct apply for dev. Never skip the SLO-gated stages.
5. ALWAYS monitor post-deploy and be ready to auto-rollback — a deployment
   isn't "done" until monitor_rollout_and_auto_rollback confirms health.

Workflow:
1. detect_infrastructure_drift(environment)
2. scan_iac_before_apply(module_path) -> plan_infrastructure_change(...)
3. apply_infrastructure_change(...) [refuses if destructive + ungated]
4. execute_deployment(service, version, environment, strategy)
5. monitor_rollout_and_auto_rollback(service, environment)
"""


def call_model(state: InfraDeployState) -> dict:
    llm = get_chat_model(agent_name="infrastructure_deployment_agent", temperature=0)
    tools = [scan_iac_before_apply, plan_infrastructure_change, apply_infrastructure_change,
             detect_infrastructure_drift, execute_deployment, monitor_rollout_and_auto_rollback]
    llm_with_tools = llm.bind_tools(tools)
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def should_continue(state: InfraDeployState) -> Literal["tools", "__end__"]:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "__end__"


def build_infrastructure_deployment_agent():
    tools = [scan_iac_before_apply, plan_infrastructure_change, apply_infrastructure_change,
             detect_infrastructure_drift, execute_deployment, monitor_rollout_and_auto_rollback]
    workflow = StateGraph(InfraDeployState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "__end__": END})
    workflow.add_edge("tools", "agent")
    return workflow.compile(checkpointer=MemorySaver())


if __name__ == "__main__":
    agent = build_infrastructure_deployment_agent()
    result = agent.invoke(
        {"messages": [HumanMessage(content=
            "Provision the new node pool for payment-service in production "
            "(module: terraform/azure/aks-node-pool) and deploy v1.43.0 with "
            "a canary strategy once infrastructure is ready.")]},
        config={"configurable": {"thread_id": "infra-deploy-payment-1.43.0"}},
    )
    print(result["messages"][-1].content)
