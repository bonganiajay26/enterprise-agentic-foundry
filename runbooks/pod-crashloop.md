# Runbook: Pod CrashLoopBackOff

**Alert:** `PodCrashLooping` — container restarted > 3 times in 15 minutes  
**Severity:** P2 (P1 if in production, critical service)

---

## Diagnosis (0–5 min)

```bash
# 1. Identify the failing pod
kubectl get pods -n <namespace> | grep -v Running

# 2. Describe the pod — check Events section
kubectl describe pod <pod-name> -n <namespace>

# 3. Get current logs
kubectl logs <pod-name> -n <namespace> --tail=100

# 4. Get previous container logs (after crash)
kubectl logs <pod-name> -n <namespace> --previous --tail=200

# 5. Check exit code
kubectl get pod <pod-name> -n <namespace> \
  -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}'
```

### Exit Code Reference

| Exit Code | Meaning | Common Cause |
|---|---|---|
| 0 | Success (shouldn't crash) | Misconfigured restart policy |
| 1 | App error | Unhandled exception, bad config |
| 137 | SIGKILL / OOMKilled | Memory limit too low |
| 139 | Segfault | C/C++/Rust memory bug |
| 143 | SIGTERM | Graceful shutdown too slow |

---

## Common Causes & Fixes

### OOMKilled (Exit 137)
```bash
# Confirm OOM
kubectl describe pod <pod> | grep -A5 "OOMKilled"

# Fix: Increase memory limit in Helm values
helm upgrade myapp ./helm/base-service \
  --set resources.limits.memory=512Mi \
  --set resources.requests.memory=256Mi \
  -n production --reuse-values
```

### Missing ConfigMap or Secret
```bash
# Check for missing env vars or mounts
kubectl describe pod <pod> | grep "Error\|Warning\|not found"

# Verify secret exists
kubectl get secret <secret-name> -n <namespace>

# Verify ConfigMap exists
kubectl get configmap <configmap-name> -n <namespace>
```

### Bad Image or ImagePullError
```bash
kubectl describe pod <pod> | grep "image\|Image\|Failed"

# Fix: Check image exists and tag is correct
docker manifest inspect <image>:<tag>

# Rollback to last known good image
kubectl rollout undo deployment/<name> -n <namespace>
```

### Liveness Probe Failing
```bash
# Check liveness probe config
kubectl get deployment <name> -n <namespace> \
  -o jsonpath='{.spec.template.spec.containers[0].livenessProbe}'

# Test probe endpoint manually
kubectl exec -it <pod> -n <namespace> -- \
  wget -qO- http://localhost:8080/health/live
```

### Application Startup Error
```bash
# Get full startup logs
kubectl logs <pod> -n <namespace> --previous 2>&1 | head -200

# Check for config file issues, missing env vars
kubectl exec -it <pod> -n <namespace> -- env | sort
```

---

## Mitigation

```bash
# Option 1: Rollback deployment
kubectl rollout undo deployment/<name> -n <namespace>
kubectl rollout status deployment/<name> -n <namespace>

# Option 2: Scale to 0 and back (force recreate)
kubectl scale deployment/<name> --replicas=0 -n <namespace>
sleep 5
kubectl scale deployment/<name> --replicas=2 -n <namespace>

# Option 3: Delete stuck pod (will be recreated by ReplicaSet)
kubectl delete pod <pod-name> -n <namespace>
```

---

## Post-Fix Verification

```bash
# Confirm pods are running
kubectl get pods -n <namespace> -w

# Verify no more restarts for 5 minutes
kubectl get pods -n <namespace> --watch | grep -v "0/1\|1/1"

# Check error rate returned to baseline
# Grafana: https://grafana.your-domain.com/d/service-health
```
