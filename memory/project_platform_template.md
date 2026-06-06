---
name: universal-platform-template
description: User's primary project is the Universal Agentic DevOps Platform — a greenfield enterprise platform template covering CI/CD, IaC, Security, Observability, Backstage, and Agentic AI
metadata:
  type: project
---

User is building/maintaining the Universal Agentic DevOps Platform at `C:\Users\ajayd\Universal Agentic DevOps Template`.

**Why:** Enterprise platform blueprint for any organization — cloud-agnostic, security-first, AI-augmented.

**How to apply:** When asked to extend, modify, or add components, follow the existing patterns (LangGraph for agents, Terraform modules per cloud, Helm for Kubernetes, Mermaid for diagrams). All agents use AzureChatOpenAI with LangGraph StateGraph pattern.

**Key design decisions:**
- Three cloud targets: Azure (primary), AWS, GCP — each with own Terraform module
- CI/CD: GitHub Actions (primary), Azure DevOps, GitLab CI
- Agents: Supervisor → [DevOps, Security, Cost, Incident, Architecture, Documentation] pattern
- Production changes always require human approval (interrupt_before in LangGraph)
- Audit logger + safety filter are mandatory governance components
