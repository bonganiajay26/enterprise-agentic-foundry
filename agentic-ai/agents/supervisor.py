"""
Supervisor Agent — Universal Agentic DevOps Platform

Orchestrates specialized sub-agents (DevOps, Security, Cost, Incident, Architecture).
Routes tasks to the appropriate agent based on intent classification.
Maintains session-level context and cross-agent state.
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
from typing_extensions import TypedDict


class SupervisorState(TypedDict):
    messages: Annotated[list, add_messages]
    next_agent: str
    session_context: dict
    completed_tasks: list[str]


AGENTS = [
    "devops", "security", "cost", "incident", "architecture", "documentation",
    "kubernetes", "performance",
    # Autonomous-SDLC agents (see docs/autonomous-sdlc.md for the full loop)
    "repo_analysis", "build_test", "infrastructure_deployment",
    "monitoring_rca", "remediation", "governance",
]

SYSTEM_PROMPT = f"""You are the Supervisor Agent for the Universal Agentic DevOps Platform.

Your role is to understand the user's request and route it to the correct specialized agent.

Available agents:
- devops: CI/CD pipelines, Kubernetes deployments, Helm releases, rollbacks, deploy triggers
- security: Vulnerability scanning, IaC security, Falco alerts, secret rotation, compliance reports
- cost: Cloud cost analysis, rightsizing, reserved instances, FinOps reports, budget alerts
- incident: Active incident management, post-mortems, runbook execution, PagerDuty integration
- architecture: Architecture reviews, diagram generation, dependency analysis, tech debt assessment
- documentation: TechDocs generation, runbook creation, API docs, ADR writing
- kubernetes: Cluster health, RBAC review, resource optimization, Helm validation
- performance: Query/latency analysis, load-test planning, capacity recommendations
- repo_analysis: Step 1 of the autonomous SDLC — analyze any repo/ZIP/folder/live
  environment, inventory it, generate current-state Mermaid diagrams, list unknowns
- build_test: Steps 3-4 — trigger builds, classify failures, run test suites,
  enforce coverage gates, quarantine flaky tests
- infrastructure_deployment: Steps 6-7 — Terraform/OpenTofu plan & apply (with a
  hard gate on any destructive change), GitOps deployments, drift detection,
  zero-downtime rollout monitoring with auto-rollback
- monitoring_rca: Steps 8-14 — configure observability for new services,
  evaluate SLO burn rates, detect anomalies, correlate logs/metrics/traces,
  and produce root-cause findings via structured 5-Whys analysis
- remediation: Steps 15-17 — classify a fix as AUTOMATIC or APPROVAL_REQUIRED
  per the canonical risk matrix, apply safe fixes or open gated change requests,
  and write the docs/issues/ record for every remediation
- governance: Continuous — audit tagging/cost/security-policy/AI-governance
  compliance and produce the executive Governance Scorecard

Routing rules:
1. Analyze the user's intent carefully
2. Select EXACTLY ONE agent from: {AGENTS}
3. If the request spans multiple domains, pick the most critical one first —
   for end-to-end "analyze and fix X" requests, prefer repo_analysis first
   (it inventories and hands off to the right specialists downstream)
4. If it's a casual conversation or greeting, handle it yourself without routing
5. After routing, summarize what the sub-agent accomplished

Always respond with which agent you're routing to and why (one sentence).
"""


def supervisor_node(state: SupervisorState) -> dict:
    llm = get_chat_model(agent_name="supervisor_agent", temperature=0)

    # Build routing prompt
    routing_system = SYSTEM_PROMPT + (
        f"\n\nCurrent session context: {state.get('session_context', {})}"
        f"\nCompleted tasks: {state.get('completed_tasks', [])}"
        "\n\nRespond with a JSON object: "
        '{"next": "<agent_name>", "reason": "<one sentence>", "response": "<direct response if no routing>"}'
    )

    messages = [SystemMessage(content=routing_system)] + state["messages"]
    response = llm.invoke(messages)

    # Parse routing decision
    try:
        import json
        content = response.content
        # Extract JSON from response
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            decision = json.loads(content[start:end])
            next_agent = decision.get("next", "devops")
            reason = decision.get("reason", "")
        else:
            next_agent = "devops"
            reason = "Default routing"
    except Exception:
        next_agent = "devops"
        reason = "Parse error — defaulting to devops agent"

    routing_message = AIMessage(
        content=f"Routing to **{next_agent}** agent: {reason}"
    )

    return {
        "messages": [routing_message],
        "next_agent": next_agent,
    }


def route_to_agent(state: SupervisorState) -> str:
    next_agent = state.get("next_agent", END)
    if next_agent not in AGENTS:
        return END
    return next_agent


def devops_node(state: SupervisorState) -> dict:
    """Delegate to DevOps Agent."""
    from agentic_ai.agents.devops_agent import build_devops_agent
    agent = build_devops_agent()
    sub_state = {
        "messages": state["messages"][-3:],  # last 3 messages for context
        "current_task": "delegated_from_supervisor",
        "environment": state["session_context"].get("environment", "unknown"),
        "requires_approval": False,
        "audit_trail": [],
    }
    config = {"configurable": {"thread_id": f"devops-{id(state)}"}}
    result = agent.invoke(sub_state, config=config)
    return {
        "messages": result["messages"][-1:],
        "completed_tasks": state.get("completed_tasks", []) + ["devops"],
    }


def security_node(state: SupervisorState) -> dict:
    """Delegate to Security Agent."""
    from agentic_ai.agents.security_agent import build_security_agent
    agent = build_security_agent()
    sub_state = {
        "messages": state["messages"][-3:],
        "findings": [],
        "risk_level": "unknown",
        "requires_immediate_action": False,
        "audit_trail": [],
    }
    config = {"configurable": {"thread_id": f"security-{id(state)}"}}
    result = agent.invoke(sub_state, config=config)
    return {
        "messages": result["messages"][-1:],
        "completed_tasks": state.get("completed_tasks", []) + ["security"],
    }


# Maps a routable agent name to (module_path, builder_function_name) for
# agents whose file/builder names diverge from the simple `<name>_agent.py`
# convention (combined agents from the autonomous-SDLC batch). Anything not
# listed here is assumed to live at `agentic_ai.agents.<name>_agent` with a
# `build_<name>_agent` builder.
AGENT_MODULE_OVERRIDES: dict[str, tuple[str, str]] = {
    "repo_analysis": ("agentic_ai.agents.repo_analysis_agent", "build_repo_analysis_agent"),
    "build_test": ("agentic_ai.agents.build_test_agent", "build_build_test_agent"),
    "infrastructure_deployment": ("agentic_ai.agents.infrastructure_deployment_agent", "build_infrastructure_deployment_agent"),
    "monitoring_rca": ("agentic_ai.agents.monitoring_rca_agent", "build_monitoring_rca_agent"),
    "remediation": ("agentic_ai.agents.remediation_agent", "build_remediation_agent"),
    "governance": ("agentic_ai.agents.governance_agent", "build_governance_agent"),
    "kubernetes": ("agentic_ai.agents.kubernetes_agent", "build_kubernetes_agent"),
    "performance": ("agentic_ai.agents.performance_agent", "build_performance_agent"),
    "cost": ("agentic_ai.agents.cost_agent", "build_cost_agent"),
    "incident": ("agentic_ai.agents.incident_agent", "build_incident_agent"),
    "architecture": ("agentic_ai.agents.architecture_agent", "build_architecture_agent"),
    "documentation": ("agentic_ai.agents.documentation_agent", "build_documentation_agent"),
}


def delegating_agent_node(agent_name: str):
    """Factory for fully-wired delegating nodes covering every agent in
    AGENT_MODULE_OVERRIDES (and, by convention, any `<name>_agent` module).
    Lazily imports + builds the sub-agent, forwards the last 3 messages of
    context, and folds the final response back into supervisor state —
    mirroring devops_node/security_node exactly so all agents are first-class.

    Falls back to a stub response if the module/builder can't be resolved
    (e.g. during incremental rollout of a brand-new agent) rather than
    crashing the whole supervisor graph.
    """
    import importlib

    module_path, builder_name = AGENT_MODULE_OVERRIDES.get(
        agent_name, (f"agentic_ai.agents.{agent_name}_agent", f"build_{agent_name}_agent")
    )

    def node(state: SupervisorState) -> dict:
        try:
            module = importlib.import_module(module_path)
            builder = getattr(module, builder_name)
            agent = builder()
            sub_state = {
                "messages": state["messages"][-3:],
                "audit_trail": [],
            }
            config = {"configurable": {"thread_id": f"{agent_name}-{id(state)}"}}
            result = agent.invoke(sub_state, config=config)
            return {
                "messages": result["messages"][-1:],
                "completed_tasks": state.get("completed_tasks", []) + [agent_name],
            }
        except Exception as exc:  # noqa: BLE001 — keep the supervisor graph alive
            return {
                "messages": [AIMessage(content=
                    f"[{agent_name.title()} Agent] Delegation failed ({exc}). "
                    f"Implementation: {module_path}.{builder_name}()")],
                "completed_tasks": state.get("completed_tasks", []) + [f"{agent_name}_failed"],
            }

    node.__name__ = f"{agent_name}_node"
    return node


def build_supervisor() -> StateGraph:
    graph = StateGraph(SupervisorState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("devops", devops_node)
    graph.add_node("security", security_node)
    for agent_name in AGENTS:
        if agent_name in ("devops", "security"):
            continue
        graph.add_node(agent_name, delegating_agent_node(agent_name))

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_to_agent,
        {**{agent: agent for agent in AGENTS}, END: END},
    )
    # All agents return to supervisor for follow-up
    for agent in AGENTS:
        graph.add_edge(agent, END)

    return graph.compile(checkpointer=MemorySaver())


if __name__ == "__main__":
    supervisor = build_supervisor()
    config = {"configurable": {"thread_id": "supervisor-demo-001"}}

    conversations = [
        "Our payment-service CI pipeline is failing. Can you investigate and fix it?",
        "Run a security scan on the payment-service container image v1.2.5",
        "What's our current cloud spend this month and are there optimization opportunities?",
    ]

    state = {
        "messages": [],
        "next_agent": "",
        "session_context": {"environment": "production", "team": "platform"},
        "completed_tasks": [],
    }

    for message in conversations:
        print(f"\n{'='*60}")
        print(f"USER: {message}")
        print('='*60)
        state["messages"].append(HumanMessage(content=message))
        result = supervisor.invoke(state, config=config)
        state = result
        last = result["messages"][-1]
        if hasattr(last, "content"):
            print(f"PLATFORM: {last.content}")
