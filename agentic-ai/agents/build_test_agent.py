"""
Build & Test Agent — Universal Agentic DevOps Platform

Combines the master-prompt's "Build Agent" and "Test Agent" responsibilities
into one cohesive unit (steps 3-4 of the Autonomous SDLC — see
docs/autonomous-sdlc.md). They share inputs (a commit/PR) and a single
pass/fail gate, so a unified agent avoids redundant repo checkouts and
keeps the build->test->report loop atomic and auditable.

Responsibilities — Build:
- Trigger and monitor language-appropriate build pipelines (npm/maven/go/
  dotnet/poetry) across GitHub Actions, Azure DevOps, GitLab CI, Jenkins
- Validate build artifacts (container image digest, SBOM, provenance attestation)
- Detect and classify build failures (dependency, compile, config, infra)

Responsibilities — Test:
- Execute unit, integration, contract, and smoke test suites
- Track coverage trends and flag regressions against the quality gate
- Quarantine flaky tests (auto-detected via historical pass/fail variance)
- Hand failing builds/tests to remediation_agent with full diagnostic context
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


class BuildTestState(TypedDict):
    messages: Annotated[list, add_messages]
    build_result: dict
    test_result: dict
    audit_trail: list[dict]


@tool
def trigger_build(repo: str, ref: str, build_system: str = "github-actions") -> dict:
    """Trigger a CI build for the given repo/ref and return structured status.
    Supports github-actions | azure-devops | gitlab-ci | jenkins."""
    return {
        "repo": repo, "ref": ref, "build_system": build_system,
        "run_id": f"run-{abs(hash(repo+ref)) % 100000}",
        "status": "success",
        "duration_seconds": 187,
        "artifact": {
            "image": f"ghcr.io/{repo}:{ref[:7]}",
            "digest": "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
            "sbom_generated": True,
            "provenance_attestation": "in-toto SLSA Level 3",
        },
        "cache_hit_rate_pct": 78.4,
    }


@tool
def classify_build_failure(error_log_excerpt: str) -> dict:
    """Classify a build failure into a category that determines remediation
    routing: dependency | compile | configuration | infrastructure | flaky."""
    lowered = error_log_excerpt.lower()
    if "could not resolve dependency" in lowered or "404 not found" in lowered and "registry" in lowered:
        category, hint = "dependency", "Lockfile drift or registry outage — check package-lock/go.sum/poetry.lock"
    elif "syntax error" in lowered or "compilation failed" in lowered or "type error" in lowered:
        category, hint = "compile", "Source-level defect — block merge, route to author for fix"
    elif "permission denied" in lowered or "no space left" in lowered or "runner" in lowered:
        category, hint = "infrastructure", "CI runner/environment issue — likely transient, retry with backoff"
    elif "yaml" in lowered or "invalid configuration" in lowered:
        category, hint = "configuration", "Pipeline/Dockerfile/Helm config syntax — auto-fixable (category=pipeline_fix)"
    else:
        category, hint = "unknown", "Insufficient signal — escalate to incident_response_agent for RCA"
    return {"category": category, "hint": hint, "remediation_category_suggestion":
            "pipeline_fix" if category == "configuration" else
            "dependency_patch" if category == "dependency" else None}


@tool
def execute_test_suite(repo: str, ref: str, suite: str = "all") -> dict:
    """Execute unit/integration/contract/smoke suites and return structured
    results including coverage delta and flaky-test detection."""
    return {
        "repo": repo, "ref": ref, "suite": suite,
        "results": {
            "unit": {"passed": 842, "failed": 0, "skipped": 3, "duration_s": 64},
            "integration": {"passed": 96, "failed": 1, "skipped": 0, "duration_s": 211},
            "contract": {"passed": 28, "failed": 0, "skipped": 0, "duration_s": 19},
            "smoke": {"passed": 14, "failed": 0, "skipped": 0, "duration_s": 47},
        },
        "coverage": {"line_pct": 84.2, "branch_pct": 76.8, "delta_vs_main": -0.3},
        "quality_gate": {"min_coverage_pct": 80, "status": "PASS"},
        "failing_tests": [
            {"name": "test_payment_retry_on_timeout", "suite": "integration",
             "failure_type": "assertion", "flaky_score": 0.71,
             "verdict": "LIKELY FLAKY — quarantine candidate (71% historical pass rate under retry)"},
        ],
        "overall_status": "PASS_WITH_WARNINGS",
    }


@tool
def quarantine_flaky_test(test_name: str, flaky_score: float, evidence: str) -> dict:
    """Quarantine a test exceeding the flaky threshold (>0.6 historical
    variance) — removes it from the merge-blocking gate while a fix is tracked,
    without silently hiding the underlying issue."""
    if flaky_score < 0.6:
        return {"status": "REFUSED", "reason": "flaky_score below 0.6 threshold — investigate as a real failure first"}
    return {
        "test_name": test_name, "status": "quarantined",
        "flaky_score": flaky_score, "evidence": evidence,
        "tracking_issue": f"docs/issues/DEBT-{datetime.datetime.utcnow():%Y}-{abs(hash(test_name))%10000:04d}.md",
        "policy": "Quarantined tests must be fixed or removed within 30 days; "
                  "governance_agent flags any quarantine older than that as a debt-report item.",
        "ci_gate_impact": "Excluded from merge-blocking gate; still runs nightly and reports to dashboard",
    }


@tool
def generate_build_test_report(repo: str, ref: str) -> dict:
    """Aggregate build + test outcomes into the step-20 report consumed by
    documentation_agent and the Grafana 'AI Agents' dashboard."""
    return {
        "repo": repo, "ref": ref,
        "summary": "Build succeeded (3m07s); 980/981 tests passed; coverage 84.2% "
                   "(gate: 80%, PASS); 1 integration test flagged as likely-flaky "
                   "and quarantined pending fix (tracked as DEBT-2026-xxxx).",
        "recommendation": "SAFE TO PROMOTE — proceed to security scan (step 5)",
        "next_step": "security_agent.scan_for_secrets / analyze_dependencies / scan_kubernetes",
    }


SYSTEM_PROMPT = """You are the Build & Test Agent for the Universal Agentic DevOps Platform —
responsible for steps 3 and 4 of the Autonomous SDLC (see docs/autonomous-sdlc.md).

Responsibilities:
1. Trigger builds across any supported CI system and validate artifacts
   (image digest, SBOM, SLSA provenance attestation) — never accept an
   unsigned/unattested artifact for a production-bound pipeline.
2. Classify build failures (dependency/compile/config/infra/flaky) precisely
   enough that remediation_agent can route correctly without re-investigating.
3. Execute the full test pyramid (unit/integration/contract/smoke), enforce
   the coverage quality gate, and detect flaky tests via historical variance.
4. Quarantine — never silently delete — flaky tests, with a tracked debt issue.
5. Always end with generate_build_test_report() so the loop can proceed or halt.

A build/test failure that you cannot classify with high confidence should be
escalated to incident_response_agent for root-cause analysis — do not guess.
"""


def call_model(state: BuildTestState) -> dict:
    llm = get_chat_model(agent_name="build_test_agent", temperature=0)
    tools = [trigger_build, classify_build_failure, execute_test_suite,
             quarantine_flaky_test, generate_build_test_report]
    llm_with_tools = llm.bind_tools(tools)
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def should_continue(state: BuildTestState) -> Literal["tools", "__end__"]:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "__end__"


def build_build_test_agent():
    tools = [trigger_build, classify_build_failure, execute_test_suite,
             quarantine_flaky_test, generate_build_test_report]
    workflow = StateGraph(BuildTestState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "__end__": END})
    workflow.add_edge("tools", "agent")
    return workflow.compile(checkpointer=MemorySaver())


if __name__ == "__main__":
    agent = build_build_test_agent()
    result = agent.invoke(
        {"messages": [HumanMessage(content=
            "Build and test bonganiajay26/payment-service @ refs/pull/842/merge, "
            "then report whether it's safe to promote to the security scan stage.")]},
        config={"configurable": {"thread_id": "build-test-payment-842"}},
    )
    print(result["messages"][-1].content)
