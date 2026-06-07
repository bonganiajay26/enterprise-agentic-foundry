"""
Cost Optimization Agent — Universal Agentic DevOps Platform

Responsibilities:
- Analyze cloud spend across Azure/AWS/GCP
- Identify idle and oversized resources
- Generate rightsizing recommendations
- Track reserved instance/savings plan coverage
- Create cost anomaly reports
- Forecast monthly spend
- Generate FinOps executive summaries
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


class CostState(TypedDict):
    messages: Annotated[list, add_messages]
    total_monthly_spend: float
    top_cost_drivers: list[dict]
    recommendations: list[dict]
    audit_trail: list[dict]


@tool
def get_cloud_spend_summary(
    cloud: Literal["azure", "aws", "gcp", "all"],
    period: str = "current_month",
) -> dict:
    """Get total cloud spend breakdown by service and resource group/account."""
    return {
        "cloud": cloud,
        "period": period,
        "total_usd": 12450.30,
        "by_service": [
            {"service": "Kubernetes (AKS/EKS/GKE)", "cost_usd": 4200.00, "pct": 33.7},
            {"service": "Storage", "cost_usd": 1800.00, "pct": 14.5},
            {"service": "Networking/Bandwidth", "cost_usd": 1200.00, "pct": 9.6},
            {"service": "Databases", "cost_usd": 3500.00, "pct": 28.1},
            {"service": "AI/ML Compute", "cost_usd": 900.00, "pct": 7.2},
            {"service": "Other", "cost_usd": 850.30, "pct": 6.8},
        ],
        "month_over_month_change_pct": 8.3,
        "forecast_end_of_month_usd": 13200.00,
    }


@tool
def get_idle_resources(
    cloud: Literal["azure", "aws", "gcp"],
    resource_type: str = "all",
) -> dict:
    """Identify idle or underutilized resources (VMs, disks, IPs, load balancers)."""
    return {
        "cloud": cloud,
        "idle_resources": [
            {
                "type": "VirtualMachine",
                "name": "dev-vm-001",
                "region": "eastus",
                "monthly_cost_usd": 89.60,
                "cpu_avg_pct": 1.2,
                "last_active": "2026-04-15",
                "recommendation": "Terminate or schedule for dev hours only",
            },
            {
                "type": "UnattachedDisk",
                "name": "old-db-backup-disk",
                "region": "eastus",
                "size_gb": 512,
                "monthly_cost_usd": 51.20,
                "recommendation": "Snapshot and delete if no longer needed",
            },
            {
                "type": "UnusedLoadBalancer",
                "name": "staging-lb-old",
                "monthly_cost_usd": 22.40,
                "recommendation": "Delete — no healthy backends for 14 days",
            },
        ],
        "total_idle_cost_usd": 163.20,
        "annual_savings_potential_usd": 1958.40,
    }


@tool
def get_rightsizing_recommendations(
    cloud: Literal["azure", "aws", "gcp"],
    namespace: str = "",
) -> dict:
    """Get Kubernetes pod/node rightsizing recommendations based on actual usage vs requests/limits."""
    return {
        "cloud": cloud,
        "over_provisioned_pods": [
            {
                "namespace": "production",
                "deployment": "user-service",
                "container": "user-service",
                "current_cpu_request": "500m",
                "p95_actual_cpu": "85m",
                "recommended_cpu_request": "100m",
                "current_memory_request": "512Mi",
                "p95_actual_memory": "128Mi",
                "recommended_memory_request": "200Mi",
                "monthly_savings_usd": 45.60,
            }
        ],
        "over_provisioned_nodes": [
            {
                "node_pool": "workloads",
                "current_vm_size": "Standard_D8s_v5",
                "recommended_vm_size": "Standard_D4s_v5",
                "avg_cpu_utilization_pct": 22.1,
                "avg_memory_utilization_pct": 31.4,
                "monthly_savings_usd": 180.00,
                "nodes_affected": 4,
            }
        ],
        "total_monthly_savings_potential_usd": 945.60,
    }


@tool
def get_reserved_instance_coverage(
    cloud: Literal["azure", "aws", "gcp"],
) -> dict:
    """Check reserved instance / savings plan / committed use discount coverage."""
    return {
        "cloud": cloud,
        "on_demand_spend_usd": 8200.00,
        "reserved_coverage_pct": 41.0,
        "on_demand_pct": 59.0,
        "recommendations": [
            {
                "instance_type": "Standard_D4s_v5",
                "region": "eastus2",
                "quantity_recommended": 4,
                "term": "1-year",
                "upfront_cost_usd": 4800.00,
                "monthly_savings_usd": 520.00,
                "break_even_months": 9.2,
                "annual_savings_usd": 6240.00,
            }
        ],
        "total_annual_savings_if_optimized_usd": 18600.00,
    }


@tool
def get_cost_anomalies(
    cloud: Literal["azure", "aws", "gcp", "all"],
    threshold_pct: float = 20.0,
) -> dict:
    """Detect cost anomalies — services spending significantly more than expected."""
    return {
        "anomalies": [
            {
                "service": "Blob Storage",
                "cloud": "azure",
                "expected_daily_usd": 12.00,
                "actual_daily_usd": 89.40,
                "anomaly_pct": 645.0,
                "detected_at": "2026-06-05",
                "likely_cause": "Unused snapshot retention — 500GB snapshots accumulating",
                "recommended_action": "Review snapshot policy, set retention to 30 days",
            }
        ],
        "total_anomaly_spend_usd": 233.40,
    }


@tool
def generate_finops_report(
    period: str = "current_month",
    format: Literal["executive", "detailed", "team"] = "executive",
) -> dict:
    """Generate a FinOps report for the specified period and audience."""
    return {
        "period": period,
        "format": format,
        "total_spend_usd": 12450.30,
        "budget_usd": 15000.00,
        "budget_utilization_pct": 83.0,
        "vs_last_month_pct": 8.3,
        "top_3_actions": [
            "Rightsize over-provisioned node pools: save $720/month",
            "Purchase reserved instances for baseline compute: save $520/month",
            "Clean up idle resources: save $163/month",
        ],
        "total_optimization_potential_usd": 1403.00,
        "report_url": f"https://backstage.your-domain.com/finops/{period}",
    }


SYSTEM_PROMPT = """You are the Cost Optimization Agent for the Universal Agentic DevOps Platform.

Your responsibilities:
1. Analyze total cloud spend and identify the top cost drivers
2. Find idle, oversized, and wasteful resources
3. Recommend Kubernetes pod and node rightsizing
4. Optimize reserved instance / savings plan coverage
5. Detect cost anomalies before they become large bills
6. Generate actionable FinOps reports with ROI calculations

Communication style:
- Always include dollar amounts and percentages
- Prioritize recommendations by annual savings potential (highest first)
- Calculate break-even periods for reserved instance investments
- Express urgency based on: anomaly size, budget burn rate, month-end forecast

Thresholds:
- Cost anomaly > 50% above baseline: Immediate alert
- Budget utilization > 90%: Warning
- Reserved instance coverage < 40%: High priority recommendation
- Idle resource > 30 days: Flag for termination
"""


def call_model(state: CostState) -> dict:
    llm = get_chat_model(agent_name="cost_optimization_agent", temperature=0)
    tools = [
        get_cloud_spend_summary,
        get_idle_resources,
        get_rightsizing_recommendations,
        get_reserved_instance_coverage,
        get_cost_anomalies,
        generate_finops_report,
    ]
    response = llm.bind_tools(tools).invoke([SystemMessage(content=SYSTEM_PROMPT)] + state["messages"])
    return {"messages": [response]}


def should_continue(state: CostState) -> Literal["tools", END]:
    last = state["messages"][-1]
    return "tools" if isinstance(last, AIMessage) and last.tool_calls else END


def build_cost_agent() -> StateGraph:
    tools = [
        get_cloud_spend_summary, get_idle_resources, get_rightsizing_recommendations,
        get_reserved_instance_coverage, get_cost_anomalies, generate_finops_report,
    ]
    graph = StateGraph(CostState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=MemorySaver())


if __name__ == "__main__":
    agent = build_cost_agent()
    state = {
        "messages": [HumanMessage(content=(
            "Give me a comprehensive cost analysis for this month across all clouds. "
            "Identify idle resources, rightsizing opportunities, and reserved instance gaps. "
            "Prioritize the top 5 actions by annual savings. Generate an executive FinOps report."
        ))],
        "total_monthly_spend": 0.0,
        "top_cost_drivers": [],
        "recommendations": [],
        "audit_trail": [],
    }
    config = {"configurable": {"thread_id": "cost-session-001"}}
    for chunk in agent.stream(state, config=config, stream_mode="values"):
        last = chunk["messages"][-1]
        if hasattr(last, "content") and last.content:
            print(f"\n{last.content}")
