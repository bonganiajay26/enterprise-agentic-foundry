# Runbook: Kubernetes Cluster Upgrade

**Frequency:** Quarterly (AKS/EKS/GKE patch upgrades monthly)  
**Risk:** HIGH — affects all workloads  
**Prerequisites:** Maintenance window approved, backup taken, runbook reviewed

---

## Pre-Upgrade Checklist

- [ ] Maintenance window approved (minimum 4h window for minor version)
- [ ] Stakeholders notified (≥ 1 week notice for minor, ≥ 1 day for patch)
- [ ] Cluster backup taken (etcd/Velero)
- [ ] Target Kubernetes version validated in staging first
- [ ] All add-ons compatibility verified (cert-manager, kyverno, ArgoCD)
- [ ] PodDisruptionBudgets verified for all critical services
- [ ] Capacity confirmed (upgrading nodes needs extra capacity)

---

## Phase 1 — Pre-Upgrade (Day Before)

```bash
# 1. Record current cluster state
kubectl version
kubectl get nodes -o wide
kubectl get all --all-namespaces | grep -v Running | grep -v Completed

# 2. Check for deprecated APIs
kubectl get --raw /apis | python3 -c "import sys, json; [print(g['preferredVersion']['groupVersion']) for g in json.load(sys.stdin)['groups']]"
# Also use: kubent (kube no trouble) to detect deprecated API usage

# 3. Take Velero backup
velero backup create "pre-upgrade-$(date +%Y%m%d)" \
  --include-cluster-resources \
  --wait

# 4. Verify backup
velero backup describe "pre-upgrade-$(date +%Y%m%d)"

# 5. Cordon and validate PDBs
kubectl get pdb --all-namespaces
```

---

## Phase 2 — Control Plane Upgrade

### Azure (AKS)
```bash
# Check available versions
az aks get-upgrades --resource-group ${RG} --name ${CLUSTER_NAME} --output table

# Upgrade control plane ONLY first
az aks upgrade \
  --resource-group ${RG} \
  --name ${CLUSTER_NAME} \
  --kubernetes-version 1.29 \
  --control-plane-only

# Monitor upgrade
az aks show --resource-group ${RG} --name ${CLUSTER_NAME} \
  --query 'provisioningState' -o tsv

# Verify control plane
kubectl version
kubectl get nodes  # Nodes still on old version — OK at this stage
```

### AWS (EKS)
```bash
# Upgrade cluster control plane
aws eks update-cluster-version \
  --name ${CLUSTER_NAME} \
  --kubernetes-version 1.29

# Monitor
aws eks describe-update \
  --name ${CLUSTER_NAME} \
  --update-id <update-id> \
  --query 'update.status'

# Update kubectl config
aws eks update-kubeconfig --name ${CLUSTER_NAME}
```

### GCP (GKE)
```bash
gcloud container clusters upgrade ${CLUSTER_NAME} \
  --master \
  --cluster-version 1.29 \
  --region ${REGION}
```

---

## Phase 3 — Node Pool Upgrade (Rolling)

```bash
# AKS: Upgrade node pools one at a time
# System node pool first, then workload pools

az aks nodepool upgrade \
  --resource-group ${RG} \
  --cluster-name ${CLUSTER_NAME} \
  --name system \
  --kubernetes-version 1.29 \
  --no-wait

# Monitor node pool upgrade
watch kubectl get nodes

# When system pool is done, upgrade workloads pool
az aks nodepool upgrade \
  --resource-group ${RG} \
  --cluster-name ${CLUSTER_NAME} \
  --name workloads \
  --kubernetes-version 1.29

# AWS EKS: Update managed node groups
aws eks update-nodegroup-version \
  --cluster-name ${CLUSTER_NAME} \
  --nodegroup-name system \
  --kubernetes-version 1.29

aws eks update-nodegroup-version \
  --cluster-name ${CLUSTER_NAME} \
  --nodegroup-name workloads \
  --kubernetes-version 1.29
```

---

## Phase 4 — Post-Upgrade Validation

```bash
# 1. Verify all nodes on new version
kubectl get nodes -o wide

# 2. Check all system pods running
kubectl get pods -n kube-system
kubectl get pods -n cert-manager
kubectl get pods -n monitoring
kubectl get pods -n kyverno

# 3. Run cluster health check
./scripts/cluster-health-check.sh production

# 4. Run smoke tests
./tests/smoke/smoke-test.sh production

# 5. Check no pods restarted unexpectedly
kubectl get pods --all-namespaces --sort-by='.status.containerStatuses[0].restartCount' | tail -20

# 6. Verify Kyverno policies still active
kubectl get clusterpolicy

# 7. Update Terraform/OpenTofu state
# Update kubernetes_version in variables.tf and run:
terraform apply -target=azurerm_kubernetes_cluster.platform
```

---

## Rollback

AKS/EKS/GKE do NOT support in-place downgrades. Rollback options:

1. **Restore from backup** — Use Velero restore to a pre-upgrade snapshot
2. **Blue-green clusters** — Deploy a new cluster running the old version, redirect traffic
3. **Node pool rollback** — Replace new node pool with nodes running old kubelet version

For critical failures, open a P1 incident immediately.

---

## Post-Upgrade Communication

```
Subject: Kubernetes Cluster Upgrade Complete — v{NEW_VERSION}

Cluster: {CLUSTER_NAME}
Upgrade: v{OLD} → v{NEW}
Duration: X hours Y minutes
Status: ✅ Successful

All services healthy. No incidents reported.

Next scheduled upgrade: {DATE}
```
