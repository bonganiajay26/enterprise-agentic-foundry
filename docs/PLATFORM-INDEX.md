# Platform File Index

## All Generated Files

### Architecture & Documentation
| File | Purpose |
|---|---|
| [README.md](../README.md) | Platform overview, quick start, tech decisions |
| [architecture/01-current-state.md](../architecture/01-current-state.md) | Current state assessment + C4 diagrams (Mermaid) |
| [architecture/02-gap-analysis.md](../architecture/02-gap-analysis.md) | Risk matrix, technical debt, FinOps gaps |
| [architecture/03-target-state.md](../architecture/03-target-state.md) | Future state diagrams, HA/DR, multi-cloud, Agentic AI |
| [docs/executive-summary.md](executive-summary.md) | Business case, ROI, investment summary |
| [docs/implementation-roadmap.md](implementation-roadmap.md) | 90-day phased roadmap with Gantt chart |

### CI/CD
| File | Purpose |
|---|---|
| [.github/workflows/ci-universal.yml](../.github/workflows/ci-universal.yml) | Universal GitHub Actions pipeline |
| [.github/workflows/security-scan.yml](../.github/workflows/security-scan.yml) | Weekly security scanning workflow |
| [azure-pipelines/ci-template.yml](../azure-pipelines/ci-template.yml) | Azure DevOps pipeline template |
| [gitlab-ci/.gitlab-ci.yml](../gitlab-ci/.gitlab-ci.yml) | GitLab CI/CD universal pipeline |

### Docker
| File | Purpose |
|---|---|
| [docker/Dockerfile.node](../docker/Dockerfile.node) | Multi-stage Node.js production image |
| [docker/Dockerfile.python](../docker/Dockerfile.python) | Multi-stage Python production image |
| [docker/docker-compose.dev.yml](../docker/docker-compose.dev.yml) | Full dev stack with observability |

### Helm
| File | Purpose |
|---|---|
| [helm/base-service/Chart.yaml](../helm/base-service/Chart.yaml) | Helm chart metadata |
| [helm/base-service/values.yaml](../helm/base-service/values.yaml) | Full production values (HPA, PDB, NetworkPolicy, etc.) |
| [helm/base-service/templates/deployment.yaml](../helm/base-service/templates/deployment.yaml) | Kubernetes Deployment template |
| [helm/base-service/templates/_helpers.tpl](../helm/base-service/templates/_helpers.tpl) | Helm template helpers |

### Terraform
| File | Purpose |
|---|---|
| [terraform/azure/main.tf](../terraform/azure/main.tf) | Azure AKS + ACR + Key Vault + VNet |
| [terraform/azure/variables.tf](../terraform/azure/variables.tf) | Azure module variables |
| [terraform/aws/main.tf](../terraform/aws/main.tf) | AWS EKS + ECR + VPC + KMS |
| [terraform/gcp/main.tf](../terraform/gcp/main.tf) | GCP GKE + Artifact Registry + KMS |

### Security
| File | Purpose |
|---|---|
| [security/policies/pod-security-policy.yaml](../security/policies/pod-security-policy.yaml) | Kyverno ClusterPolicy + NetworkPolicy |
| [security/scanning/trivy-config.yaml](../security/scanning/trivy-config.yaml) | Trivy scanner configuration |
| [security/compliance/owasp-controls.md](../security/compliance/owasp-controls.md) | OWASP Top 10 + ASVS + SOC 2 mapping |

### Monitoring & Observability
| File | Purpose |
|---|---|
| [monitoring/prometheus.yml](../monitoring/prometheus.yml) | Prometheus scrape config + remote write |
| [monitoring/rules/slo-rules.yml](../monitoring/rules/slo-rules.yml) | SLO alert rules (error budget burn rate) |
| [observability/otel-collector.yaml](../observability/otel-collector.yaml) | OpenTelemetry Collector full config |

### Backstage
| File | Purpose |
|---|---|
| [backstage/app-config/app-config.yaml](../backstage/app-config/app-config.yaml) | Full Backstage configuration |
| [backstage/templates/microservice-template.yaml](../backstage/templates/microservice-template.yaml) | Software template (full-stack microservice) |

### Agentic AI
| File | Purpose |
|---|---|
| [agentic-ai/agents/supervisor.py](../agentic-ai/agents/supervisor.py) | Supervisor agent + routing |
| [agentic-ai/agents/devops_agent.py](../agentic-ai/agents/devops_agent.py) | DevOps agent (LangGraph) |
| [agentic-ai/agents/security_agent.py](../agentic-ai/agents/security_agent.py) | Security agent (LangGraph) |
| [agentic-ai/governance/audit_logger.py](../agentic-ai/governance/audit_logger.py) | Immutable audit logger |
| [agentic-ai/governance/safety_filter.py](../agentic-ai/governance/safety_filter.py) | Pre-execution safety checks |
| [agentic-ai/requirements.txt](../agentic-ai/requirements.txt) | Python dependencies |

### Runbooks
| File | Purpose |
|---|---|
| [runbooks/incident-response.md](../runbooks/incident-response.md) | Full incident response procedure + post-mortem |
| [runbooks/dr-failover.md](../runbooks/dr-failover.md) | Disaster recovery failover procedure |

### Scripts
| File | Purpose |
|---|---|
| [scripts/bootstrap.sh](../scripts/bootstrap.sh) | One-command platform bootstrap |

---

## Pending / Extend As Needed

| Component | Status | Notes |
|---|---|---|
| Cost Agent (LangGraph) | Stub | Extend `agentic-ai/agents/cost_agent.py` |
| Incident Agent | Stub | Extend `agentic-ai/agents/incident_agent.py` |
| Architecture Agent | Stub | Extend `agentic-ai/agents/architecture_agent.py` |
| Helm chart: platform-services | Pending | ArgoCD, cert-manager, Kyverno umbrella chart |
| Terraform: OpenTofu equivalents | Pending | Direct symlink/copy of Terraform modules |
| Grafana dashboards JSON | Pending | Import from grafana.com community dashboards |
| Backstage catalog-info templates | Pending | Per-service catalog-info.yaml skeleton |
| Jenkins pipeline | Pending | Jenkinsfile equivalent of GitHub Actions pipeline |
| Chaos engineering runbooks | Pending | Chaos Mesh experiment templates |
