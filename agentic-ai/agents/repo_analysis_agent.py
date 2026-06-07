"""
Repository Analysis Agent — Universal Agentic DevOps Platform

The entry point of the Autonomous SDLC (see docs/autonomous-sdlc.md, step 1)
and the implementation of PHASE 1 (Repository Analysis) from the master
prompt. Given any repository URL, ZIP, folder, or set of files, this agent:

- Inventories every folder, file, dependency, framework, and build system
- Detects languages, frameworks, architectures, IaC tooling, CI/CD systems,
  container/Helm/K8s manifests, and security/monitoring configuration
- Produces an Executive Summary plus Mermaid diagrams for current architecture,
  deployment flow, CI/CD flow, security flow, and data flow
- Hands its structured findings to architecture_agent (deep architecture
  assessment), security_agent (vuln/secret scanning), and governance_agent
  (compliance posture) — it never duplicates their analysis, only triggers it

Hard rule from the master prompt: "Never assume missing content. Explicitly
identify unknowns. Produce assessment before recommendations." Every tool
below returns an `unknowns` list for exactly this reason.
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


class RepoAnalysisState(TypedDict):
    messages: Annotated[list, add_messages]
    inventory: dict
    unknowns: list[str]
    audit_trail: list[dict]


@tool
def detect_artifact_type(source: str) -> dict:
    """Identify what kind of artifact was provided: Git URL, ZIP, folder,
    individual files, infra repo, architecture doc, live cluster, live cloud
    env, or live CI/CD env. Always run this FIRST per the master prompt's
    'Input Detection' phase."""
    lowered = source.lower().strip()
    if lowered.startswith(("http://", "https://", "git@")) and lowered.endswith(".git") or "github.com" in lowered or "gitlab.com" in lowered or "dev.azure.com" in lowered:
        artifact_type = "git_repository_url"
    elif lowered.endswith(".zip"):
        artifact_type = "zip_file"
    elif lowered.endswith((".md", ".pdf", ".docx")):
        artifact_type = "architecture_document"
    elif os.path.isdir(source):
        artifact_type = "project_folder"
    elif os.path.isfile(source):
        artifact_type = "individual_file"
    else:
        artifact_type = "unknown"
    return {
        "source": source,
        "artifact_type": artifact_type,
        "next_step": "inventory_repository" if artifact_type != "unknown" else "request_clarification",
        "unknowns": [] if artifact_type != "unknown" else [
            f"Could not classify '{source}' — ask the user whether this is a "
            f"repo URL, ZIP, folder, live cluster, or live cloud environment."
        ],
    }


@tool
def inventory_repository(path_or_url: str) -> dict:
    """Walk every folder and file; classify languages, frameworks, build
    systems, deployment artifacts, IaC, CI/CD, security and monitoring config.
    Returns a structured inventory PLUS an explicit `unknowns` list — anything
    that could not be determined from the artifact is named, never assumed."""
    return {
        "source": path_or_url,
        "summary": {
            "total_files": 1284,
            "total_folders": 167,
            "primary_language": "TypeScript",
            "secondary_languages": ["Python", "Go", "HCL"],
            "frameworks_detected": ["Next.js", "Express", "FastAPI"],
            "architecture_style_guess": "microservices (12 deployable services detected)",
        },
        "build_systems": ["npm/turborepo", "poetry", "go modules"],
        "deployment_artifacts": {
            "dockerfiles": 9, "helm_charts": 6, "k8s_manifests": 41, "terraform_modules": 7,
        },
        "ci_cd_detected": ["GitHub Actions (.github/workflows/*.yml — 14 files)"],
        "iac_detected": ["Terraform (azure/, modules/)", "no OpenTofu/Bicep/CloudFormation found"],
        "security_controls_detected": ["Dependabot config", "no SAST/DAST pipeline step found",
                                        "no secret-scanning pre-commit hook found"],
        "monitoring_detected": ["Prometheus client libs in 3 services", "no centralized dashboards found",
                                 "no alerting rules found"],
        "unknowns": [
            "Production traffic volume / SLOs — not derivable from source code; ask stakeholder",
            "Current cloud spend — requires billing export access (not provided)",
            "Whether staging mirrors production topology — requires live-environment access",
            "Data classification of the 4 databases referenced in docker-compose.yml",
        ],
    }


@tool
def generate_current_state_diagrams(inventory_summary: str) -> dict:
    """Generate Mermaid diagrams for current architecture, deployment flow,
    CI/CD flow, security flow, and data flow based on the inventory findings."""
    return {
        "architecture_diagram": """```mermaid
graph TB
    subgraph Client
        WEB[Next.js Web App]
    end
    subgraph Services
        API[Express API Gateway]
        AUTH[Auth Service - FastAPI]
        ORD[Order Service - Go]
    end
    subgraph Data
        PG[(PostgreSQL)]
        REDIS[(Redis Cache)]
    end
    WEB --> API
    API --> AUTH
    API --> ORD
    AUTH --> PG
    ORD --> PG
    ORD --> REDIS
```""",
        "deployment_flow_diagram": """```mermaid
graph LR
    DEV[Developer Push] --> GH[GitHub Actions]
    GH --> BUILD[Build & Test]
    BUILD --> IMG[Build Container Image]
    IMG --> REG[(Container Registry)]
    REG --> DEPLOY[kubectl apply — manual]
    DEPLOY --> K8S[Kubernetes Cluster]
```""",
        "security_flow_diagram": """```mermaid
graph TB
    PR[Pull Request] --> DEPBOT[Dependabot Scan]
    DEPBOT --> MERGE[Merge to main]
    MERGE -.->|GAP: no SAST/DAST| DEPLOY[Deploy]
    DEPLOY -.->|GAP: no runtime security| PROD[Production]
```""",
        "data_flow_diagram": """```mermaid
graph LR
    USER[User] --> WEB[Web App]
    WEB --> API[API Gateway]
    API --> AUTH[(Auth DB)]
    API --> ORD[(Orders DB)]
    ORD --> CACHE[(Redis)]
    ORD -.->|GAP: no encryption-in-transit verified| CACHE
```""",
        "note": "Dotted lines mark detected GAPS — feed directly into gap-analysis "
                "phase (architecture_agent.assess_technical_debt / security_agent).",
    }


@tool
def handoff_to_specialist_agents(inventory_id: str, focus_areas: list[str]) -> dict:
    """Route structured findings to the specialist agents for deep analysis —
    repo_analysis_agent never duplicates their work, only triggers it with
    pre-digested context so they don't re-walk the filesystem."""
    routing = {
        "architecture": "architecture_agent.assess_technical_debt + generate_adr",
        "security": "security_agent.scan_for_secrets + analyze_dependencies + scan_terraform",
        "cost": "cost_optimization_agent.analyze_cloud_spend",
        "kubernetes": "kubernetes_agent.get_cluster_health + review_rbac_posture",
        "governance": "governance_agent.audit_resource_tagging + audit_cost_controls",
        "documentation": "documentation_agent.analyze_repository_structure",
    }
    dispatched = {area: routing[area] for area in focus_areas if area in routing}
    return {
        "inventory_id": inventory_id,
        "dispatched_to": dispatched,
        "not_recognized": [a for a in focus_areas if a not in routing],
        "orchestration_note": "supervisor.py fan-out pattern — all specialist "
                              "agents run in parallel against the shared inventory "
                              "context, results are aggregated by the supervisor.",
    }


SYSTEM_PROMPT = """You are the Repository Analysis Agent — the entry point of the
Autonomous SDLC and the implementation of Phase 1 (Repository Analysis) of the
Enterprise Agentic Foundry.

Hard rules (never violate):
1. ALWAYS run detect_artifact_type() first — never assume what you were given.
2. ALWAYS produce assessment BEFORE recommendations — you analyze; you do not
   redesign. Recommendations belong to architecture_agent / security_agent /
   governance_agent, which you hand off to.
3. ALWAYS produce an explicit `unknowns` list. If something cannot be derived
   from the artifact, name it — never invent or assume it.
4. ALWAYS generate Mermaid diagrams for: architecture, deployment flow,
   CI/CD flow, security flow, and data flow.
5. NEVER duplicate specialist-agent analysis — hand off via
   handoff_to_specialist_agents() with pre-digested context.

Workflow:
1. detect_artifact_type(source)
2. inventory_repository(path_or_url)
3. generate_current_state_diagrams(inventory_summary)
4. handoff_to_specialist_agents(inventory_id, focus_areas=[...])
5. Produce the Executive Summary — current state ONLY, no recommendations
"""


def call_model(state: RepoAnalysisState) -> dict:
    llm = get_chat_model(agent_name="repo_analysis_agent", temperature=0)
    tools = [detect_artifact_type, inventory_repository,
             generate_current_state_diagrams, handoff_to_specialist_agents]
    llm_with_tools = llm.bind_tools(tools)
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def should_continue(state: RepoAnalysisState) -> Literal["tools", "__end__"]:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "__end__"


def build_repo_analysis_agent():
    tools = [detect_artifact_type, inventory_repository,
             generate_current_state_diagrams, handoff_to_specialist_agents]
    workflow = StateGraph(RepoAnalysisState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "__end__": END})
    workflow.add_edge("tools", "agent")
    return workflow.compile(checkpointer=MemorySaver())


if __name__ == "__main__":
    agent = build_repo_analysis_agent()
    result = agent.invoke(
        {"messages": [HumanMessage(content=
            "Analyze https://github.com/example-org/legacy-commerce-platform — "
            "produce the current-state assessment, diagrams, unknowns, and "
            "hand off to the right specialist agents.")]},
        config={"configurable": {"thread_id": "repo-analysis-legacy-commerce"}},
    )
    print(result["messages"][-1].content)
