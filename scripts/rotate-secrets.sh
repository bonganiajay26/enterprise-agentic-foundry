#!/usr/bin/env bash
# Secret Rotation Script
# Rotates secrets in Azure Key Vault / AWS Secrets Manager / GCP Secret Manager
# and forces External Secrets Operator to re-sync

set -euo pipefail

CLOUD="${1:-azure}"
SECRET_NAME="${2:-}"
NAMESPACE="${3:-production}"

usage() {
    echo "Usage: $0 <cloud> <secret-name> [namespace]"
    echo "  cloud:       azure | aws | gcp"
    echo "  secret-name: Name of the secret to rotate"
    echo "  namespace:   Kubernetes namespace (default: production)"
    echo ""
    echo "Examples:"
    echo "  $0 azure database-password production"
    echo "  $0 aws myapp/database-url default"
    exit 1
}

[ -z "${SECRET_NAME}" ] && usage

echo "═══════════════════════════════════════"
echo "  Secret Rotation: ${SECRET_NAME}"
echo "  Cloud: ${CLOUD} | Namespace: ${NAMESPACE}"
echo "═══════════════════════════════════════"

rotate_azure() {
    local VAULT_NAME="${AZURE_KEY_VAULT_NAME:?AZURE_KEY_VAULT_NAME required}"

    echo "→ Generating new secret value..."
    NEW_VALUE=$(openssl rand -base64 32)

    echo "→ Rotating ${SECRET_NAME} in Azure Key Vault ${VAULT_NAME}..."
    az keyvault secret set \
        --vault-name "${VAULT_NAME}" \
        --name "${SECRET_NAME}" \
        --value "${NEW_VALUE}" \
        --output none

    echo "✓ Secret rotated in Key Vault"
}

rotate_aws() {
    echo "→ Rotating ${SECRET_NAME} in AWS Secrets Manager..."
    aws secretsmanager rotate-secret \
        --secret-id "${SECRET_NAME}" \
        --force-delete-without-recovery

    # Wait for rotation
    aws secretsmanager describe-secret --secret-id "${SECRET_NAME}" \
        --query 'RotationEnabled' --output text

    echo "✓ Secret rotated in AWS Secrets Manager"
}

rotate_gcp() {
    local PROJECT="${GCP_PROJECT_ID:?GCP_PROJECT_ID required}"
    local TIMESTAMP=$(date +%Y%m%d%H%M%S)

    echo "→ Creating new version of ${SECRET_NAME} in GCP Secret Manager..."
    NEW_VALUE=$(openssl rand -base64 32)
    echo -n "${NEW_VALUE}" | \
        gcloud secrets versions add "${SECRET_NAME}" \
            --project="${PROJECT}" \
            --data-file=-

    echo "✓ New secret version created in GCP Secret Manager"
}

force_k8s_sync() {
    echo "→ Forcing External Secrets Operator sync..."

    # Find ExternalSecret resources for this secret
    kubectl annotate externalsecrets \
        -n "${NAMESPACE}" \
        -l "app.kubernetes.io/instance=${SECRET_NAME}" \
        force-sync="$(date +%s)" \
        --overwrite 2>/dev/null || true

    # Force sync all ExternalSecrets in namespace
    kubectl get externalsecrets -n "${NAMESPACE}" -o name | while read -r es; do
        kubectl annotate "${es}" -n "${NAMESPACE}" \
            "force-sync=$(date +%s)" \
            --overwrite
        echo "  Synced: ${es}"
    done

    echo "→ Waiting for secrets to sync (30s)..."
    sleep 30

    # Restart pods to pick up new secret values
    echo "→ Rolling restart of affected deployments..."
    kubectl rollout restart deployment -n "${NAMESPACE}"
    kubectl rollout status deployment -n "${NAMESPACE}" --timeout=5m

    echo "✓ All deployments restarted with new secrets"
}

# ─── Main ─────────────────────────────────────────────────────────────
case "${CLOUD}" in
    azure) rotate_azure ;;
    aws)   rotate_aws ;;
    gcp)   rotate_gcp ;;
    *)     echo "Unknown cloud: ${CLOUD}"; usage ;;
esac

force_k8s_sync

echo ""
echo "✓ Secret rotation complete: ${SECRET_NAME}"
echo "  Remember to:"
echo "  1. Update any non-Kubernetes consumers"
echo "  2. Verify application health after rotation"
echo "  3. Document rotation in your audit log"
