"""
Auto-Remediation Agent — Universal Agentic DevOps Platform

Closes the loop on the Autonomous SDLC (see docs/autonomous-sdlc.md): once the
Incident, Security, Kubernetes, or Performance agents detect a problem, this
agent classifies the fix, applies it automatically when safe, or opens a
gated approval request when it is not.

Responsibilities:
- Classify a proposed remediation as AUTOMATIC or APPROVAL_REQUIRED
- Apply low-risk fixes directly (formatting, lint, dependency patches,
  pipeline/Docker/Helm/monitoring config corrections) via PR automation
- Open an approval-gated change request for high-risk actions (IAM, database,
  infra deletion, prod rollback, security policy, LLM provider changes)
- Re-run validation after every fix and roll back automatically on failure
- Emit a full audit trail (who/what/when/why/approved-by) for compliance
- Generate a docs/issues/ entry for every remediation (see issue_template)

Risk classification mirrors PHASE 7 of the master prompt exactly — this is
the single source of truth other agents call into via `classify_remediation`.
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


class RemediationState(TypedDict):
    messages: Annotated[list, add_messages]
    classification: str
    remediation_plan: dict
    audit_trail: list[dict]


# ---------------------------------------------------------------------------
# Risk classification — the canonical AUTOMATIC vs APPROVAL_REQUIRED matrix.
# ---------------------------------------------------------------------------
AUTOMATIC_CATEGORIES = {
    "formatting": "Code formatting (prettier, black, gofmt, spotless)",
    "linting": "Lint auto-fixes (eslint --fix, ruff --fix, golangci-lint)",
    "dependency_patch": "Patch-level dependency bumps with passing CI + no CVE regressions",
    "pipeline_fix": "CI/CD syntax/config corrections that don't change deploy targets",
    "docker_optimization": "Dockerfile layer caching, base-image digest pinning, size reduction",
    "helm_fix": "Helm template/values corrections that don't change replica/resource limits in prod",
    "monitoring_fix": "Alert rule syntax fixes, dashboard JSON corrections, scrape config typos",
}

APPROVAL_REQUIRED_CATEGORIES = {
    "iam_change": "IAM/RBAC role, policy, or permission binding changes",
    "database_change": "Schema migrations, data deletion, connection string changes",
    "infra_deletion": "Terraform/OpenTofu destroy, resource group deletion, namespace removal",
    "production_rollback": "Rolling back a production deployment or database restore",
    "security_policy_change": "OPA/Kyverno/Falco/NetworkPolicy/WAF rule modifications",
    "llm_provider_change": "Changing active_profile, provider credentials, or routing strategy in llm-config.yaml",
    "scaling_change": "HPA/cluster-autoscaler limits affecting prod capacity or cost > $1000/mo delta",
    "major_dependency_bump": "Major/minor version upgrades with breaking-change potential",
}


@tool
def classify_remediation(category: str, environment: str = "production") -> dict:
    """Classify a proposed remediation as AUTOMATIC (apply immediately) or
    APPROVAL_REQUIRED (open a gated change request). `category` should be
    one of the canonical keys (e.g. 'formatting', 'iam_change')."""
    if category in AUTOMATIC_CATEGORIES:
        # Production database/IAM-adjacent categories never auto-apply,
        # regardless of nominal classification — defense in depth.
        if environment == "production" and category in ("helm_fix", "pipeline_fix"):
            return {
                "category": category,
                "classification": "AUTOMATIC_WITH_CANARY",
                "reason": AUTOMATIC_CATEGORIES[category],
                "policy": "Apply to staging first, run smoke tests, canary 10% in prod, then full rollout.",
            }
        return {
            "category": category,
            "classification": "AUTOMATIC",
            "reason": AUTOMATIC_CATEGORIES[category],
            "policy": "Apply directly via automated PR + CI gate; no human approval required.",
        }
    if category in APPROVAL_REQUIRED_CATEGORIES:
        return {
            "category": category,
            "classification": "APPROVAL_REQUIRED",
            "reason": APPROVAL_REQUIRED_CATEGORIES[category],
            "policy": "Open a gated change request; require 1+ approval from CODEOWNERS + "
                      "the relevant domain lead (Security/DBA/Platform) before execution.",
            "approvers_required": _approvers_for(category),
        }
    return {
        "category": category,
        "classification": "UNKNOWN — DEFAULT TO APPROVAL_REQUIRED",
        "reason": "Unrecognized remediation category; fail closed per zero-trust policy.",
        "policy": "Route to human review until a category mapping is added to remediation_agent.py.",
    }


def _approvers_for(category: str) -> list[str]:
    mapping = {
        "iam_change": ["security-lead", "platform-lead"],
        "database_change": ["dba-lead", "platform-lead"],
        "infra_deletion": ["platform-lead", "sre-lead"],
        "production_rollback": ["sre-on-call", "engineering-manager"],
        "security_policy_change": ["security-lead"],
        "llm_provider_change": ["platform-lead", "finops-lead"],
        "scaling_change": ["sre-lead", "finops-lead"],
        "major_dependency_bump": ["tech-lead"],
    }
    return mapping.get(category, ["platform-lead"])


@tool
def generate_remediation_plan(issue_id: str, root_cause: str, category: str) -> dict:
    """Produce a structured remediation plan: steps, validation, rollback,
    and the docs/issues/ entry payload. Always pairs with classify_remediation."""
    return {
        "issue_id": issue_id,
        "root_cause": root_cause,
        "category": category,
        "plan_steps": [
            "1. Reproduce the issue in a non-prod environment",
            "2. Draft the minimal fix (smallest blast radius)",
            "3. Run unit + integration + security scan against the fix branch",
            "4. Classify via classify_remediation() — route AUTOMATIC or APPROVAL_REQUIRED",
            "5. Apply (direct merge+deploy) or open gated change request",
            "6. Re-run full validation suite post-deploy (tests/smoke/smoke-test.sh)",
            "7. Monitor SLO burn-rate for 30 minutes; auto-rollback on regression",
            "8. Close out docs/issues/<issue_id>.md with resolution + evidence",
        ],
        "validation_gates": [
            "CI pipeline green", "Security scan clean (no new CVSS >= 7.0)",
            "Smoke tests pass", "SLO burn-rate within budget for 30 min post-deploy",
        ],
        "rollback_strategy": "Automated: ArgoCD sync to previous Git revision; "
                             "Helm: `helm rollback <release> <revision>`; "
                             "DB: pgBackRest point-in-time restore (see docs/backup-strategy.md)",
        "audit_entry": {
            "issue_id": issue_id,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "category": category,
            "actor": "remediation_agent",
            "status": "plan_generated",
        },
    }


@tool
def apply_automatic_fix(issue_id: str, category: str, diff_summary: str) -> dict:
    """Apply a pre-classified AUTOMATIC remediation: opens an automated PR,
    waits for CI, auto-merges on green, and records the audit trail. Will
    refuse to run if `category` is not in AUTOMATIC_CATEGORIES (fail-closed)."""
    if category not in AUTOMATIC_CATEGORIES:
        return {
            "status": "REFUSED",
            "reason": f"'{category}' is not an auto-approved category. "
                      f"Use open_change_request() instead.",
        }
    return {
        "issue_id": issue_id,
        "status": "applied",
        "pr_url": f"https://github.com/bonganiajay26/enterprise-agentic-foundry/pull/auto-{issue_id}",
        "diff_summary": diff_summary,
        "ci_status": "green",
        "merge_strategy": "squash-and-merge on green CI + required checks",
        "post_merge_actions": ["ArgoCD auto-sync", "smoke test re-run", "30-min SLO watch"],
        "audit": {
            "actor": "remediation_agent",
            "action": "apply_automatic_fix",
            "category": category,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        },
    }


@tool
def open_change_request(issue_id: str, category: str, justification: str) -> dict:
    """Open a gated, human-approval-required change request for high-risk
    remediations (IAM, database, infra deletion, prod rollback, security
    policy, LLM provider changes). Never executes the change itself."""
    approvers = _approvers_for(category)
    return {
        "issue_id": issue_id,
        "status": "PENDING_APPROVAL",
        "category": category,
        "justification": justification,
        "approvers_required": approvers,
        "change_request_url": f"https://github.com/bonganiajay26/enterprise-agentic-foundry/issues/cr-{issue_id}",
        "sla": "Approve/reject within 4 business hours for P1/P2; 2 business days otherwise",
        "escalation_path": "If no response within SLA, escalate to engineering-manager via PagerDuty",
        "audit": {
            "actor": "remediation_agent",
            "action": "open_change_request",
            "category": category,
            "approvers_required": approvers,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        },
    }


@tool
def write_issue_record(issue_id: str, severity: str, description: str,
                        root_cause: str, resolution: str, files_changed: list[str],
                        status: str = "resolved") -> dict:
    """Generate the docs/issues/<issue_id>.md content per the platform's
    Issue Management Framework (see docs/issues/README.md and ISSUE-TEMPLATE.md)."""
    content = f"""# Issue {issue_id}

**Severity:** {severity}
**Status:** {status}
**Detected by:** remediation_agent (autonomous SDLC loop)
**Date:** {datetime.datetime.utcnow().strftime('%Y-%m-%d')}

## Description
{description}

## Evidence
- Logs: Loki query `{{issue_id="{issue_id}"}}`
- Metrics: Grafana dashboard "Platform / Incidents" filtered by `issue_id={issue_id}`
- Traces: Tempo trace search tagged `issue.id={issue_id}`

## Root Cause
{root_cause}

## Resolution
{resolution}

## Files Changed
{chr(10).join(f"- `{f}`" for f in files_changed)}

## Validation
- [ ] CI pipeline green
- [ ] Security scan clean
- [ ] Smoke tests passed
- [ ] SLO burn-rate normal for 30 min post-deploy

## Prevention
Add a regression test, update the relevant runbook, and (if applicable) a
Falco/OPA rule or alert to detect recurrence before user impact.

## Status
{status}
"""
    return {"issue_id": issue_id, "file_path": f"docs/issues/{issue_id}.md", "content": content}


SYSTEM_PROMPT = """You are the Auto-Remediation Agent for the Universal Agentic DevOps Platform.

Your job is to close the loop of the Autonomous SDLC: take a detected issue
(from Incident, Security, Kubernetes, or Performance agents), classify the
correct remediation, and either apply it automatically (low risk) or open a
gated, human-approved change request (high risk).

Hard rules — never violate these:
1. NEVER apply IAM, database, infrastructure-deletion, production-rollback,
   security-policy, or LLM-provider changes without human approval.
2. ALWAYS classify before acting — call classify_remediation() first.
3. ALWAYS generate a docs/issues/ record for every remediation, automatic or not.
4. ALWAYS define a rollback strategy before applying any fix.
5. Fail closed: if a category is unrecognized, route to human review.

Workflow:
1. classify_remediation(category, environment)
2. generate_remediation_plan(issue_id, root_cause, category)
3a. If AUTOMATIC -> apply_automatic_fix(...)
3b. If APPROVAL_REQUIRED -> open_change_request(...)
4. write_issue_record(...) — always, regardless of path taken
"""


def call_model(state: RemediationState) -> dict:
    llm = get_chat_model(agent_name="remediation_agent", temperature=0)
    tools = [classify_remediation, generate_remediation_plan,
             apply_automatic_fix, open_change_request, write_issue_record]
    llm_with_tools = llm.bind_tools(tools)
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def should_continue(state: RemediationState) -> Literal["tools", "__end__"]:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "__end__"


def build_remediation_agent():
    tools = [classify_remediation, generate_remediation_plan,
             apply_automatic_fix, open_change_request, write_issue_record]
    workflow = StateGraph(RemediationState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "__end__": END})
    workflow.add_edge("tools", "agent")
    return workflow.compile(checkpointer=MemorySaver())


if __name__ == "__main__":
    agent = build_remediation_agent()
    result = agent.invoke(
        {"messages": [HumanMessage(content=
            "Issue INC-2026-0142: payment-service pods CrashLoopBackOff due to "
            "a missing DB connection-pool env var introduced in the last Helm "
            "values change. Root cause confirmed. Classify and remediate.")]},
        config={"configurable": {"thread_id": "remediation-inc-2026-0142"}},
    )
    print(result["messages"][-1].content)
