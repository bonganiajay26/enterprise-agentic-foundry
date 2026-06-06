"""
Audit Logger — Agentic AI Governance Layer

All agent actions, tool calls, and decisions are logged to an immutable audit trail.
Supports: structured logging, cloud audit log integration, compliance reporting.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

import structlog

# ─── Structured logging setup ─────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()


class AuditEvent:
    """Represents a single auditable agent action."""

    def __init__(
        self,
        agent_name: str,
        action_type: Literal[
            "tool_call", "decision", "deployment", "security_scan",
            "approval_request", "approval_granted", "approval_denied",
            "rollback", "escalation", "compliance_check",
        ],
        action: str,
        actor: str = "ai-agent",
        environment: str = "unknown",
        resource: str = "",
        outcome: Literal["success", "failure", "pending", "denied"] = "success",
        details: dict[str, Any] | None = None,
        risk_level: Literal["low", "medium", "high", "critical"] = "low",
    ):
        self.event_id = str(uuid.uuid4())
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.agent_name = agent_name
        self.action_type = action_type
        self.action = action
        self.actor = actor
        self.environment = environment
        self.resource = resource
        self.outcome = outcome
        self.details = details or {}
        self.risk_level = risk_level
        self.session_id = structlog.contextvars.get_contextvars().get("session_id", "")

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "agent_name": self.agent_name,
            "action_type": self.action_type,
            "action": self.action,
            "actor": self.actor,
            "environment": self.environment,
            "resource": self.resource,
            "outcome": self.outcome,
            "details": self.details,
            "risk_level": self.risk_level,
            "session_id": self.session_id,
        }


class AuditLogger:
    """
    Centralized audit logger for all agent actions.
    Logs to: stdout (structured JSON), cloud audit logs, optional SIEM webhook.
    """

    def __init__(self, siem_webhook_url: str = ""):
        self.siem_webhook_url = siem_webhook_url or os.environ.get("SIEM_WEBHOOK_URL", "")

    def log(self, event: AuditEvent) -> None:
        log_data = event.to_dict()

        # Always log to structured stdout
        log_fn = logger.warning if event.risk_level in ("high", "critical") else logger.info
        log_fn(
            "agent_audit_event",
            **log_data,
        )

        # Send to SIEM for high/critical risk actions
        if self.siem_webhook_url and event.risk_level in ("high", "critical"):
            self._send_to_siem(log_data)

        # Critical actions: also write to immutable audit log file
        if event.risk_level == "critical":
            self._write_to_immutable_log(log_data)

    def log_tool_call(
        self,
        agent_name: str,
        tool_name: str,
        tool_args: dict,
        result: dict,
        environment: str = "unknown",
    ) -> None:
        # Redact sensitive values from args before logging
        safe_args = self._redact_sensitive(tool_args)
        event = AuditEvent(
            agent_name=agent_name,
            action_type="tool_call",
            action=f"tool:{tool_name}",
            environment=environment,
            outcome="success" if not result.get("error") else "failure",
            details={"args": safe_args, "result_keys": list(result.keys())},
            risk_level=self._assess_tool_risk(tool_name, tool_args),
        )
        self.log(event)

    def log_deployment(
        self,
        agent_name: str,
        service: str,
        image_tag: str,
        environment: str,
        strategy: str,
        approved_by: str = "",
        outcome: str = "pending",
    ) -> None:
        risk = "critical" if environment == "production" else "medium"
        event = AuditEvent(
            agent_name=agent_name,
            action_type="deployment",
            action=f"deploy:{service}:{image_tag}",
            environment=environment,
            resource=service,
            outcome=outcome,
            details={
                "image_tag": image_tag,
                "strategy": strategy,
                "approved_by": approved_by,
            },
            risk_level=risk,
        )
        self.log(event)

    def _assess_tool_risk(self, tool_name: str, args: dict) -> Literal["low", "medium", "high", "critical"]:
        critical_tools = {"rollback_deployment", "trigger_deployment", "delete_resource"}
        high_tools = {"create_remediation_pr", "rotate_secret", "scale_deployment"}
        if tool_name in critical_tools:
            env = args.get("environment", "")
            return "critical" if env == "production" else "high"
        if tool_name in high_tools:
            return "high"
        return "low"

    def _redact_sensitive(self, data: dict) -> dict:
        sensitive_keys = {"password", "secret", "token", "key", "credential", "api_key"}
        return {
            k: "***REDACTED***" if any(s in k.lower() for s in sensitive_keys) else v
            for k, v in data.items()
        }

    def _send_to_siem(self, data: dict) -> None:
        try:
            import urllib.request
            payload = json.dumps(data).encode()
            req = urllib.request.Request(
                self.siem_webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            logger.error("siem_webhook_failed", error=str(e))

    def _write_to_immutable_log(self, data: dict) -> None:
        log_path = os.environ.get("AUDIT_LOG_PATH", "/var/log/agent-audit/critical.jsonl")
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a") as f:
                f.write(json.dumps(data) + "\n")
        except Exception as e:
            logger.error("immutable_log_write_failed", error=str(e))


# Global audit logger instance
audit_logger = AuditLogger()
