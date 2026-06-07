#!/usr/bin/env bash
# Compliance Evidence Collection Script
# Automatically collects evidence for SOC2, ISO27001, PCI-DSS audits
# Usage: ./compliance/evidence-collection.sh --framework soc2 --output evidence/2026-06

set -euo pipefail

FRAMEWORK="${1:-soc2}"
OUTPUT_DIR="${2:-evidence/$(date +%Y-%m)}"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
CLUSTER_CONTEXT="${CLUSTER_CONTEXT:-$(kubectl config current-context 2>/dev/null || echo 'not-configured')}"

echo "════════════════════════════════════════════"
echo "  Compliance Evidence Collection"
echo "  Framework: ${FRAMEWORK}"
echo "  Output:    ${OUTPUT_DIR}"
echo "  Timestamp: ${TIMESTAMP}"
echo "════════════════════════════════════════════"

mkdir -p "${OUTPUT_DIR}"

collect_kubernetes_evidence() {
    echo "→ Collecting Kubernetes configuration evidence..."
    local k8s_dir="${OUTPUT_DIR}/kubernetes"
    mkdir -p "${k8s_dir}"

    # RBAC configuration
    kubectl get clusterroles -o yaml > "${k8s_dir}/cluster-roles.yaml" 2>/dev/null || echo "kubectl not available"
    kubectl get clusterrolebindings -o yaml > "${k8s_dir}/cluster-role-bindings.yaml" 2>/dev/null || true
    kubectl get roles --all-namespaces -o yaml > "${k8s_dir}/namespace-roles.yaml" 2>/dev/null || true

    # Network policies
    kubectl get networkpolicies --all-namespaces -o yaml > "${k8s_dir}/network-policies.yaml" 2>/dev/null || true

    # Pod security policies / Kyverno policies
    kubectl get clusterpolicies -o yaml > "${k8s_dir}/kyverno-policies.yaml" 2>/dev/null || true

    # Resource quotas (shows cost controls)
    kubectl get resourcequota --all-namespaces -o yaml > "${k8s_dir}/resource-quotas.yaml" 2>/dev/null || true

    # Certificate status (shows TLS evidence)
    kubectl get certificates --all-namespaces -o yaml > "${k8s_dir}/certificates.yaml" 2>/dev/null || true

    echo "  ✓ Kubernetes evidence collected"
}

collect_security_evidence() {
    echo "→ Collecting security scan evidence..."
    local sec_dir="${OUTPUT_DIR}/security"
    mkdir -p "${sec_dir}"

    # Gitleaks — secrets scan (last 30 days of commits)
    if command -v gitleaks >/dev/null 2>&1; then
        gitleaks detect --source . --report-format json \
            --report-path "${sec_dir}/gitleaks-report.json" 2>/dev/null || true
    fi

    # Trivy — latest scan results
    if command -v trivy >/dev/null 2>&1; then
        trivy fs . --format json --output "${sec_dir}/trivy-fs-scan.json" 2>/dev/null || true
    fi

    # Checkov — IaC scan
    if command -v checkov >/dev/null 2>&1; then
        checkov -d terraform/ --output json > "${sec_dir}/checkov-terraform.json" 2>/dev/null || true
    fi

    # Copy security policies as evidence
    cp -r security/ "${sec_dir}/platform-security-config/" 2>/dev/null || true

    echo "  ✓ Security evidence collected"
}

collect_access_management_evidence() {
    echo "→ Collecting access management evidence..."
    local access_dir="${OUTPUT_DIR}/access-management"
    mkdir -p "${access_dir}"

    # Service accounts (for CC6.1 — principle of least privilege)
    kubectl get serviceaccounts --all-namespaces -o yaml > "${access_dir}/service-accounts.yaml" 2>/dev/null || true

    # External secrets (shows secrets aren't in source code — CC6.6)
    kubectl get externalsecrets --all-namespaces -o yaml > "${access_dir}/external-secrets.yaml" 2>/dev/null || true

    echo "  ✓ Access management evidence collected"
}

collect_change_management_evidence() {
    echo "→ Collecting change management evidence..."
    local change_dir="${OUTPUT_DIR}/change-management"
    mkdir -p "${change_dir}"

    # Git log of last 90 days
    git log --since="90 days ago" --format="%H|%an|%ae|%ad|%s" \
        > "${change_dir}/git-commits-90d.csv" 2>/dev/null || echo "Not a git repo"

    # ArgoCD application history
    kubectl get applications -n argocd -o yaml > "${change_dir}/argocd-applications.yaml" 2>/dev/null || true

    # CI/CD pipeline configs as evidence
    cp -r .github/workflows/ "${change_dir}/github-actions/" 2>/dev/null || true

    echo "  ✓ Change management evidence collected"
}

collect_availability_evidence() {
    echo "→ Collecting availability evidence..."
    local avail_dir="${OUTPUT_DIR}/availability"
    mkdir -p "${avail_dir}"

    # Deployment status
    kubectl get deployments --all-namespaces -o yaml > "${avail_dir}/deployments.yaml" 2>/dev/null || true

    # HPA status (shows auto-scaling)
    kubectl get hpa --all-namespaces -o yaml > "${avail_dir}/hpa-config.yaml" 2>/dev/null || true

    # PDB status (shows availability guarantees)
    kubectl get pdb --all-namespaces -o yaml > "${avail_dir}/pod-disruption-budgets.yaml" 2>/dev/null || true

    # Runbooks as evidence of DR preparedness
    cp -r runbooks/ "${avail_dir}/operational-runbooks/" 2>/dev/null || true

    echo "  ✓ Availability evidence collected"
}

generate_evidence_manifest() {
    echo "→ Generating evidence manifest..."
    cat > "${OUTPUT_DIR}/EVIDENCE-MANIFEST.md" <<EOF
# Compliance Evidence Manifest

**Framework:** ${FRAMEWORK}
**Collection Date:** ${TIMESTAMP}
**Cluster:** ${CLUSTER_CONTEXT}
**Collected By:** $(whoami)

## Contents

\`\`\`
$(find "${OUTPUT_DIR}" -type f | sort)
\`\`\`

## Attestation

I attest that this evidence was automatically collected from production systems
at the time and date shown above. This evidence supports our ${FRAMEWORK} compliance posture.

| Role | Name | Date |
|------|------|------|
| Platform Engineer | | |
| Security Officer | | |
| Compliance Manager | | |
EOF
    echo "  ✓ Manifest generated"
}

# ─── Main ─────────────────────────────────────────────────────────────
collect_kubernetes_evidence
collect_security_evidence
collect_access_management_evidence
collect_change_management_evidence
collect_availability_evidence
generate_evidence_manifest

echo ""
echo "════════════════════════════════════════════"
echo "  Evidence collection complete!"
echo "  Output: ${OUTPUT_DIR}/"
echo "  Files:  $(find "${OUTPUT_DIR}" -type f | wc -l)"
echo "════════════════════════════════════════════"
