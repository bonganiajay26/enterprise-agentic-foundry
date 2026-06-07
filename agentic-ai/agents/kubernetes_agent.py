"""
Kubernetes Agent — Universal Agentic DevOps Platform

Responsibilities:
- Diagnose cluster health (nodes, pods, events)
- Analyze resource utilization and suggest optimizations
- Review RBAC and security posture
- Validate Helm releases
- Generate cluster health reports
- Advise on scaling strategies (HPA, KEDA, VPA)
- Detect common Kubernetes misconfigurations
"""

from __future__ import annotations

import os
from typing import Annotated, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from agentic_ai.llm import get_chat_model
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict


class KubernetesState(TypedDict):
    messages: Annotated[list, add_messages]
    cluster_health: str
    issues_found: list[dict]
    audit_trail: list[dict]


@tool
def get_cluster_health(context: str = "production") -> dict:
    """Get overall cluster health: node status, system pod health, resource pressure."""
    return {
        "context": context,
        "nodes": {
            "total": 9,
            "ready": 8,
            "not_ready": 1,
            "node_issues": [{"name": "worker-3", "condition": "DiskPressure", "since": "2h"}],
        },
        "system_pods": {"total": 45, "running": 43, "failing": 2},
        "resource_utilization": {
            "avg_cpu_pct": 42.1,
            "avg_memory_pct": 61.3,
            "nodes_above_80pct_cpu": 0,
            "nodes_above_80pct_memory": 2,
        },
        "api_server_latency_ms": 45,
        "etcd_health": "healthy",
        "overall_health": "degraded",
    }


@tool
def get_failing_pods(
    namespace: str = "",
    max_results: int = 20,
) -> dict:
    """List all failing, pending, or crash-looping pods across the cluster."""
    return {
        "failing_pods": [
            {
                "namespace": "production",
                "name": "order-service-7d4f9c-xk2mp",
                "status": "CrashLoopBackOff",
                "restarts": 14,
                "last_state": "OOMKilled",
                "memory_limit": "256Mi",
                "recommendation": "Increase memory limit to 512Mi; container OOMKilled",
            }
        ],
        "pending_pods": [
            {
                "namespace": "ml-serving",
                "name": "model-server-5b9d7c-abc12",
                "status": "Pending",
                "reason": "Insufficient GPU resources",
                "pending_since": "45m",
                "recommendation": "Scale GPU node pool or check node selector labels",
            }
        ],
        "total_issues": 2,
    }


@tool
def analyze_rbac(namespace: str = "") -> dict:
    """Analyze RBAC configuration for over-privileged service accounts and roles."""
    return {
        "findings": [
            {
                "severity": "HIGH",
                "type": "over_privileged_service_account",
                "resource": "default/default",
                "issue": "Default service account has cluster-admin binding in 3 namespaces",
                "recommendation": "Create dedicated service accounts with least-privilege permissions",
            },
            {
                "severity": "MEDIUM",
                "type": "wildcard_verb_role",
                "resource": "production/developer-role",
                "issue": "Role has verbs: ['*'] on resource: secrets",
                "recommendation": "Restrict secret access to specific named secrets only",
            },
        ],
        "total_service_accounts": 34,
        "cluster_admin_bindings": 7,
        "wildcard_roles": 3,
    }


@tool
def get_resource_quotas_and_limits(namespace: str = "") -> dict:
    """Check namespace resource quotas and LimitRange policies."""
    return {
        "namespaces_without_quotas": ["staging", "dev", "ml-serving"],
        "namespaces_without_limitranges": ["staging", "dev"],
        "quota_violations": [],
        "recommendation": "Add ResourceQuota and LimitRange to all non-system namespaces",
    }


@tool
def check_pod_disruption_budgets(namespace: str = "production") -> dict:
    """Verify PodDisruptionBudgets exist for all critical deployments."""
    return {
        "deployments_without_pdb": [
            {"namespace": "production", "name": "email-service"},
            {"namespace": "production", "name": "notification-service"},
        ],
        "pdbs_with_zero_disruptions_allowed": [],
        "recommendation": "Add PDB with minAvailable: 1 for all production deployments",
    }


@tool
def analyze_node_pool_utilization(cloud: Literal["azure", "aws", "gcp"] = "azure") -> dict:
    """Analyze node pool utilization and Karpenter/autoscaler efficiency."""
    return {
        "node_pools": [
            {
                "name": "workloads",
                "nodes": 6,
                "avg_cpu_pct": 38.0,
                "avg_memory_pct": 55.0,
                "scale_up_events_24h": 3,
                "scale_down_events_24h": 1,
                "estimated_monthly_cost_usd": 2400.00,
                "recommendation": "Reduce min_nodes from 6 to 4; autoscaler can handle demand spikes",
            }
        ],
        "cluster_bin_packing_efficiency_pct": 61.0,
        "wasted_resources_pct": 39.0,
    }


@tool
def validate_helm_releases(namespace: str = "") -> dict:
    """Validate all Helm releases: check for failed, pending-upgrade, or outdated releases."""
    return {
        "releases": [
            {"name": "myapp-prod", "namespace": "production", "status": "deployed", "chart": "base-service-1.0.0", "healthy": True},
            {"name": "cert-manager", "namespace": "cert-manager", "status": "deployed", "chart": "cert-manager-v1.13.0", "healthy": True},
            {"name": "old-service", "namespace": "production", "status": "failed", "chart": "old-service-0.1.0", "healthy": False,
             "error": "timeout waiting for condition", "recommendation": "Rollback or redeploy"},
        ],
        "total_releases": 12,
        "failed_releases": 1,
        "outdated_charts": 2,
    }


SYSTEM_PROMPT = """You are the Kubernetes Agent for the Universal Agentic DevOps Platform.

Your responsibilities:
1. Diagnose cluster health problems quickly and accurately
2. Identify pod failures and provide root-cause analysis
3. Review RBAC for security violations (over-privileged accounts, wildcard roles)
4. Ensure namespace best practices: quotas, limit ranges, PDBs
5. Analyze node pool efficiency and autoscaling behavior
6. Validate Helm releases and detect configuration drift

Diagnostic approach:
- Start with cluster-wide health, then drill into specific issues
- Always include both the problem and the recommended fix
- Prioritize production issues over non-production
- OOMKilled: increase memory limits or find memory leak
- CrashLoopBackOff: check logs, recent config changes, dependency availability
- Pending pods: check node selectors, tolerations, resource availability

Security posture scoring (out of 100):
- Each missing PDB: -2 points
- Each namespace without quotas: -5 points
- Each over-privileged SA: -10 points
- Each wildcard role in production: -15 points
"""


def call_model(state: KubernetesState) -> dict:
    llm = get_chat_model(agent_name="kubernetes_agent", temperature=0)
    tools = [get_cluster_health, get_failing_pods, analyze_rbac,
             get_resource_quotas_and_limits, check_pod_disruption_budgets,
             analyze_node_pool_utilization, validate_helm_releases]
    response = llm.bind_tools(tools).invoke([SystemMessage(content=SYSTEM_PROMPT)] + state["messages"])
    return {"messages": [response]}


def should_continue(state: KubernetesState) -> Literal["tools", END]:
    last = state["messages"][-1]
    return "tools" if isinstance(last, AIMessage) and last.tool_calls else END


def build_kubernetes_agent() -> StateGraph:
    tools = [get_cluster_health, get_failing_pods, analyze_rbac,
             get_resource_quotas_and_limits, check_pod_disruption_budgets,
             analyze_node_pool_utilization, validate_helm_releases]
    graph = StateGraph(KubernetesState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=MemorySaver())


if __name__ == "__main__":
    agent = build_kubernetes_agent()
    state = {
        "messages": [HumanMessage(content=(
            "Give me a full cluster health report for the production cluster. "
            "Check for failing pods, RBAC issues, missing PDBs, and node utilization. "
            "Score our Kubernetes security posture and give me the top 5 fixes."
        ))],
        "cluster_health": "unknown",
        "issues_found": [],
        "audit_trail": [],
    }
    config = {"configurable": {"thread_id": "k8s-session-001"}}
    for chunk in agent.stream(state, config=config, stream_mode="values"):
        last = chunk["messages"][-1]
        if hasattr(last, "content") and last.content:
            print(f"\n{last.content}")
