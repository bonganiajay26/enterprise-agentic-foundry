# Contributing to the Universal Agentic DevOps Platform

## Development Setup

```bash
git clone https://github.com/your-org/enterprise-agentic-foundry
cd enterprise-agentic-foundry

# Install pre-commit hooks (validates secrets, linting, IaC before each commit)
pip install pre-commit
pre-commit install
pre-commit install --hook-type commit-msg
```

## Branch Strategy

```
main          ← Production-ready, protected
develop       ← Integration branch
feature/*     ← New features (branch from develop)
fix/*         ← Bug fixes
release/*     ← Release preparation
hotfix/*      ← Critical production fixes (branch from main)
```

## Commit Convention (Conventional Commits)

```
feat:     New feature
fix:      Bug fix
docs:     Documentation only
style:    Formatting, no logic change
refactor: Code change without new feature or fix
test:     Adding or fixing tests
chore:    Build process or tooling changes
ci:       CI/CD pipeline changes
security: Security fixes
```

Examples:
```
feat(agents): add performance agent with database query analysis
fix(helm): correct HPA minReplicas for production values
docs(runbooks): add cluster-upgrade procedure with rollback steps
ci(github-actions): add dependency review step to CI pipeline
```

## Pull Request Requirements

All PRs must:
- [ ] Target `develop` (not `main`)
- [ ] Pass all CI checks (green status checks)
- [ ] Have 1+ approval from CODEOWNERS
- [ ] Include tests for new functionality
- [ ] Update documentation if applicable
- [ ] Follow commit convention

## Directory Conventions

| Directory | Purpose |
|---|---|
| `templates/` | Complete working application starters (has runnable code) |
| `helm/` | Kubernetes Helm charts |
| `terraform/` | Cloud-specific IaC modules |
| `clouds/` | Cloud service extensions (WAF, CDN, DNS) |
| `shared-modules/` | Reusable Terraform modules |
| `agentic-ai/agents/` | LangGraph agents (one file per agent) |
| `agentic-ai/autogen/` | AutoGen multi-agent workflows |
| `agentic-ai/rag/` | RAG pipeline components |
| `agentic-ai/tools/` | MCP server and tool implementations |
| `backstage/templates/` | Backstage scaffolder templates |
| `security/` | Security policies, rules, compliance |
| `governance/` | OPA/Rego policies for cost and tagging |
| `compliance/` | Compliance evidence and controls |
| `monitoring/` | Prometheus, Grafana, Alertmanager |
| `observability/` | OpenTelemetry, Loki, Tempo |
| `runbooks/` | Operational runbooks (one file per scenario) |
| `scripts/` | Utility scripts |
| `tests/` | Integration and smoke tests |

## Adding a New Agent

1. Create `agentic-ai/agents/<agent-name>_agent.py`
2. Follow the pattern: `State` → tools → `call_model` → `should_continue` → `build_<name>_agent()`
3. Add the agent to `supervisor.py` routing
4. Add a stub node in `supervisor.py` `placeholder_agent_node`
5. Update `docs/PLATFORM-INDEX.md`

## Adding a New Backstage Template

1. Create `backstage/templates/<name>-template.yaml`
2. Follow `apiVersion: scaffolder.backstage.io/v1beta3`
3. Add rich parameter forms with validation
4. Register the template in `backstage/app-config/app-config.yaml`

## Security Guidelines

- Never commit secrets (Gitleaks will block it)
- New OPA policies go in `governance/policies/`
- New Falco rules go in `security/falco/falco-rules.yaml`
- Security fixes should be tagged `security:` in commit message
- CVSS ≥ 7.0 vulnerabilities require same-day fix
