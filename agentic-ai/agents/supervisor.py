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
from langchain_openai import AzureChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class SupervisorState(TypedDict):
    messages: Annotated[list, add_messages]
    next_agent: str
    session_context: dict
    completed_tasks: list[str]


AGENTS = ["devops", "security", "cost", "incident", "architecture", "documentation"]

SYSTEM_PROMPT = f"""You are the Supervisor Agent for the Universal Agentic DevOps Platform.

Your role is to understand the user's request and route it to the correct specialized agent.

Available agents:
- devops: CI/CD pipelines, Kubernetes deployments, Helm releases, rollbacks, deploy triggers
- security: Vulnerability scanning, IaC security, Falco alerts, secret rotation, compliance reports
- cost: Cloud cost analysis, rightsizing, reserved instances, FinOps reports, budget alerts
- incident: Active incident management, post-mortems, runbook execution, PagerDuty integration
- architecture: Architecture reviews, diagram generation, dependency analysis, tech debt assessment
- documentation: TechDocs generation, runbook creation, API docs, ADR writing

Routing rules:
1. Analyze the user's intent carefully
2. Select EXACTLY ONE agent from: {AGENTS}
3. If the request spans multiple domains, pick the most critical one first
4. If it's a casual conversation or greeting, handle it yourself without routing
5. After routing, summarize what the sub-agent accomplished

Always respond with which agent you're routing to and why (one sentence).
"""


def supervisor_node(state: SupervisorState) -> dict:
    llm = AzureChatOpenAI(
        azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version="2025-01-01-preview",
        temperature=0,
    )

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


def placeholder_agent_node(agent_name: str):
    """Factory for placeholder agent nodes (cost, incident, architecture, documentation)."""
    def node(state: SupervisorState) -> dict:
        return {
            "messages": [
                AIMessage(
                    content=(
                        f"[{agent_name.title()} Agent] Task received. "
                        f"Full {agent_name} agent implementation available in "
                        f"agentic-ai/agents/{agent_name}_agent.py"
                    )
                )
            ],
            "completed_tasks": state.get("completed_tasks", []) + [agent_name],
        }
    node.__name__ = f"{agent_name}_node"
    return node


def build_supervisor() -> StateGraph:
    graph = StateGraph(SupervisorState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("devops", devops_node)
    graph.add_node("security", security_node)
    graph.add_node("cost", placeholder_agent_node("cost"))
    graph.add_node("incident", placeholder_agent_node("incident"))
    graph.add_node("architecture", placeholder_agent_node("architecture"))
    graph.add_node("documentation", placeholder_agent_node("documentation"))

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_to_agent,
        {
            "devops": "devops",
            "security": "security",
            "cost": "cost",
            "incident": "incident",
            "architecture": "architecture",
            "documentation": "documentation",
            END: END,
        },
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
