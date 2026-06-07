"""
Architecture Agent — Universal Agentic DevOps Platform

Responsibilities:
- Analyze existing codebases for architecture patterns
- Generate Mermaid architecture diagrams
- Identify architectural anti-patterns and tech debt
- Recommend modernization paths (monolith → microservices, etc.)
- Review dependency graphs and coupling
- Generate ADRs (Architecture Decision Records)
- Advise on cloud-native migration strategies
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


class ArchitectureState(TypedDict):
    messages: Annotated[list, add_messages]
    architecture_style: str
    findings: list[dict]
    diagrams: list[str]
    audit_trail: list[dict]


@tool
def analyze_service_dependencies(
    repo_path: str = ".",
    language: Literal["nodejs", "python", "java", "go", "dotnet"] = "nodejs",
) -> dict:
    """Analyze inter-service dependencies, external API calls, and event subscriptions."""
    return {
        "services": [
            {
                "name": "api-gateway",
                "type": "BFF",
                "calls": ["user-service", "order-service", "product-service"],
                "protocols": ["HTTP/REST", "gRPC"],
                "coupling_score": "LOW",
            },
            {
                "name": "order-service",
                "type": "Domain",
                "calls": ["payment-service", "inventory-service", "notification-service"],
                "events_published": ["OrderCreated", "OrderUpdated"],
                "events_consumed": ["PaymentCompleted", "InventoryReserved"],
                "coupling_score": "HIGH",
                "concern": "Too many synchronous dependencies — consider event-driven decoupling",
            },
        ],
        "shared_databases": [
            {"database": "orders-db", "accessed_by": ["order-service", "reporting-service"],
             "concern": "Database sharing violates service autonomy"},
        ],
        "circular_dependencies": [],
        "architecture_style": "microservices",
    }


@tool
def generate_architecture_diagram(
    services: list[str],
    diagram_type: Literal["c4-context", "c4-container", "sequence", "deployment", "data-flow"],
    format: Literal["mermaid", "plantuml"] = "mermaid",
) -> dict:
    """Generate an architecture diagram in Mermaid or PlantUML format."""
    mermaid_diagram = """
flowchart TB
    subgraph EXTERNAL["External"]
        CLIENT[Web Browser / Mobile App]
        THIRDPARTY[Payment Gateway]
    end

    subgraph PLATFORM["Platform — Kubernetes"]
        GW[API Gateway :8080]
        subgraph SERVICES["Domain Services"]
            US[User Service]
            OS[Order Service]
            PS[Product Service]
            PAY[Payment Service]
        end
        subgraph DATA["Data Layer"]
            USDB[(Users DB)]
            OSDB[(Orders DB)]
            PSDB[(Products DB)]
            CACHE[(Redis Cache)]
            MQ[Event Bus — Kafka]
        end
    end

    CLIENT --> GW
    GW --> US & OS & PS
    OS --> PAY
    PAY --> THIRDPARTY
    US --> USDB
    OS --> OSDB & MQ
    PS --> PSDB & CACHE
    PAY --> MQ
"""
    return {
        "diagram_type": diagram_type,
        "format": format,
        "diagram": mermaid_diagram,
        "services_included": len(services),
    }


@tool
def assess_technical_debt(
    repo_path: str = ".",
    include_categories: list[str] = None,
) -> dict:
    """Assess technical debt across architecture, code quality, and operational dimensions."""
    return {
        "total_debt_score": 67,
        "categories": [
            {
                "category": "Architecture",
                "score": 55,
                "issues": [
                    "Shared database between order-service and reporting-service (high coupling)",
                    "Synchronous chain 4 services deep (order→inventory→warehouse→shipping) — cascading failure risk",
                    "No API versioning strategy — breaking changes break clients",
                ],
                "estimated_effort_days": 21,
            },
            {
                "category": "Code Quality",
                "score": 72,
                "issues": [
                    "Test coverage at 43% (target: 80%)",
                    "12 TODO/FIXME comments in payment service",
                    "3 deprecated dependency versions",
                ],
                "estimated_effort_days": 10,
            },
            {
                "category": "Operational Readiness",
                "score": 61,
                "issues": [
                    "No distributed tracing implemented",
                    "Health check endpoints return 200 even when DB is unreachable",
                    "No circuit breaker on external payment gateway calls",
                ],
                "estimated_effort_days": 8,
            },
        ],
        "priority_fixes": [
            "Decouple shared database — highest coupling risk",
            "Add circuit breaker to payment gateway — revenue impact",
            "Implement proper health checks — cascading failures",
        ],
    }


@tool
def generate_adr(
    decision_title: str,
    context: str,
    options: list[str],
    selected_option: str,
    rationale: str,
) -> dict:
    """Generate an Architecture Decision Record (ADR) document."""
    adr_content = f"""# ADR: {decision_title}

**Date:** 2026-06-06
**Status:** Accepted
**Deciders:** Architecture Team

## Context

{context}

## Options Considered

{chr(10).join(f"- {opt}" for opt in options)}

## Decision

**Selected:** {selected_option}

## Rationale

{rationale}

## Consequences

### Positive
- Documented decision for future team members
- Clear rationale prevents re-litigating the decision

### Negative
- Migration effort required
- Team learning curve

## Implementation Notes

See `architecture/` directory for implementation diagrams.
"""
    return {
        "title": decision_title,
        "filename": f"ADR-{decision_title.lower().replace(' ', '-')}.md",
        "content": adr_content,
        "status": "created",
    }


@tool
def recommend_modernization_path(
    current_architecture: Literal["monolith", "modular-monolith", "microservices", "serverless"],
    target_architecture: Literal["modular-monolith", "microservices", "serverless", "event-driven"],
    team_size: int = 10,
    timeline_months: int = 6,
) -> dict:
    """Recommend a phased modernization strategy."""
    return {
        "current": current_architecture,
        "target": target_architecture,
        "recommended_pattern": "Strangler Fig",
        "phases": [
            {
                "phase": 1,
                "duration_weeks": 4,
                "title": "Extract Authentication Service",
                "description": "Lowest risk, high value. Auth is well-bounded and independently deployable.",
                "risk": "LOW",
            },
            {
                "phase": 2,
                "duration_weeks": 6,
                "title": "Extract Order Service",
                "description": "Core business domain with clear bounded context.",
                "risk": "MEDIUM",
            },
            {
                "phase": 3,
                "duration_weeks": 8,
                "title": "Extract remaining bounded contexts",
                "description": "Products, Inventory, Notifications",
                "risk": "MEDIUM",
            },
        ],
        "anti_patterns_to_avoid": [
            "Distributed monolith — microservices with shared database",
            "Nano-services — too fine-grained, high network overhead",
            "Big-bang rewrite — high risk, high cost",
        ],
        "success_metrics": [
            "Independent deployability of each service",
            "No shared databases between services",
            "< 5 synchronous hops in any request chain",
        ],
    }


SYSTEM_PROMPT = """You are the Architecture Agent for the Universal Agentic DevOps Platform.

Your responsibilities:
1. Analyze codebases and identify the current architecture style and patterns
2. Generate clear, accurate Mermaid architecture diagrams
3. Identify architectural anti-patterns: shared databases, tight coupling, circular dependencies
4. Recommend modernization paths with phased, risk-aware approaches
5. Create Architecture Decision Records (ADRs) to document important choices
6. Assess technical debt across architectural, code, and operational dimensions

Principles you uphold:
- Single Responsibility: Each service owns its data
- Loose Coupling: Prefer events over synchronous chains
- High Cohesion: Related functionality stays together
- Evolvability: Architecture should support independent deployments
- Observability: Every service should be traceable

When analyzing architecture, always answer:
1. What style is this? (monolith, microservices, serverless, etc.)
2. What's the biggest architectural risk?
3. What one change would have the highest impact?

Always generate a Mermaid diagram as part of any architecture analysis.
"""


def call_model(state: ArchitectureState) -> dict:
    llm = get_chat_model(agent_name="architecture_agent", temperature=0)
    tools = [analyze_service_dependencies, generate_architecture_diagram,
             assess_technical_debt, generate_adr, recommend_modernization_path]
    response = llm.bind_tools(tools).invoke([SystemMessage(content=SYSTEM_PROMPT)] + state["messages"])
    return {"messages": [response]}


def should_continue(state: ArchitectureState) -> Literal["tools", END]:
    last = state["messages"][-1]
    return "tools" if isinstance(last, AIMessage) and last.tool_calls else END


def build_architecture_agent() -> StateGraph:
    tools = [analyze_service_dependencies, generate_architecture_diagram,
             assess_technical_debt, generate_adr, recommend_modernization_path]
    graph = StateGraph(ArchitectureState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=MemorySaver())
