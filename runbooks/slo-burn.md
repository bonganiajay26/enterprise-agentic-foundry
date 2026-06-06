# Runbook: SLO Error Budget Burning Fast

**Alert:** `SLOAvailabilityBurn_Critical` — burning at 14.4x rate  
**Alert:** `SLOAvailabilityBurn_Warning` — burning at 6x rate  
**Severity:** P1 (Critical burn), P2 (Warning burn)

---

## Understanding the Alert

Error budget burn rate of X means:
- **14.4x**: Will exhaust 2% of monthly budget in **1 hour**
- **6x**: Will exhaust 5% of monthly budget in **6 hours**  
- **3x**: Will exhaust 10% of monthly budget in **3.3 days**

With a 99.9% SLO, you have **43.8 minutes** of downtime per month.

---

## Immediate Triage (0–5 min)

```bash
# Check current error rate
# PromQL: sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))

# Check which service is burning
curl -s "http://prometheus:9090/api/v1/query?query=sum(rate(http_requests_total{status=~'5..'}[5m]))by(job)" | jq

# Check error budget remaining
# Grafana: https://grafana.your-domain.com/d/slo-dashboard

# Quick look at recent pod issues
kubectl get pods -n production --field-selector=status.phase!=Running

# Check for recent deployments
kubectl rollout history deployment --all -n production 2>/dev/null
```

---

## Common Causes & Mitigations

### Recent Deployment Causing Errors
```bash
# Check last deploy time vs alert start time
kubectl get events -n production --sort-by='.lastTimestamp' | tail -20

# Rollback if deployment correlates
kubectl rollout undo deployment/<service> -n production

# Monitor recovery (should see error rate drop within 2–3 minutes)
watch kubectl top pods -n production
```

### Dependency Failure (DB, External API)
```bash
# Check database connectivity
kubectl exec -it <app-pod> -n production -- \
  sh -c "nc -zv <db-host> 5432; echo exit code: $?"

# Check for circuit breaker trips
kubectl logs -l app=<service> -n production --since=10m | grep "circuit\|timeout\|unavailable"

# If external API: check status page
# Enable circuit breaker / fallback if not already
```

### Sudden Traffic Spike
```bash
# Check request rates
# PromQL: sum(rate(http_requests_total[5m])) by (job)

# Check HPA scaling
kubectl get hpa -n production
kubectl describe hpa <service> -n production

# Manually scale if HPA hasn't triggered yet
kubectl scale deployment/<service> --replicas=5 -n production
```

### Infrastructure Issue (Node, Network)
```bash
# Check node health
kubectl get nodes
kubectl describe node <problematic-node>

# Check for network policy issues
kubectl get networkpolicies -n production

# Check ingress controller
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=50 | grep error
```

---

## Error Budget Status Dashboard

Track current SLO status:

```promql
# Error rate for the month
1 - (
  sum(rate(http_requests_total{status!~"5.."}[30d]))
  /
  sum(rate(http_requests_total[30d]))
)

# Budget remaining (for 99.9% SLO)
(0.001 - <above_query>) / 0.001 * 100
```

---

## Escalation

| Budget Remaining | Action |
|---|---|
| > 50% | Monitor only |
| 20–50% | Developer investigation |
| 10–20% | On-call engineer, consider freeze |
| < 10% | Incident Commander, feature freeze |
| 0% | Major incident, escalate to VP |

When budget hits 0%: enforce deployment freeze until next measurement window.
