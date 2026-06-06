# Disaster Recovery Failover Runbook

## Overview

**RTO Target:** 15 minutes  
**RPO Target:** 5 minutes  
**Trigger Conditions:** Primary region failure, data center outage, catastrophic cluster failure

---

## Pre-Conditions Checklist

Before initiating DR failover, verify:

- [ ] Primary region is confirmed unavailable (not a transient issue)
- [ ] Cloud provider status page confirms outage
- [ ] At least 2 senior engineers present
- [ ] Incident declared (SEV-1)
- [ ] Stakeholders notified
- [ ] DR runbook reviewed in last 30 days

**Decision authority: VP Engineering or above required to declare DR failover**

---

## Phase 1 — Validate DR Region Readiness (0–5 min)

```bash
# Azure: Check DR AKS cluster
az aks show \
  --resource-group ${DR_RESOURCE_GROUP} \
  --name ${DR_AKS_CLUSTER} \
  --query 'powerState.code' -o tsv

# AWS: Check DR EKS cluster
aws eks describe-cluster \
  --name ${DR_EKS_CLUSTER} \
  --region ${DR_REGION} \
  --query 'cluster.status'

# Check DR database replica lag
# (varies by DB technology)
# PostgreSQL: SELECT pg_last_wal_receive_lsn() - pg_last_wal_replay_lsn();

# Verify critical services in DR
kubectl --context=${DR_CONTEXT} get pods -n production
```

---

## Phase 2 — Database Promotion (5–10 min)

```bash
# Azure: Promote read replica to primary
az postgres flexible-server replica promote \
  --resource-group ${DR_RESOURCE_GROUP} \
  --name ${DR_DB_SERVER}

# AWS: Promote RDS replica
aws rds promote-read-replica \
  --db-instance-identifier ${DR_RDS_INSTANCE}

# Wait for promotion to complete
aws rds wait db-instance-available \
  --db-instance-identifier ${DR_RDS_INSTANCE}

# Update connection strings in Key Vault / Secrets Manager
az keyvault secret set \
  --vault-name ${DR_KEY_VAULT} \
  --name "database-url" \
  --value "${DR_DATABASE_URL}"
```

---

## Phase 3 — DNS Failover (10–12 min)

```bash
# Azure Traffic Manager: Switch to DR endpoint
az network traffic-manager endpoint update \
  --resource-group ${GLOBAL_RG} \
  --profile-name ${TM_PROFILE} \
  --name primary-endpoint \
  --type azureEndpoints \
  --endpoint-status Disabled

az network traffic-manager endpoint update \
  --resource-group ${GLOBAL_RG} \
  --profile-name ${TM_PROFILE} \
  --name dr-endpoint \
  --type azureEndpoints \
  --endpoint-status Enabled

# AWS Route53: Update routing policy
aws route53 change-resource-record-sets \
  --hosted-zone-id ${HOSTED_ZONE_ID} \
  --change-batch file://dr-dns-change.json

# Verify DNS propagation (allow up to 60s for TTL)
nslookup your-domain.com 8.8.8.8
```

---

## Phase 4 — Application Deployment Verification (12–15 min)

```bash
# Verify all deployments running in DR
kubectl --context=${DR_CONTEXT} rollout status \
  deployment --all -n production --timeout=5m

# Run smoke tests against DR
TARGET_ENV=dr ./scripts/smoke-test.sh

# Check error rates in DR
# Grafana: point to DR Prometheus/Thanos endpoint
```

---

## Phase 5 — Communicate Resolution

1. Update StatusPage: "Service restored via DR region"
2. Notify stakeholders: "Failover complete, RTO achieved at HH:MM"
3. Begin post-mortem scheduling

---

## Failback Procedure (after primary region recovery)

1. Restore primary region infrastructure (Terraform apply)
2. Sync data from DR back to primary (database replication)
3. Validate primary region health
4. Schedule maintenance window for failback (off-peak)
5. Reverse DNS failover (primary → enabled, DR → disabled)
6. Monitor for 30 minutes
7. Declare incident resolved

---

## DR Test Schedule

| Test Type | Frequency | Last Tested | Next Scheduled |
|---|---|---|---|
| DNS failover drill | Quarterly | 2026-03-01 | 2026-09-01 |
| Full DR exercise | Semi-annually | 2026-01-15 | 2026-07-15 |
| Data restoration test | Monthly | 2026-05-31 | 2026-06-30 |
| RTO/RPO validation | Annually | 2025-12-01 | 2026-12-01 |
