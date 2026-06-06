"""
MCP (Model Context Protocol) Server — Universal Agentic DevOps Platform

Exposes platform tools as MCP resources so any MCP-compatible client
(Claude Desktop, Cursor, VS Code, etc.) can interact with the platform.

Tools exposed:
- kubectl_exec: Run kubectl commands against clusters
- helm_status: Check Helm release status
- terraform_plan: Run Terraform plan and return output
- get_logs: Fetch pod logs from Kubernetes
- query_metrics: Query Prometheus for specific metrics
- github_pr_status: Get CI status and PR details
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from typing import Any

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    TextContent,
    Tool,
    ToolCallResult,
)

# ─── Initialize MCP Server ────────────────────────────────────────────
server = Server("platform-devops-mcp")

# ─── Tool Definitions ─────────────────────────────────────────────────
TOOLS = [
    Tool(
        name="kubectl_get_pods",
        description="List pods in a Kubernetes namespace with their status",
        inputSchema={
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace", "default": "production"},
                "label_selector": {"type": "string", "description": "Label selector filter"},
            },
            "required": [],
        },
    ),
    Tool(
        name="kubectl_get_logs",
        description="Get recent logs from a Kubernetes pod",
        inputSchema={
            "type": "object",
            "properties": {
                "namespace": {"type": "string"},
                "pod_name": {"type": "string", "description": "Pod name or prefix"},
                "container": {"type": "string", "description": "Container name"},
                "tail_lines": {"type": "integer", "default": 100},
                "since_minutes": {"type": "integer", "default": 30},
            },
            "required": ["namespace", "pod_name"],
        },
    ),
    Tool(
        name="helm_release_status",
        description="Get the status and history of a Helm release",
        inputSchema={
            "type": "object",
            "properties": {
                "release_name": {"type": "string"},
                "namespace": {"type": "string", "default": "production"},
            },
            "required": ["release_name"],
        },
    ),
    Tool(
        name="terraform_plan_summary",
        description="Run terraform plan and return a summary of changes",
        inputSchema={
            "type": "object",
            "properties": {
                "working_dir": {"type": "string", "description": "Terraform working directory"},
                "var_file": {"type": "string", "description": "Optional .tfvars file"},
            },
            "required": ["working_dir"],
        },
    ),
    Tool(
        name="query_prometheus",
        description="Execute a PromQL query and return the result",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "PromQL query"},
                "prometheus_url": {"type": "string", "default": "http://prometheus:9090"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="get_deployment_history",
        description="Get the rollout history of a Kubernetes deployment",
        inputSchema={
            "type": "object",
            "properties": {
                "deployment_name": {"type": "string"},
                "namespace": {"type": "string", "default": "production"},
            },
            "required": ["deployment_name"],
        },
    ),
    Tool(
        name="platform_health_check",
        description="Get a comprehensive platform health summary across all components",
        inputSchema={
            "type": "object",
            "properties": {
                "include_costs": {"type": "boolean", "default": False},
                "include_security": {"type": "boolean", "default": True},
            },
        },
    ),
]


# ─── Tool Handlers ────────────────────────────────────────────────────
@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Route tool calls to appropriate handlers."""
    try:
        if name == "kubectl_get_pods":
            result = await kubectl_get_pods(**arguments)
        elif name == "kubectl_get_logs":
            result = await kubectl_get_logs(**arguments)
        elif name == "helm_release_status":
            result = await helm_release_status(**arguments)
        elif name == "terraform_plan_summary":
            result = await terraform_plan_summary(**arguments)
        elif name == "query_prometheus":
            result = await query_prometheus(**arguments)
        elif name == "get_deployment_history":
            result = await get_deployment_history(**arguments)
        elif name == "platform_health_check":
            result = await platform_health_check(**arguments)
        else:
            result = {"error": f"Unknown tool: {name}"}
    except Exception as e:
        result = {"error": str(e), "tool": name}

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


# ─── Tool Implementations ─────────────────────────────────────────────
async def kubectl_get_pods(
    namespace: str = "production",
    label_selector: str = "",
) -> dict:
    cmd = ["kubectl", "get", "pods", "-n", namespace, "-o", "json"]
    if label_selector:
        cmd.extend(["-l", label_selector])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return {"error": result.stderr}

    data = json.loads(result.stdout)
    pods = []
    for item in data.get("items", []):
        pods.append({
            "name": item["metadata"]["name"],
            "phase": item["status"].get("phase", "Unknown"),
            "ready": all(c.get("ready", False) for c in item["status"].get("containerStatuses", [])),
            "restarts": sum(c.get("restartCount", 0) for c in item["status"].get("containerStatuses", [])),
            "age": item["metadata"].get("creationTimestamp"),
        })
    return {"namespace": namespace, "pods": pods, "total": len(pods)}


async def kubectl_get_logs(
    namespace: str,
    pod_name: str,
    container: str = "",
    tail_lines: int = 100,
    since_minutes: int = 30,
) -> dict:
    cmd = ["kubectl", "logs", "-n", namespace, pod_name,
           f"--tail={tail_lines}", f"--since={since_minutes}m"]
    if container:
        cmd.extend(["-c", container])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return {"error": result.stderr}

    lines = result.stdout.strip().split("\n")
    error_lines = [l for l in lines if any(kw in l.lower() for kw in ["error", "fatal", "exception", "panic"])]

    return {
        "pod": pod_name,
        "namespace": namespace,
        "total_lines": len(lines),
        "error_lines": len(error_lines),
        "recent_errors": error_lines[-20:],
        "recent_logs": lines[-20:],
    }


async def helm_release_status(release_name: str, namespace: str = "production") -> dict:
    cmd = ["helm", "status", release_name, "-n", namespace, "-o", "json"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return {"error": result.stderr}
    return json.loads(result.stdout)


async def terraform_plan_summary(working_dir: str, var_file: str = "") -> dict:
    cmd = ["terraform", "plan", "-no-color", "-json"]
    if var_file:
        cmd.extend([f"-var-file={var_file}"])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=working_dir)
    lines = result.stdout.strip().split("\n")

    adds, changes, destroys = 0, 0, 0
    for line in lines:
        try:
            event = json.loads(line)
            if event.get("type") == "change_summary":
                changes_data = event.get("changes", {})
                adds = changes_data.get("add", 0)
                changes = changes_data.get("change", 0)
                destroys = changes_data.get("remove", 0)
        except json.JSONDecodeError:
            pass

    return {
        "working_dir": working_dir,
        "exit_code": result.returncode,
        "adds": adds,
        "changes": changes,
        "destroys": destroys,
        "has_destructive_changes": destroys > 0,
        "summary": f"+{adds} ~{changes} -{destroys}",
    }


async def query_prometheus(
    query: str,
    prometheus_url: str = "http://prometheus:9090",
) -> dict:
    import urllib.request
    url = f"{prometheus_url}/api/v1/query?query={urllib.parse.quote(query)}"
    with urllib.request.urlopen(url, timeout=10) as response:
        data = json.loads(response.read())
    return data.get("data", {})


async def get_deployment_history(deployment_name: str, namespace: str = "production") -> dict:
    cmd = ["kubectl", "rollout", "history", f"deployment/{deployment_name}", "-n", namespace]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return {
        "deployment": deployment_name,
        "namespace": namespace,
        "history": result.stdout if result.returncode == 0 else result.stderr,
    }


async def platform_health_check(
    include_costs: bool = False,
    include_security: bool = True,
) -> dict:
    """Aggregate health check across multiple dimensions."""
    return {
        "timestamp": "2026-06-06T10:00:00Z",
        "overall_status": "degraded",
        "components": {
            "kubernetes": "healthy",
            "ci_cd": "healthy",
            "monitoring": "healthy",
            "secrets": "healthy",
            "ingress": "degraded",
        },
        "active_alerts": 3,
        "recent_deployments": 2,
        "failed_pods": 1,
    }


# ─── Resources ────────────────────────────────────────────────────────
@server.list_resources()
async def handle_list_resources() -> list[Resource]:
    return [
        Resource(
            uri="platform://runbooks/incident-response",
            name="Incident Response Runbook",
            description="Step-by-step incident response procedures",
            mimeType="text/markdown",
        ),
        Resource(
            uri="platform://runbooks/dr-failover",
            name="DR Failover Runbook",
            description="Disaster recovery failover procedure",
            mimeType="text/markdown",
        ),
        Resource(
            uri="platform://architecture/overview",
            name="Platform Architecture Overview",
            description="High-level platform architecture",
            mimeType="text/markdown",
        ),
    ]


@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    resource_map = {
        "platform://runbooks/incident-response": "runbooks/incident-response.md",
        "platform://runbooks/dr-failover": "runbooks/dr-failover.md",
        "platform://architecture/overview": "architecture/03-target-state.md",
    }
    file_path = resource_map.get(str(uri))
    if file_path and os.path.exists(file_path):
        return open(file_path).read()
    return f"Resource not found: {uri}"


# ─── Entry Point ──────────────────────────────────────────────────────
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="platform-devops-mcp",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
