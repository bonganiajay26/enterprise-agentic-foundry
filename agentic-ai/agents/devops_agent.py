"""
DevOps Agent — Universal Agentic DevOps Platform

Responsibilities:
- Analyze CI/CD pipeline failures and suggest fixes
- Review Helm releases and identify drift
- Trigger deployments with approval workflows
- Generate deployment summaries and post to Slack
- Monitor rollout health and auto-rollback on degradation
"""

from __future__ import annotations

import json
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

# ─── Agent State ──────────────────────────────────────────────────────
class DevOpsState(TypedDict):
    messages: Annotated[list, add_messages]
    current_task: str
    environment: str
    requires_approval: bool
    audit_trail: list[dict]


# ─── Tools ────────────────────────────────────────────────────────────
@tool
def get_pipeline_status(pipeline_id: str, ci_provider: str = "github") -> dict:
    """Get the current status of a CI/CD pipeline run."""
    # In production: call GitHub/Azure DevOps/GitLab API
    return {
        "pipeline_id": pipeline_id,
        "status": "failed",
        "failed_step": "trivy-scan",
        "error": "CRITICAL vulnerability CVE-2024-12345 in base image node:20-alpine",
        "duration_seconds": 142,
    }


@tool
def get_kubernetes_deployment_status(
    namespace: str,
    deployment_name: str,
    cluster_context: str = "production",
) -> dict:
    """Get the rollout status of a Kubernetes deployment."""
    # In production: call k8s API via kubeconfig or in-cluster config
    return {
        "deployment": deployment_name,
        "namespace": namespace,
        "desired_replicas": 3,
        "ready_replicas": 2,
        "available_replicas": 2,
        "conditions": [
            {"type": "Available", "status": "True"},
            {"type": "Progressing", "status": "True", "reason": "ReplicaSetUpdated"},
        ],
        "rollout_history": ["v1.2.3", "v1.2.4", "v1.2.5-current"],
    }


@tool
def rollback_deployment(
    namespace: str,
    deployment_name: str,
    revision: int = 0,
    reason: str = "",
) -> dict:
    """Roll back a Kubernetes deployment to a previous revision. Requires approval for production."""
    return {
        "action": "rollback",
        "deployment": deployment_name,
        "namespace": namespace,
        "target_revision": revision,
        "status": "initiated",
        "message": f"Rollback initiated: {reason}",
    }


@tool
def get_helm_release_status(
    release_name: str,
    namespace: str,
) -> dict:
    """Get the status of a Helm release."""
    return {
        "release": release_name,
        "namespace": namespace,
        "status": "deployed",
        "chart": "base-service-1.0.0",
        "app_version": "1.2.5",
        "last_deployed": "2026-06-06T10:00:00Z",
        "resources": {
            "Deployment": 1,
            "Service": 1,
            "HPA": 1,
            "ServiceMonitor": 1,
        },
    }


@tool
def check_service_health(
    service_name: str,
    namespace: str,
    check_type: Literal["http", "metrics", "logs"] = "metrics",
) -> dict:
    """Check service health via metrics, HTTP probes, or recent error logs."""
    return {
        "service": service_name,
        "health": "degraded",
        "error_rate_5m": 0.03,  # 3% error rate
        "p95_latency_ms": 850,
        "p99_latency_ms": 2100,
        "slo_status": "burning_fast",
        "error_budget_remaining_percent": 12.5,
    }


@tool
def trigger_deployment(
    image_tag: str,
    service_name: str,
    environment: str,
    strategy: Literal["rolling", "canary", "blue-green"] = "canary",
    canary_weight: int = 10,
) -> dict:
    """Trigger a deployment. Non-production deployments are automatic; production requires approval."""
    return {
        "deployment_id": "deploy-abc123",
        "service": service_name,
        "image_tag": image_tag,
        "environment": environment,
        "strategy": strategy,
        "status": "pending_approval" if environment == "production" else "triggered",
        "approval_url": f"https://backstage.your-domain.com/approvals/deploy-abc123",
    }


@tool
def post_slack_notification(
    channel: str,
    message: str,
    severity: Literal["info", "warning", "critical"] = "info",
) -> dict:
    """Post a notification to a Slack channel."""
    # In production: call Slack API
    emoji = {"info": ":white_check_mark:", "warning": ":warning:", "critical": ":red_circle:"}
    return {
        "status": "sent",
        "channel": channel,
        "message": f"{emoji[severity]} {message}",
    }


# ─── LLM Configuration ────────────────────────────────────────────────
def create_llm():
    return AzureChatOpenAI(
        azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version="2025-01-01-preview",
        temperature=0,
        streaming=True,
    )


# ─── System Prompt ────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are the DevOps Agent for the Universal Agentic DevOps Platform.

Your responsibilities:
1. Diagnose CI/CD pipeline failures and provide actionable fixes
2. Monitor Kubernetes deployments and detect health degradation
3. Recommend and execute rollbacks when error budgets are burning fast
4. Trigger deployments with appropriate strategy (canary for production)
5. Keep stakeholders informed via Slack notifications

Operating principles:
- ALWAYS check service health before recommending production deployments
- NEVER rollback production without explicit human approval
- Log all actions to the audit trail
- Prefer canary deployments for production
- Trigger Slack notifications for all critical events
- When error budget < 10%, escalate to Critical and require PagerDuty page

Available environments: dev, staging, production
Production changes require approval: YES
Max autonomous canary weight: 10% (must request approval to increase)
"""


# ─── Graph Nodes ──────────────────────────────────────────────────────
def should_continue(state: DevOpsState) -> Literal["tools", "require_approval", END]:
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage):
        return END
    if not last_message.tool_calls:
        return END
    # Check if any tool requires approval
    for call in last_message.tool_calls:
        if call["name"] == "trigger_deployment" and "production" in str(call["args"]):
            return "require_approval"
        if call["name"] == "rollback_deployment" and "production" in str(call["args"]):
            return "require_approval"
    return "tools"


def call_model(state: DevOpsState) -> dict:
    llm = create_llm()
    tools = [
        get_pipeline_status,
        get_kubernetes_deployment_status,
        rollback_deployment,
        get_helm_release_status,
        check_service_health,
        trigger_deployment,
        post_slack_notification,
    ]
    llm_with_tools = llm.bind_tools(tools)
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    # Append to audit trail
    audit_entry = {
        "timestamp": "now",
        "agent": "devops",
        "action": response.content[:100] if response.content else "tool_call",
        "tool_calls": [c["name"] for c in (response.tool_calls or [])],
    }
    return {
        "messages": [response],
        "audit_trail": state.get("audit_trail", []) + [audit_entry],
    }


def require_approval_node(state: DevOpsState) -> dict:
    """Pause execution and require human approval."""
    return {
        "messages": [
            AIMessage(
                content=(
                    "⚠️ **Human Approval Required**\n\n"
                    "This action affects the production environment. "
                    "Please review and approve at: https://backstage.your-domain.com/approvals\n\n"
                    "I will resume once approved."
                )
            )
        ],
        "requires_approval": True,
    }


# ─── Build Graph ──────────────────────────────────────────────────────
def build_devops_agent() -> StateGraph:
    tools = [
        get_pipeline_status,
        get_kubernetes_deployment_status,
        rollback_deployment,
        get_helm_release_status,
        check_service_health,
        trigger_deployment,
        post_slack_notification,
    ]
    tool_node = ToolNode(tools)

    graph = StateGraph(DevOpsState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", tool_node)
    graph.add_node("require_approval", require_approval_node)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")
    graph.add_edge("require_approval", END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer, interrupt_before=["require_approval"])


# ─── Entry Point ──────────────────────────────────────────────────────
if __name__ == "__main__":
    agent = build_devops_agent()

    # Example: diagnose a failing pipeline
    initial_state = {
        "messages": [
            HumanMessage(
                content=(
                    "Pipeline #1234 failed in the trivy-scan step for the payment-service. "
                    "The service is currently running in production on v1.2.4. "
                    "Please diagnose the failure and tell me if we need to take any action."
                )
            )
        ],
        "current_task": "diagnose_pipeline_failure",
        "environment": "production",
        "requires_approval": False,
        "audit_trail": [],
    }

    config = {"configurable": {"thread_id": "devops-session-001"}}
    for chunk in agent.stream(initial_state, config=config, stream_mode="values"):
        last_message = chunk["messages"][-1]
        if hasattr(last_message, "content") and last_message.content:
            print(f"\n{last_message.content}")
