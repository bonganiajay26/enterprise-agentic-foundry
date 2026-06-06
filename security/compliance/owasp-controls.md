# OWASP Top 10 — Platform Control Mapping

## Control Matrix

| OWASP Risk | Risk ID | Platform Control | Implementation | Status |
|---|---|---|---|---|
| Broken Access Control | A01:2021 | RBAC enforcement | Kubernetes RBAC + OPA/Kyverno | ✅ Template |
| Cryptographic Failures | A02:2021 | TLS everywhere, secrets encryption | Cert-Manager, Vault, KMS | ✅ Template |
| Injection | A03:2021 | SAST scanning | CodeQL + SonarQube in CI | ✅ Template |
| Insecure Design | A04:2021 | Threat modeling | Architecture review gate | 🔄 Process |
| Security Misconfiguration | A05:2021 | IaC security scan | Checkov + Kyverno policies | ✅ Template |
| Vulnerable Components | A06:2021 | SCA + image scanning | Snyk + Trivy + SBOM | ✅ Template |
| Auth Failures | A07:2021 | MFA + short-lived tokens | OIDC + Workload Identity | ✅ Template |
| Software & Data Integrity | A08:2021 | Image signing, supply chain | Cosign + SBOM | ✅ Template |
| Security Logging Failures | A09:2021 | Centralized logging | Loki + Cloud audit logs | ✅ Template |
| Server-Side Request Forgery | A10:2021 | Network policies, WAF | NetworkPolicy + WAF rules | ✅ Template |

---

## OWASP ASVS Checklist (Level 2)

### V1 — Architecture, Design & Threat Modeling
- [x] Security architecture documented
- [x] All application components identified
- [x] Trust levels defined per component
- [ ] Threat model created per service (requires per-service effort)

### V2 — Authentication
- [x] Passwords never stored in plaintext
- [x] MFA supported
- [x] OIDC/OAuth2 integration
- [x] Session tokens rotated after authentication

### V3 — Session Management
- [x] Short session token lifetimes (< 24h)
- [x] Secure, HttpOnly, SameSite cookie flags
- [x] Session invalidation on logout

### V4 — Access Control
- [x] Principle of least privilege enforced
- [x] RBAC model implemented
- [x] Kubernetes RBAC + IRSA/Workload Identity

### V7 — Error Handling & Logging
- [x] No sensitive data in logs
- [x] Audit logs for all privileged operations
- [x] Log integrity protected (WORM storage)
- [x] Centralized SIEM integration

### V9 — Communication
- [x] TLS 1.2+ enforced everywhere
- [x] mTLS between services (Istio)
- [x] Certificate rotation automated (cert-manager)

### V10 — Malicious Code
- [x] SAST in CI pipeline
- [x] Dependency scanning (Snyk)
- [x] Container scanning (Trivy)
- [x] Runtime security (Falco)

### V14 — Configuration
- [x] IaC security scanning (Checkov)
- [x] Secrets not in source code (Gitleaks)
- [x] Pod Security Standards enforced
- [x] Read-only root filesystem

---

## SOC 2 Control Mapping

| SOC 2 Control | Platform Mechanism |
|---|---|
| CC6.1 — Logical access | Kubernetes RBAC + IAM |
| CC6.2 — Multi-factor auth | OIDC + MFA enforcement |
| CC6.3 — Removal of access | Automated offboarding via IaC |
| CC6.6 — Encryption at rest | KMS keys for all storage |
| CC6.7 — Encryption in transit | TLS 1.2+, mTLS (Istio) |
| CC7.1 — Threat detection | Falco + SIEM |
| CC7.2 — Monitoring | Prometheus + Grafana + alerting |
| CC7.3 — Incident response | Runbooks + PagerDuty integration |
| CC8.1 — Change management | GitOps + approval workflows |
| A1.2 — Capacity management | Kubernetes HPA + cluster autoscaler |
| A1.3 — Backups | Velero + cloud-native backup |
