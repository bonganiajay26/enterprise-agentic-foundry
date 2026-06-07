"""
Documentation Agent — Universal Agentic DevOps Platform

Responsibilities:
- Generate production-ready README.md for any repository
- Create operational runbooks from incident history
- Produce API documentation from OpenAPI specs or code
- Write SOPs (Standard Operating Procedures)
- Generate Architecture Decision Records (ADRs)
- Create onboarding guides for new engineers
- Keep TechDocs in Backstage up to date
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from agentic_ai.llm import get_chat_model
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict


class DocumentationState(TypedDict):
    messages: Annotated[list, add_messages]
    documents_created: list[str]
    repository_context: dict
    audit_trail: list[dict]


@tool
def analyze_repository_structure(repo_path: str = ".") -> dict:
    """Scan a repository and extract structure, languages, frameworks, and patterns."""
    import subprocess
    structure = {"files": [], "languages": set(), "frameworks": [], "has_tests": False, "has_ci": False}

    for ext, lang in [(".py", "Python"), (".js", "JavaScript"), (".ts", "TypeScript"),
                       (".java", "Java"), (".go", "Go"), (".cs", "C#"), (".rs", "Rust")]:
        result = subprocess.run(["find", repo_path, "-name", f"*{ext}", "-not", "-path", "*/.*"],
                                capture_output=True, text=True)
        if result.stdout.strip():
            structure["languages"].add(lang)

    # Detect frameworks
    checks = {
        "package.json": ["express", "fastify", "nestjs", "nextjs", "react", "vue", "angular"],
        "requirements.txt": ["fastapi", "django", "flask", "langchain", "torch", "tensorflow"],
        "pom.xml": ["spring-boot"],
    }
    for file, frameworks in checks.items():
        fp = Path(repo_path) / file
        if fp.exists():
            content = fp.read_text()
            for fw in frameworks:
                if fw in content.lower():
                    structure["frameworks"].append(fw)

    structure["has_tests"] = any([
        (Path(repo_path) / d).exists()
        for d in ["tests", "test", "__tests__", "spec"]
    ])
    structure["has_ci"] = (Path(repo_path) / ".github" / "workflows").exists() or \
                          (Path(repo_path) / ".gitlab-ci.yml").exists()
    structure["languages"] = list(structure["languages"])
    return structure


@tool
def generate_readme(
    service_name: str,
    description: str,
    language: str,
    framework: str,
    cloud: str,
    api_endpoints: list[str] = None,
    include_badges: bool = True,
) -> dict:
    """Generate a comprehensive README.md for a service."""
    badges = ""
    if include_badges:
        badges = f"""
![CI](https://github.com/your-org/{service_name}/actions/workflows/ci.yml/badge.svg)
![Security](https://snyk.io/test/github/your-org/{service_name}/badge.svg)
![Coverage](https://codecov.io/gh/your-org/{service_name}/branch/main/graph/badge.svg)
"""

    endpoints_section = ""
    if api_endpoints:
        table_rows = "\n".join([f"| `{ep}` | TODO |" for ep in api_endpoints])
        endpoints_section = f"""
## API Endpoints

| Endpoint | Description |
|----------|-------------|
{table_rows}
"""

    readme = f"""# {service_name}
{badges}
> {description}

## Overview

{service_name} is a **{language}** service built with **{framework}**, deployed on **{cloud}**.

## Architecture

```mermaid
flowchart LR
    CLIENT[Client] --> GW[API Gateway]
    GW --> SVC[{service_name}]
    SVC --> DB[(Database)]
    SVC --> CACHE[(Redis Cache)]
```

## Prerequisites

- Docker 24+
- Kubernetes 1.28+ (for production deployment)
- [Language runtime]

## Quick Start

### Local Development

```bash
# Clone
git clone https://github.com/your-org/{service_name}
cd {service_name}

# Install dependencies
# Node.js: npm ci
# Python:  pip install -r requirements.txt
# Java:    ./mvnw install

# Start with Docker Compose (includes all dependencies)
docker-compose -f docker/docker-compose.dev.yml up

# Service available at: http://localhost:8080
```

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `PORT` | No | `8080` | Service port |
| `LOG_LEVEL` | No | `info` | Log verbosity |
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `REDIS_URL` | No | — | Redis connection string |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | — | OpenTelemetry collector endpoint |
{endpoints_section}
## Health Endpoints

| Endpoint | Purpose | Kubernetes Probe |
|---|---|---|
| `GET /health/live` | Liveness | livenessProbe |
| `GET /health/ready` | Readiness | readinessProbe |
| `GET /metrics` | Prometheus metrics | — |

## Deployment

```bash
# Build and push image
docker build -f docker/Dockerfile.{language.lower()} -t your-registry/{service_name}:v1.0.0 .
docker push your-registry/{service_name}:v1.0.0

# Deploy to Kubernetes via Helm
helm upgrade --install {service_name} ./helm/base-service \\
  --namespace production --create-namespace \\
  --set image.repository=your-registry/{service_name} \\
  --set image.tag=v1.0.0 \\
  --values helm/base-service/values-prod.yaml
```

## Development

```bash
# Run tests
# Node.js: npm test -- --coverage
# Python:  pytest --cov
# Java:    ./mvnw test

# Lint
# Node.js: npm run lint
# Python:  ruff check .
# Java:    ./mvnw checkstyle:check
```

## Observability

- **Metrics:** Prometheus — `GET /metrics`
- **Tracing:** OpenTelemetry → Tempo → Grafana
- **Logs:** Structured JSON → Loki → Grafana
- **Dashboard:** [Grafana](https://grafana.your-domain.com/d/{service_name})

## On-Call

| Alert | Runbook |
|---|---|
| High error rate | [runbooks/slo-burn.md](runbooks/slo-burn.md) |
| Pod CrashLoop | [runbooks/pod-crashloop.md](runbooks/pod-crashloop.md) |
| Certificate expiry | [runbooks/cert-expiry.md](runbooks/cert-expiry.md) |

## Contributing

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for development guidelines.

## License

Apache 2.0
"""

    return {
        "document": readme,
        "filename": "README.md",
        "word_count": len(readme.split()),
    }


@tool
def generate_runbook(
    service_name: str,
    alert_name: str,
    alert_description: str,
    symptoms: list[str],
    mitigation_steps: list[str],
    escalation_path: str = "",
) -> dict:
    """Generate an operational runbook for a specific alert or scenario."""
    symptoms_list = "\n".join([f"- {s}" for s in symptoms])
    mitigation_list = "\n".join([f"{i+1}. {s}" for i, s in enumerate(mitigation_steps)])

    runbook = f"""# Runbook: {alert_name}

**Service:** {service_name}
**Severity:** P1/P2 (determine based on impact)
**Created:** 2026-06-06

## Description

{alert_description}

## Symptoms

{symptoms_list}

## Investigation

```bash
# 1. Check pod status
kubectl get pods -n production -l app={service_name}

# 2. Describe failing pod
kubectl describe pod <pod-name> -n production

# 3. View recent logs
kubectl logs -l app={service_name} -n production --since=10m --tail=200

# 4. Check recent deployments
kubectl rollout history deployment/{service_name} -n production

# 5. Check metrics
# PromQL: sum(rate(http_requests_total{{status=~"5..", job="{service_name}"}}[5m]))
```

## Mitigation

{mitigation_list}

## Escalation

{escalation_path or "If issue not resolved in 30 minutes, escalate to platform team lead."}

## Post-Incident

After resolving, update this runbook with:
1. Root cause
2. Any new diagnostic commands discovered
3. Any preventive measures taken
"""
    return {"document": runbook, "filename": f"runbooks/{alert_name.lower().replace(' ', '-')}.md"}


@tool
def generate_sop(
    process_name: str,
    frequency: str,
    owner_role: str,
    steps: list[str],
    prerequisites: list[str] = None,
    approval_required: bool = False,
) -> dict:
    """Generate a Standard Operating Procedure document."""
    prereqs_section = ""
    if prerequisites:
        prereqs_section = "## Prerequisites\n\n" + "\n".join([f"- {p}" for p in prerequisites]) + "\n\n"

    approval_section = ""
    if approval_required:
        approval_section = """
## Approval Required

This procedure requires sign-off from **Engineering Manager** before execution.

| Approver | Date | Signature |
|---|---|---|
| Engineering Manager | | |
| Security Team (if security-related) | | |

"""

    steps_formatted = "\n".join([f"### Step {i+1}: {s}\n\n```bash\n# Commands for this step\n```\n"
                                  for i, s in enumerate(steps)])

    sop = f"""# SOP: {process_name}

**Owner:** {owner_role}
**Frequency:** {frequency}
**Last Reviewed:** 2026-06-06
**Version:** 1.0

## Purpose

This SOP defines the procedure for: **{process_name}**

{prereqs_section}{approval_section}
## Procedure

{steps_formatted}

## Verification

After completing the procedure:

- [ ] Verify expected outcome achieved
- [ ] Check monitoring dashboards for anomalies
- [ ] Update change log / incident ticket
- [ ] Notify stakeholders if required

## Rollback

If the procedure fails, perform the following rollback steps:

1. Stop the current operation
2. Restore previous state
3. Notify on-call engineer
4. Create incident ticket

## References

- [Related Runbook](../runbooks/)
- [Architecture Documentation](../architecture/)
"""
    return {"document": sop, "filename": f"docs/sop-{process_name.lower().replace(' ', '-')}.md"}


@tool
def generate_api_documentation(
    service_name: str,
    base_url: str,
    endpoints: list[dict],
    auth_method: Literal["none", "bearer", "api-key", "oauth2"] = "bearer",
) -> dict:
    """Generate API documentation in Markdown format."""
    auth_section = {
        "none": "No authentication required.",
        "bearer": "Include a JWT Bearer token in the `Authorization` header:\n```\nAuthorization: Bearer <token>\n```",
        "api-key": "Include your API key in the `X-API-Key` header:\n```\nX-API-Key: your-api-key\n```",
        "oauth2": "Use OAuth2 PKCE flow. Obtain token from the authorization server.",
    }[auth_method]

    endpoints_docs = []
    for ep in endpoints:
        endpoints_docs.append(f"""
### {ep.get('method', 'GET')} {ep.get('path', '/')}

{ep.get('description', '')}

**Request**
```json
{ep.get('request_example', '{}')}
```

**Response** `{ep.get('response_status', '200 OK')}`
```json
{ep.get('response_example', '{}')}
```
""")

    api_doc = f"""# {service_name} API Documentation

**Base URL:** `{base_url}`
**Version:** v1

## Authentication

{auth_section}

## Endpoints

{''.join(endpoints_docs)}

## Error Responses

| Status | Code | Description |
|---|---|---|
| 400 | VALIDATION_ERROR | Invalid request parameters |
| 401 | UNAUTHORIZED | Missing or invalid authentication |
| 403 | FORBIDDEN | Insufficient permissions |
| 404 | NOT_FOUND | Resource not found |
| 429 | RATE_LIMITED | Too many requests |
| 500 | INTERNAL_ERROR | Unexpected server error |

## Rate Limiting

- **Default:** 100 requests per minute per IP
- **Authenticated:** 1000 requests per minute per token
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
"""
    return {"document": api_doc, "filename": f"docs/api-reference-{service_name.lower()}.md"}


@tool
def write_document_to_file(filename: str, content: str) -> dict:
    """Write a generated document to the filesystem."""
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"status": "written", "path": str(path), "bytes": len(content)}


SYSTEM_PROMPT = """You are the Documentation Agent for the Universal Agentic DevOps Platform.

Your mission is to generate production-quality technical documentation that:
1. Saves engineers time — they should be able to use docs without asking questions
2. Follows enterprise documentation standards (clear structure, Markdown, code examples)
3. Includes both "what" and "how" — never just describe, always show
4. Stays accurate and up-to-date with the actual codebase

Documentation types you produce:
- README.md: Project overview, quick start, env vars, deployment, observability
- Runbooks: Step-by-step incident response procedures with actual commands
- SOPs: Formal procedures for recurring operations (releases, rotations, upgrades)
- API docs: Endpoint reference with request/response examples
- ADRs: Architecture decisions with context, options, and rationale

Quality standards:
- Every README must have a Quick Start that works in < 5 minutes
- Every runbook must have copy-paste-ready kubectl/shell commands
- Every API endpoint must have a real request/response example
- All Mermaid diagrams must render correctly
- No "TODO" placeholders unless explicitly noted

Always write for the reader, not the writer.
"""


def call_model(state: DocumentationState) -> dict:
    llm = get_chat_model(agent_name="documentation_agent", temperature=0.2)
    tools = [analyze_repository_structure, generate_readme, generate_runbook,
             generate_sop, generate_api_documentation, write_document_to_file]
    response = llm.bind_tools(tools).invoke([SystemMessage(content=SYSTEM_PROMPT)] + state["messages"])
    return {"messages": [response]}


def should_continue(state: DocumentationState) -> Literal["tools", END]:
    last = state["messages"][-1]
    return "tools" if isinstance(last, AIMessage) and last.tool_calls else END


def build_documentation_agent() -> StateGraph:
    tools = [analyze_repository_structure, generate_readme, generate_runbook,
             generate_sop, generate_api_documentation, write_document_to_file]
    graph = StateGraph(DocumentationState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=MemorySaver())
