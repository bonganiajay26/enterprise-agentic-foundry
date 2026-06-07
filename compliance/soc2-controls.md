# SOC 2 Type II — Control Evidence Matrix

**Organization:** Your Organization  
**Period:** Annual  
**Last Updated:** 2026-06-06

---

## CC6 — Logical and Physical Access Controls

### CC6.1 — Logical Access Security Measures

| Control | Implementation | Evidence Location | Status |
|---|---|---|---|
| CC6.1.1 — Access provisioning via IDP | Azure AD / Okta SSO for all services | Azure AD audit logs | ✅ Implemented |
| CC6.1.2 — MFA enforced for all users | Conditional Access Policy + Entra ID | Conditional Access policies | ✅ Implemented |
| CC6.1.3 — Least privilege RBAC | Kubernetes RBAC + Azure RBAC | `security/opa/admission-policy.rego` | ✅ Implemented |
| CC6.1.4 — Access reviews quarterly | Quarterly entitlement review | Access review reports | 🔄 In Progress |
| CC6.1.5 — Privileged access monitored | PIM + Azure Monitor alerts | PIM audit logs | ✅ Implemented |

### CC6.2 — MFA and Authentication

| Control | Implementation | Evidence |
|---|---|---|
| MFA required for all production access | Azure AD Conditional Access | CAP-PROD-001 policy |
| Short session tokens (< 24h) | JWT expiry: 8h access, 24h refresh | Token config in Key Vault |
| Service-to-service: Workload Identity | OIDC + no static credentials | AKS workload identity config |

### CC6.6 — Encryption at Rest

| Asset | Encryption | Key Management |
|---|---|---|
| Kubernetes Secrets | AES-256 via KMS | Azure Key Vault customer-managed key |
| Database (PostgreSQL) | TDE + column encryption for PII | Key Vault rotation: 90 days |
| Container Registry (ACR) | AES-256 | Platform-managed |
| Storage (Blob) | AES-256 | Customer-managed key |
| Backup | AES-256 | Separate key per environment |

### CC6.7 — Encryption in Transit

| Flow | Encryption | Evidence |
|---|---|---|
| External HTTPS | TLS 1.3 | cert-manager, Let's Encrypt / DigiCert |
| Internal service mesh | mTLS (Istio/Cilium) | Istio PeerAuthentication policy |
| Database connections | TLS + cert validation | App config `ssl: { require: true }` |
| Key Vault access | TLS 1.2+ | Azure built-in |

---

## CC7 — System Operations

### CC7.1 — Threat Detection

| Control | Tool | Alert Routing |
|---|---|---|
| Runtime threat detection | Falco | `security/falco/falco-rules.yaml` → PagerDuty |
| Vulnerability scanning | Trivy (image + IaC) | CI pipeline gates |
| Secret scanning | Gitleaks + detect-secrets | Pre-commit + CI |
| SIEM | Azure Sentinel / Splunk | All cloud audit logs ingested |
| Anomaly detection | Azure Defender for Cloud | Security alerts |

### CC7.2 — Monitoring and Alerting

| Component | Tool | Dashboard |
|---|---|---|
| Infrastructure metrics | Prometheus + Grafana | grafana.your-domain.com/d/platform |
| Application traces | OpenTelemetry → Tempo | Grafana Tempo |
| Logs | Loki | Grafana Loki |
| SLO tracking | Prometheus + multi-burn alert | grafana.your-domain.com/d/slo |
| Cost anomalies | Azure Cost Management | FinOps dashboard |

### CC7.3 — Incident Response

Evidence: `runbooks/incident-response.md`

| Phase | Process | SLA |
|---|---|---|
| Detection | Automated alerting via Prometheus/PagerDuty | < 5 min for P0 |
| Response | On-call engineer acknowledges | < 15 min |
| Resolution | Remediation per runbook | RTO < 1hr (P0) |
| Post-mortem | Blameless review within 48h | All P0/P1 |

---

## CC8 — Change Management

### CC8.1 — Change Controls

| Control | Implementation | Evidence |
|---|---|---|
| All changes via GitOps | ArgoCD + main branch protection | Git branch policies |
| Peer review required | CODEOWNERS + 2 approvers | GitHub PR settings |
| Automated testing gates | CI must pass | GitHub Actions status checks |
| Production approval | Environment protection rules | GitHub Environments |
| Change documentation | Conventional commits + CHANGELOG | Git history |
| Rollback capability | `kubectl rollout undo` + ArgoCD sync | Runbook + GitOps history |

---

## A1 — Availability

### A1.2 — Capacity Management

| Resource | Current | Threshold | Action |
|---|---|---|---|
| AKS nodes | 9 nodes (3 AZ) | 80% CPU | Karpenter auto-scales |
| Database | 2 replicas | 80% storage | Alert + expand |
| Storage | 5TB used | 85% | Alert + extend |

### A1.3 — Backup and Recovery

| Data | Backup Frequency | Retention | Last Tested |
|---|---|---|---|
| PostgreSQL (production) | Continuous WAL + daily full | 35 days | 2026-05-15 |
| Kubernetes config (etcd) | Daily via Velero | 14 days | 2026-05-01 |
| Secrets (Key Vault) | Soft delete 90 days | N/A | Always available |
| Code (Git) | GitHub replication | Indefinite | N/A |

---

## Evidence Collection Script

```bash
# Run monthly to collect compliance evidence
./compliance/evidence-collection.sh --framework soc2 --output evidence/$(date +%Y-%m)
```

---

## Exceptions Register

| Exception | Risk | Compensating Control | Approved By | Expiry |
|---|---|---|---|---|
| Legacy service without MFA | MEDIUM | IP allowlisting + audit logging | CISO | 2026-09-01 |
