# Incident Response Runbook

## Overview

This runbook covers the standard incident response procedure for the Universal Agentic DevOps Platform.

**Incident Severity Levels**

| Severity | Definition | Response Time | Examples |
|---|---|---|---|
| SEV-1 / P0 | Complete service outage, data loss, security breach | Immediate (< 5 min) | Production down, DB corruption |
| SEV-2 / P1 | Major feature unavailable, SLO burning fast (>14x) | < 15 minutes | Payment failures, auth down |
| SEV-3 / P2 | Degraded performance, minor feature down | < 1 hour | Slow responses, dashboard broken |
| SEV-4 / P3 | Low-impact issue, no user facing | Next business day | Cosmetic bugs, slow batch jobs |

---

## Phase 1 — Detection & Triage (0–15 min)

### 1.1 Alert Fires
- PagerDuty/OpsGenie pages on-call engineer
- Alert includes: service, metric, threshold, dashboard link
- Acknowledge within 5 minutes

### 1.2 Initial Assessment
```bash
# Check pod health
kubectl get pods -n production --field-selector=status.phase!=Running

# Check recent deployments
kubectl rollout history deployment/<service-name> -n production

# Check error rates (Grafana query)
# sum(rate(http_requests_total{status=~"5..",namespace="production"}[5m])) by (service)

# Check recent logs
kubectl logs -n production -l app=<service-name> --since=10m --tail=100

# Check HPA status
kubectl get hpa -n production
```

### 1.3 Declare Incident
1. Post in `#incidents` Slack channel: `@here SEV-X incident: <description>`
2. Create incident in PagerDuty/StatusPage
3. Assign Incident Commander (IC) and Communications Lead

---

## Phase 2 — Mitigation (15–60 min)

### 2.1 Quick Mitigations

**Option A — Rollback Deployment**
```bash
# Check rollout history
kubectl rollout history deployment/<name> -n production

# Rollback to previous version
kubectl rollout undo deployment/<name> -n production

# Rollback to specific revision
kubectl rollout undo deployment/<name> -n production --to-revision=<N>

# Monitor rollback
kubectl rollout status deployment/<name> -n production -w
```

**Option B — Scale Up Replicas**
```bash
kubectl scale deployment/<name> -n production --replicas=<N>
```

**Option C — Feature Flag Disable**
```bash
# Via LaunchDarkly/Unleash API
curl -X PATCH https://flags.your-domain.com/api/v1/flags/<flag-name> \
  -H "Authorization: Bearer $FLAG_TOKEN" \
  -d '{"enabled": false}'
```

**Option D — Traffic Shift (Istio)**
```bash
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: <service>
  namespace: production
spec:
  http:
    - route:
        - destination:
            host: <service>
            subset: stable
          weight: 100
        - destination:
            host: <service>
            subset: canary
          weight: 0
EOF
```

**Option E — Circuit Breaker (Emergency)**
```bash
# Return 503 from ingress while fixing
kubectl annotate ingress <name> -n production \
  nginx.ingress.kubernetes.io/server-snippet="return 503;"
```

### 2.2 Communicate
- Update StatusPage: "Investigating issue with <service>"
- Post to `#incidents` every 15 minutes
- Notify stakeholders for SEV-1/SEV-2

---

## Phase 3 — Resolution & Verification (60+ min)

### 3.1 Verify Fix
```bash
# Check error rate normalized
kubectl top pods -n production

# Verify SLO recovery
# Dashboard: https://grafana.your-domain.com/d/slo-dashboard

# Run smoke tests
./scripts/smoke-test.sh production
```

### 3.2 Restore Normal Operations
1. Remove any temporary mitigations (circuit breakers, traffic shifts)
2. Confirm monitoring shows green
3. Resolve PagerDuty incident
4. Update StatusPage to "Resolved"
5. Post resolution in `#incidents`

---

## Phase 4 — Post-Incident Review (within 48h for P0/P1)

### Post-Mortem Template

```markdown
## Incident Post-Mortem: <Title>

**Date:** YYYY-MM-DD
**Severity:** SEV-X
**Duration:** Xh Ym
**Services Affected:** 
**Incident Commander:**
**Author:**

### Impact
- Users affected:
- Revenue impact:
- SLO burn:

### Timeline
| Time | Event |
|------|-------|
| HH:MM | Alert fired |
| HH:MM | On-call engaged |
| HH:MM | Root cause identified |
| HH:MM | Fix deployed |
| HH:MM | Incident resolved |

### Root Cause
<5 Whys analysis>

### Contributing Factors
1.
2.

### What Went Well
1.
2.

### What Went Poorly
1.
2.

### Action Items
| Action | Owner | Due Date | Priority |
|--------|-------|----------|----------|
| | | | |
```

---

## Runbook Index

| Scenario | Runbook |
|---|---|
| Pod CrashLoop | [pod-crashloop.md](./pod-crashloop.md) |
| Node NotReady | [node-not-ready.md](./node-not-ready.md) |
| OOM Kill | [oom-kill.md](./oom-kill.md) |
| Database Connection Exhaustion | [db-connection-pool.md](./db-connection-pool.md) |
| Certificate Expiry | [cert-expiry.md](./cert-expiry.md) |
| SLO Burn Rate High | [slo-burn.md](./slo-burn.md) |
| Security Alert (Falco) | [security-alert.md](./security-alert.md) |
| Kubernetes Cluster Upgrade | [cluster-upgrade.md](./cluster-upgrade.md) |
| DR Failover | [dr-failover.md](./dr-failover.md) |
