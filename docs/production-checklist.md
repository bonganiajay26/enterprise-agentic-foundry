# Production Readiness Checklist

**Service:** _______________  
**Version:** _______________  
**Release Date:** _______________  
**Release Lead:** _______________

> Complete ALL items before promoting to production. Items marked ⚠️ require sign-off.

---

## 1. Code Quality & Testing

| # | Check | Status | Owner |
|---|---|---|---|
| 1.1 | Unit test coverage ≥ 80% | ☐ | Dev |
| 1.2 | Integration tests passing | ☐ | Dev |
| 1.3 | E2E / smoke tests passing against staging | ☐ | QA |
| 1.4 | No CRITICAL or HIGH SonarQube issues | ☐ | Dev |
| 1.5 | No P0/P1 Snyk vulnerabilities in dependencies | ☐ | Security |
| 1.6 | Code review approved (2 approvers) | ☐ | Dev |
| 1.7 | No merge conflicts with main | ☐ | Dev |

---

## 2. Container & Supply Chain Security

| # | Check | Status | Owner |
|---|---|---|---|
| 2.1 | Trivy scan: no CRITICAL CVEs in container image | ☐ | Security |
| 2.2 | Container image signed with Cosign | ☐ | DevOps |
| 2.3 | SBOM generated and stored | ☐ | DevOps |
| 2.4 | Image uses non-root user | ☐ | Dev |
| 2.5 | Read-only root filesystem | ☐ | Dev |
| 2.6 | ALL capabilities dropped | ☐ | Dev |
| 2.7 | No privileged escalation | ☐ | Dev |
| 2.8 | Image tag is immutable (not `:latest`) | ☐ | DevOps |

---

## 3. Kubernetes Configuration

| # | Check | Status | Owner |
|---|---|---|---|
| 3.1 | Resource requests and limits set | ☐ | DevOps |
| 3.2 | Liveness probe configured and tested | ☐ | Dev |
| 3.3 | Readiness probe configured and tested | ☐ | Dev |
| 3.4 | Startup probe configured (if slow start) | ☐ | Dev |
| 3.5 | HPA configured (minReplicas ≥ 2 in prod) | ☐ | DevOps |
| 3.6 | PodDisruptionBudget configured | ☐ | DevOps |
| 3.7 | NetworkPolicy configured (deny-all + allowlist) | ☐ | Security |
| 3.8 | ServiceAccount with least privilege | ☐ | Security |
| 3.9 | Topology spread across zones | ☐ | DevOps |
| 3.10 | Graceful shutdown (terminationGracePeriodSeconds) | ☐ | Dev |

---

## 4. Configuration & Secrets

| # | Check | Status | Owner |
|---|---|---|---|
| 4.1 | No secrets in source code (Gitleaks passed) | ☐ | Security |
| 4.2 | All secrets sourced from Key Vault / Secrets Manager | ☐ | DevOps |
| 4.3 | ExternalSecret configured and syncing | ☐ | DevOps |
| 4.4 | Environment-specific config files exist (dev/staging/prod) | ☐ | Dev |
| 4.5 | Database connection string uses pool (not direct) | ☐ | Dev |
| 4.6 | All feature flags configured for production | ☐ | Dev |

---

## 5. Observability

| # | Check | Status | Owner |
|---|---|---|---|
| 5.1 | Prometheus metrics endpoint `/metrics` works | ☐ | Dev |
| 5.2 | ServiceMonitor created and scraping | ☐ | DevOps |
| 5.3 | OpenTelemetry tracing configured | ☐ | Dev |
| 5.4 | Structured JSON logging implemented | ☐ | Dev |
| 5.5 | Grafana dashboard created | ☐ | SRE |
| 5.6 | SLO defined and alert configured | ☐ | SRE |
| 5.7 | Error budget alert configured | ☐ | SRE |
| 5.8 | On-call runbook exists and linked in alert | ☐ | SRE |
| 5.9 | PagerDuty integration tested | ☐ | SRE |

---

## 6. Security ⚠️

| # | Check | Status | Owner |
|---|---|---|---|
| 6.1 | ⚠️ Threat model completed for new attack surfaces | ☐ | Security |
| 6.2 | OWASP Top 10 reviewed for web endpoints | ☐ | Security |
| 6.3 | Authentication/authorization reviewed | ☐ | Security |
| 6.4 | Rate limiting configured | ☐ | Dev |
| 6.5 | Input validation on all user inputs | ☐ | Dev |
| 6.6 | Error messages don't leak internal details | ☐ | Dev |
| 6.7 | HTTPS only (HTTP → HTTPS redirect) | ☐ | DevOps |
| 6.8 | Security headers configured | ☐ | Dev |
| 6.9 | DAST scan completed against staging | ☐ | Security |

---

## 7. Database & Data

| # | Check | Status | Owner |
|---|---|---|---|
| 7.1 | Database migrations tested (up + down) | ☐ | Dev |
| 7.2 | Migration runs without downtime (no table locks) | ☐ | Dev |
| 7.3 | Connection pool sized correctly | ☐ | Dev |
| 7.4 | Database backup verified for production | ☐ | DBA |
| 7.5 | PII fields encrypted or masked | ☐ | Security |
| 7.6 | Indexes verified for all query patterns | ☐ | Dev |

---

## 8. Deployment Strategy

| # | Check | Status | Owner |
|---|---|---|---|
| 8.1 | Deployment strategy selected (canary/rolling/blue-green) | ☐ | DevOps |
| 8.2 | Rollback procedure documented and tested | ☐ | DevOps |
| 8.3 | ArgoCD sync policy configured | ☐ | DevOps |
| 8.4 | Canary weight start: ≤ 10% | ☐ | DevOps |
| 8.5 | Success criteria defined for canary promotion | ☐ | SRE |
| 8.6 | Change ticket created and approved | ☐ | DevOps |

---

## 9. Performance

| # | Check | Status | Owner |
|---|---|---|---|
| 9.1 | Load test completed (realistic production load) | ☐ | Dev |
| 9.2 | P95 latency within SLO target | ☐ | Dev |
| 9.3 | No memory leaks under sustained load | ☐ | Dev |
| 9.4 | Startup time ≤ 60 seconds | ☐ | Dev |

---

## 10. Documentation

| # | Check | Status | Owner |
|---|---|---|---|
| 10.1 | README updated with latest changes | ☐ | Dev |
| 10.2 | API documentation updated | ☐ | Dev |
| 10.3 | Runbooks updated for any new alerts | ☐ | SRE |
| 10.4 | Changelog entry created | ☐ | Dev |
| 10.5 | Architecture diagrams updated if applicable | ☐ | Arch |
| 10.6 | Backstage catalog-info.yaml updated | ☐ | Dev |

---

## Sign-off

| Role | Name | Date | Signature |
|---|---|---|---|
| Release Lead | | | |
| Security (if applicable) | | | |
| SRE / On-Call | | | |
| Engineering Manager (P0 changes) | | | |

---

## Automated Checks (must all pass in CI)

```bash
# These gates must be green before merge to main:
✓ Gitleaks secrets scan
✓ CodeQL SAST
✓ SonarQube quality gate (coverage ≥ 80%, no critical issues)
✓ Trivy image scan (no CRITICAL CVEs)
✓ Checkov IaC scan
✓ Helm lint
✓ Unit tests
✓ Integration tests
✓ Smoke tests (staging)
```
