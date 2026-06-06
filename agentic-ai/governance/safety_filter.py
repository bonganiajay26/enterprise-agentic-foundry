"""
Safety Filter — Agentic AI Governance Layer

Prevents agents from taking destructive, unauthorized, or out-of-scope actions.
Applied as a pre-execution guard on all tool calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class SafetyDecision:
    allowed: bool
    reason: str
    requires_approval: bool = False
    risk_level: str = "low"


class SafetyFilter:
    """
    Rule-based safety filter applied before any agent tool execution.
    Implements deny-by-default for destructive production operations.
    """

    # Patterns that are always blocked
    BLOCKED_PATTERNS = [
        r"rm\s+-rf\s+/",
        r"DROP\s+TABLE",
        r"DELETE\s+FROM\s+\w+\s*;?\s*$",
        r"kubectl\s+delete\s+namespace\s+(production|staging)",
        r"terraform\s+destroy\s+--auto-approve",
        r"git\s+push\s+--force\s+origin\s+main",
    ]

    # Production actions always require human approval
    APPROVAL_REQUIRED_PRODUCTION = {
        "trigger_deployment",
        "rollback_deployment",
        "scale_deployment",
        "delete_resource",
        "rotate_secret",
        "apply_network_policy",
    }

    # Maximum canary weight without approval
    MAX_AUTONOMOUS_CANARY_WEIGHT = 10

    def check_tool_call(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        environment: str,
        agent_name: str,
    ) -> SafetyDecision:
        """Evaluate whether a tool call is safe to execute."""

        # Check blocked command patterns
        for arg_value in tool_args.values():
            if isinstance(arg_value, str):
                for pattern in self.BLOCKED_PATTERNS:
                    if re.search(pattern, arg_value, re.IGNORECASE):
                        return SafetyDecision(
                            allowed=False,
                            reason=f"Blocked: command matches unsafe pattern '{pattern}'",
                            risk_level="critical",
                        )

        # Production approval gate
        if environment == "production" and tool_name in self.APPROVAL_REQUIRED_PRODUCTION:
            return SafetyDecision(
                allowed=True,
                reason=f"Production {tool_name} requires human approval",
                requires_approval=True,
                risk_level="critical",
            )

        # Canary weight guard
        if tool_name == "trigger_deployment":
            canary_weight = tool_args.get("canary_weight", 0)
            if canary_weight > self.MAX_AUTONOMOUS_CANARY_WEIGHT:
                return SafetyDecision(
                    allowed=True,
                    reason=f"Canary weight {canary_weight}% exceeds autonomous limit of {self.MAX_AUTONOMOUS_CANARY_WEIGHT}%",
                    requires_approval=True,
                    risk_level="high",
                )

        # Namespace protection
        protected_namespaces = {"kube-system", "production", "cert-manager", "monitoring"}
        target_ns = tool_args.get("namespace", "")
        if target_ns in protected_namespaces and tool_name in {"delete_resource", "apply_policy"}:
            return SafetyDecision(
                allowed=True,
                reason=f"Operation on protected namespace '{target_ns}' requires approval",
                requires_approval=True,
                risk_level="high",
            )

        return SafetyDecision(
            allowed=True,
            reason="Passed all safety checks",
            risk_level="low",
        )

    def check_llm_output(self, output: str) -> SafetyDecision:
        """Scan LLM output for potential prompt injection or sensitive data leakage."""

        # Check for potential secret exposure
        secret_patterns = [
            r"[A-Za-z0-9+/]{40,}={0,2}",  # Base64 encoded secrets
            r"(password|secret|token|key)\s*[:=]\s*[^\s]{8,}",
            r"-----BEGIN\s+(RSA|EC|OPENSSH|PRIVATE|CERTIFICATE)",
        ]

        for pattern in secret_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                return SafetyDecision(
                    allowed=False,
                    reason="Output contains potential secret or credential — redacted for safety",
                    risk_level="critical",
                )

        # Check for prompt injection attempts
        injection_patterns = [
            r"ignore\s+(previous|all|above)\s+instructions",
            r"you\s+are\s+now\s+(a|an)\s+(?!the)",
            r"system\s*prompt\s*:",
            r"<\|im_start\|>",
        ]

        for pattern in injection_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                return SafetyDecision(
                    allowed=False,
                    reason="Potential prompt injection detected in output",
                    risk_level="critical",
                )

        return SafetyDecision(allowed=True, reason="Output passed safety checks")


# Global safety filter instance
safety_filter = SafetyFilter()
