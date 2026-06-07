"""
AutoGen Multi-Agent Platform Team — Universal Agentic DevOps Platform

Implements a conversational multi-agent team using Microsoft AutoGen.
Agents collaborate to solve complex platform problems that require
multiple specializations working together.

Team composition:
- PlatformLead:   Orchestrates, makes final decisions
- SecurityExpert: Security analysis and threat modeling
- DevOpsEngineer: CI/CD, deployment, infrastructure
- SREEngineer:    Reliability, SLOs, incident response
- FinOpsAnalyst:  Cost optimization

Use cases:
- Architecture review sessions
- Pre-production checklists
- Post-incident retrospectives
- New project onboarding analysis
"""

from __future__ import annotations

import os

try:
    import autogen
    from autogen import AssistantAgent, GroupChat, GroupChatManager, UserProxyAgent
    AUTOGEN_AVAILABLE = True
except ImportError:
    AUTOGEN_AVAILABLE = False
    print("AutoGen not installed. Run: pip install pyautogen")


def create_platform_team(
    task: str,
    max_rounds: int = 20,
    verbose: bool = True,
) -> str:
    """
    Assemble the platform team and run a collaborative session.

    Args:
        task: The problem or task to solve collaboratively
        max_rounds: Maximum conversation rounds
        verbose: Whether to print conversation

    Returns:
        Final summary from the team
    """
    if not AUTOGEN_AVAILABLE:
        raise RuntimeError("AutoGen not available. Install with: pip install pyautogen")

    llm_config = {
        "config_list": [
            {
                "model": os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
                "api_type": "azure",
                "api_key": os.environ["AZURE_OPENAI_API_KEY"],
                "azure_endpoint": os.environ["AZURE_OPENAI_ENDPOINT"],
                "api_version": "2025-01-01-preview",
            }
        ],
        "temperature": 0,
        "timeout": 120,
        "cache_seed": None,
    }

    # ─── Platform Lead ────────────────────────────────────────────────
    platform_lead = AssistantAgent(
        name="PlatformLead",
        system_message="""You are the Platform Engineering Lead with 20 years experience.
You orchestrate the team discussion, synthesize inputs from all specialists,
and make final architectural and operational decisions.

Responsibilities:
- Direct the conversation to ensure all aspects are covered
- Ask SecurityExpert, DevOpsEngineer, SREEngineer, and FinOpsAnalyst for their input
- Resolve disagreements by applying engineering judgment
- Produce a final actionable recommendation

Always end your contributions with either a question to a specific team member,
or a FINAL RECOMMENDATION if the discussion is complete.
Reply TERMINATE when the task is fully resolved.""",
        llm_config=llm_config,
    )

    # ─── Security Expert ──────────────────────────────────────────────
    security_expert = AssistantAgent(
        name="SecurityExpert",
        system_message="""You are a Security Architect specializing in cloud-native security.
Your focus: Zero Trust, supply chain security, secrets management, RBAC, compliance.

When reviewing:
1. Identify security risks (CVSS score if applicable)
2. Reference specific controls: OWASP, CIS, NIST
3. Provide concrete mitigations, not just observations
4. Flag anything that blocks compliance (SOC2, ISO27001, PCI-DSS)

Never approve production deployments with CRITICAL vulnerabilities unmitigated.""",
        llm_config=llm_config,
    )

    # ─── DevOps Engineer ──────────────────────────────────────────────
    devops_engineer = AssistantAgent(
        name="DevOpsEngineer",
        system_message="""You are a Senior DevOps/Platform Engineer expert in Kubernetes,
CI/CD, Terraform, Helm, GitOps, and container platforms.

When reviewing:
1. Assess CI/CD pipeline quality: security gates, test coverage, deployment strategy
2. Review Kubernetes configurations: resource limits, HPA, PDB, security contexts
3. Evaluate IaC: Terraform module quality, state management, drift detection
4. Recommend automation improvements

Always provide specific, actionable commands and configurations, not vague advice.""",
        llm_config=llm_config,
    )

    # ─── SRE Engineer ─────────────────────────────────────────────────
    sre_engineer = AssistantAgent(
        name="SREEngineer",
        system_message="""You are a Senior Site Reliability Engineer with expertise in
SLOs, error budgets, incident management, and production reliability.

When reviewing:
1. Define or validate SLOs: availability, latency, throughput
2. Assess observability: metrics, logs, traces, dashboards
3. Review alert quality: actionability, false positive rate, runbook coverage
4. Evaluate DR/HA strategy: RTO/RPO targets, multi-region, backup

Always quantify reliability improvements in terms of user-facing impact.""",
        llm_config=llm_config,
    )

    # ─── FinOps Analyst ───────────────────────────────────────────────
    finops_analyst = AssistantAgent(
        name="FinOpsAnalyst",
        system_message="""You are a FinOps practitioner specializing in cloud cost optimization.

When reviewing:
1. Identify over-provisioned resources with dollar amounts
2. Recommend reserved instances / savings plans with ROI calculations
3. Detect idle resources (PVCs, load balancers, stopped VMs)
4. Suggest architectural changes that reduce cost (caching, CDN, right-sizing)

Always express recommendations in annual savings potential (USD).""",
        llm_config=llm_config,
    )

    # ─── User Proxy (Orchestration) ───────────────────────────────────
    user_proxy = UserProxyAgent(
        name="PlatformOrchestrator",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=0,
        is_termination_msg=lambda x: "TERMINATE" in x.get("content", ""),
        code_execution_config=False,
    )

    # ─── Group Chat ───────────────────────────────────────────────────
    group_chat = GroupChat(
        agents=[user_proxy, platform_lead, security_expert, devops_engineer, sre_engineer, finops_analyst],
        messages=[],
        max_round=max_rounds,
        speaker_selection_method="auto",
        allow_repeat_speaker=False,
    )

    manager = GroupChatManager(
        groupchat=group_chat,
        llm_config=llm_config,
    )

    # ─── Run the session ──────────────────────────────────────────────
    user_proxy.initiate_chat(manager, message=task)

    # Extract final summary
    messages = group_chat.messages
    return messages[-1]["content"] if messages else "No output generated"


def run_production_readiness_review(
    service_name: str,
    deployment_context: str,
) -> str:
    """
    Run a multi-agent production readiness review for a service.
    All specialists weigh in before the Platform Lead summarizes.
    """
    task = f"""
## Production Readiness Review: {service_name}

**Context:** {deployment_context}

Each specialist must review this service deployment from their domain:

1. **SecurityExpert**: Review security controls, secrets management, and compliance gaps
2. **DevOpsEngineer**: Review CI/CD pipeline, Kubernetes configuration, and deployment strategy
3. **SREEngineer**: Review SLOs, observability, alerting, and DR posture
4. **FinOpsAnalyst**: Review resource sizing and cost optimization opportunities

**PlatformLead**: Synthesize the review into:
- GO / NO-GO recommendation
- List of blocking issues (must fix before production)
- List of improvements (fix within 30 days)
- Estimated effort for each item

Please proceed with the review.
"""
    return create_platform_team(task, max_rounds=15)


def run_incident_postmortem(
    incident_id: str,
    incident_summary: str,
    timeline: str,
    impact: str,
) -> str:
    """
    Run a collaborative post-mortem analysis with the platform team.
    """
    task = f"""
## Post-Mortem Analysis: {incident_id}

**Summary:** {incident_summary}

**Timeline:**
{timeline}

**Impact:** {impact}

Team, please analyze this incident:

1. **SREEngineer**: Identify gaps in monitoring/alerting that delayed detection
2. **DevOpsEngineer**: Identify any deployment, configuration, or infrastructure root causes
3. **SecurityExpert**: Assess if there were any security implications
4. **FinOpsAnalyst**: Estimate the business cost of downtime

**PlatformLead**: Synthesize into a post-mortem document with:
- Root cause (5 Whys)
- What went well
- What went poorly
- Action items with owners and due dates
- SLO impact assessment

TERMINATE when complete.
"""
    return create_platform_team(task, max_rounds=12)


if __name__ == "__main__":
    if not AUTOGEN_AVAILABLE:
        print("Install AutoGen: pip install pyautogen")
        exit(1)

    print("Running production readiness review demo...\n")

    result = run_production_readiness_review(
        service_name="payment-service",
        deployment_context="""
        - Node.js Express API, 3 replicas in production AKS
        - PostgreSQL backend with 500GB data
        - Processes $2M/day in transactions
        - Last deployment was 2 weeks ago (v1.2.4)
        - No HPA configured, resource limits set to 500m CPU / 512Mi memory
        - Trivy scan shows 2 HIGH CVEs in node:20-alpine base image
        - No distributed tracing implemented
        - P99 latency: 890ms (SLO target: 500ms)
        """,
    )
    print("\n=== Final Recommendation ===")
    print(result)
