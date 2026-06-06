"""
Security Agent — Universal Agentic DevOps Platform

Responsibilities:
- Scan container images on demand or schedule
- Analyze IaC for misconfigurations
- Triage vulnerability reports and generate fix PRs
- Monitor Falco runtime alerts
- Generate compliance reports (SOC2, PCI-DSS, ISO27001)
- Enforce security policies via OPA/Kyverno
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
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict


class SecurityState(TypedDict):
    messages: Annotated[list, add_messages]
    findings: list[dict]
    risk_level: str
    requires_immediate_action: bool
    audit_trail: list[dict]


@tool
def scan_container_image(image_ref: str, severity_threshold: str = "HIGH") -> dict:
    """Run Trivy scan against a container image. Returns vulnerabilities above threshold."""
    return {
        "image": image_ref,
        "scan_time": "2026-06-06T10:00:00Z",
        "vulnerabilities": [
            {
                "cve": "CVE-2024-12345",
                "severity": "CRITICAL",
                "package": "openssl",
                "installed_version": "3.1.2",
                "fixed_version": "3.1.4",
                "description": "Buffer overflow in TLS handshake",
                "score": 9.8,
            }
        ],
        "total_critical": 1,
        "total_high": 3,
        "sbom_available": True,
    }


@tool
def scan_iac_directory(path: str, framework: str = "terraform") -> dict:
    """Run Checkov IaC security scan against a directory."""
    return {
        "path": path,
        "framework": framework,
        "passed": 42,
        "failed": 3,
        "skipped": 1,
        "findings": [
            {
                "check_id": "CKV_AZURE_5",
                "check_name": "Ensure that Azure AKS has an identity",
                "resource": "azurerm_kubernetes_cluster.main",
                "severity": "HIGH",
            }
        ],
    }


@tool
def get_falco_alerts(
    namespace: str = "",
    severity: Literal["emergency", "alert", "critical", "error", "warning"] = "critical",
    limit: int = 20,
) -> dict:
    """Retrieve recent Falco runtime security alerts from the cluster."""
    return {
        "alerts": [
            {
                "time": "2026-06-06T09:55:12Z",
                "rule": "Terminal shell in container",
                "severity": "warning",
                "namespace": "production",
                "pod": "payment-service-7d8b9c4f6-xk2mp",
                "container": "payment-service",
                "process": "/bin/bash",
                "message": "A shell was spawned in a container in production",
            }
        ],
        "total": 1,
    }


@tool
def get_secret_rotation_status(
    secret_store: Literal["azure-key-vault", "aws-secrets-manager", "gcp-secret-manager", "vault"],
) -> dict:
    """Check which secrets are past their rotation deadline."""
    return {
        "secret_store": secret_store,
        "overdue_secrets": [
            {
                "secret_name": "database-password",
                "last_rotated": "2026-01-01",
                "days_since_rotation": 156,
                "rotation_policy_days": 90,
                "overdue_days": 66,
            }
        ],
        "due_soon_7d": 2,
        "compliant": 18,
    }


@tool
def generate_compliance_report(
    framework: Literal["soc2", "pci-dss", "iso27001", "hipaa", "cis-kubernetes"],
) -> dict:
    """Generate a compliance posture report for the specified framework."""
    return {
        "framework": framework,
        "generated_at": "2026-06-06T10:00:00Z",
        "overall_score": 78,
        "critical_gaps": 2,
        "high_gaps": 5,
        "summary": "2 critical controls failing: audit log retention < 1 year, no MFA for admin accounts.",
        "report_url": f"https://compliance.your-domain.com/reports/{framework}-2026-06",
    }


@tool
def create_remediation_pr(
    repo: str,
    finding: dict,
    suggested_fix: str,
) -> dict:
    """Create a GitHub PR with an automated fix for a security finding."""
    return {
        "pr_url": f"https://github.com/{repo}/pull/999",
        "branch": f"security/fix-{finding.get('cve', 'misconfiguration')}",
        "title": f"fix: Remediate {finding.get('cve', finding.get('check_id', 'security finding'))}",
        "status": "created",
    }


SYSTEM_PROMPT = """You are the Security Agent for the Universal Agentic DevOps Platform.

Your responsibilities:
1. Triage vulnerabilities from container scans (Trivy), IaC scans (Checkov), and DAST
2. Monitor Falco runtime security events for suspicious activity
3. Ensure secrets are rotated on schedule
4. Generate compliance gap reports on demand
5. Create automated remediation PRs for fixable issues
6. Escalate CRITICAL/EMERGENCY findings immediately

Risk Levels:
- CRITICAL: CVE score >= 9.0, Falco Emergency/Alert, production secret exposure → Page on-call immediately
- HIGH: CVE score 7.0-8.9, overdue secret rotation > 30 days → Create PR + Slack alert
- MEDIUM: CVE score 4.0-6.9, IaC misconfiguration → Create issue + weekly report
- LOW: Advisory/informational → Include in next weekly report

Never expose secret values in responses. Reference secrets by name only.
Always include CVE references and CVSS scores in vulnerability reports.
"""


def call_model(state: SecurityState) -> dict:
    llm = AzureChatOpenAI(
        azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version="2025-01-01-preview",
        temperature=0,
    )
    tools = [
        scan_container_image,
        scan_iac_directory,
        get_falco_alerts,
        get_secret_rotation_status,
        generate_compliance_report,
        create_remediation_pr,
    ]
    llm_with_tools = llm.bind_tools(tools)
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def should_continue(state: SecurityState) -> Literal["tools", END]:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


def build_security_agent() -> StateGraph:
    tools = [
        scan_container_image,
        scan_iac_directory,
        get_falco_alerts,
        get_secret_rotation_status,
        generate_compliance_report,
        create_remediation_pr,
    ]
    graph = StateGraph(SecurityState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=MemorySaver())


if __name__ == "__main__":
    agent = build_security_agent()
    state = {
        "messages": [
            HumanMessage(
                content=(
                    "Run a full security assessment for the payment-service. "
                    "Check the container image ghcr.io/our-org/payment-service:v1.2.5, "
                    "scan the terraform/azure IaC directory, check for overdue secret rotations "
                    "in Azure Key Vault, and check for any Falco alerts in the production namespace. "
                    "Give me a prioritized remediation plan."
                )
            )
        ],
        "findings": [],
        "risk_level": "unknown",
        "requires_immediate_action": False,
        "audit_trail": [],
    }
    config = {"configurable": {"thread_id": "security-session-001"}}
    for chunk in agent.stream(state, config=config, stream_mode="values"):
        last = chunk["messages"][-1]
        if hasattr(last, "content") and last.content:
            print(f"\n{last.content}")
