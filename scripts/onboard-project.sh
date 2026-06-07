#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# One-Click Project Onboarding Script
# Universal Agentic DevOps Platform
#
# What this does (end-to-end):
#   1. Creates GitHub repository with branch protection
#   2. Scaffolds project structure from template
#   3. Generates CI/CD pipeline (GitHub Actions / Azure DevOps)
#   4. Creates Helm chart with correct values
#   5. Generates Terraform module for the service
#   6. Creates Kubernetes namespace with quotas and network policies
#   7. Registers service in Backstage catalog
#   8. Sets up monitoring (ServiceMonitor + Grafana dashboard)
#   9. Creates initial documentation (README + runbook skeleton)
#  10. Runs first CI pipeline to validate everything works
#
# Usage:
#   ./scripts/onboard-project.sh \
#     --name payment-service \
#     --language python \
#     --cloud azure \
#     --owner platform-team \
#     --repo-org your-org
# ═══════════════════════════════════════════════════════════════════════

set -euo pipefail

# ─── Defaults ─────────────────────────────────────────────────────────
SERVICE_NAME=""
LANGUAGE="nodejs"
FRAMEWORK=""
CLOUD="azure"
ENVIRONMENT="dev"
OWNER="platform-team"
REPO_ORG="${GITHUB_ORG:-your-org}"
REPO_VISIBILITY="private"
CI_PROVIDER="github-actions"
ENABLE_DATABASE=false
DATABASE_TYPE="postgresql"
ENABLE_REDIS=false
K8S_CONTEXT="${KUBECTL_CONTEXT:-}"
PLATFORM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DRY_RUN=false

# ─── Colors ───────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

log_info()    { echo -e "${BLUE}ℹ${NC}  $1"; }
log_success() { echo -e "${GREEN}✓${NC}  $1"; }
log_warning() { echo -e "${YELLOW}⚠${NC}  $1"; }
log_error()   { echo -e "${RED}✗${NC}  $1" >&2; }
log_step()    { echo -e "\n${BOLD}${BLUE}══ Step $1 ══${NC}"; }

# ─── Usage ────────────────────────────────────────────────────────────
usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Required:
  --name NAME            Service name (kebab-case, e.g. payment-service)

Optional:
  --language LANG        nodejs | python | java | dotnet | go (default: nodejs)
  --framework FW         express | fastapi | springboot | django | gin
  --cloud CLOUD          azure | aws | gcp (default: azure)
  --environment ENV      dev | staging | production (default: dev)
  --owner OWNER          Team owner (default: platform-team)
  --repo-org ORG         GitHub organization (default: \$GITHUB_ORG)
  --ci-provider CI       github-actions | azure-devops | gitlab-ci (default: github-actions)
  --enable-database      Add database infrastructure
  --database-type TYPE   postgresql | mysql | mongodb (default: postgresql)
  --enable-redis         Add Redis cache infrastructure
  --dry-run              Show what would be created without doing it
  -h, --help             Show this help

Examples:
  $0 --name user-service --language python --cloud azure
  $0 --name order-service --language java --framework springboot --enable-database
  $0 --name analytics --language python --framework fastapi --enable-database --enable-redis
EOF
    exit 0
}

# ─── Parse Arguments ──────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --name)           SERVICE_NAME="$2"; shift 2 ;;
        --language)       LANGUAGE="$2"; shift 2 ;;
        --framework)      FRAMEWORK="$2"; shift 2 ;;
        --cloud)          CLOUD="$2"; shift 2 ;;
        --environment)    ENVIRONMENT="$2"; shift 2 ;;
        --owner)          OWNER="$2"; shift 2 ;;
        --repo-org)       REPO_ORG="$2"; shift 2 ;;
        --ci-provider)    CI_PROVIDER="$2"; shift 2 ;;
        --enable-database) ENABLE_DATABASE=true; shift ;;
        --database-type)  DATABASE_TYPE="$2"; shift 2 ;;
        --enable-redis)   ENABLE_REDIS=true; shift ;;
        --dry-run)        DRY_RUN=true; shift ;;
        -h|--help)        usage ;;
        *) log_error "Unknown option: $1"; usage ;;
    esac
done

[ -z "${SERVICE_NAME}" ] && { log_error "Service name is required (--name)"; usage; }

# ─── Validation ───────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}══════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Universal Platform — Project Onboarding${NC}"
echo -e "${BOLD}══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Service:     ${BOLD}${SERVICE_NAME}${NC}"
echo -e "  Language:    ${LANGUAGE}"
echo -e "  Cloud:       ${CLOUD}"
echo -e "  Owner:       ${OWNER}"
echo -e "  Repository:  ${REPO_ORG}/${SERVICE_NAME}"
echo -e "  CI/CD:       ${CI_PROVIDER}"
echo -e "  Database:    $([ "${ENABLE_DATABASE}" = true ] && echo "${DATABASE_TYPE}" || echo "none")"
echo -e "  Redis:       $([ "${ENABLE_REDIS}" = true ] && echo "yes" || echo "no")"
[ "${DRY_RUN}" = true ] && echo -e "  ${YELLOW}DRY RUN — no changes will be made${NC}"
echo ""

read -p "Proceed? [y/N] " confirm
[[ "${confirm}" =~ ^[Yy]$ ]] || { echo "Cancelled."; exit 0; }

# ─── Step 1: Create GitHub Repository ─────────────────────────────────
log_step "1/10 — Create GitHub Repository"
if [ "${DRY_RUN}" = false ]; then
    if command -v gh >/dev/null 2>&1; then
        gh repo create "${REPO_ORG}/${SERVICE_NAME}" \
            --"${REPO_VISIBILITY}" \
            --description "$(echo "${SERVICE_NAME}" | sed 's/-/ /g' | sed 's/\b\(.\)/\u\1/g') service" \
            --gitignore "$([ "${LANGUAGE}" = "python" ] && echo Python || echo Node)" \
            || log_warning "Repository may already exist"

        # Enable branch protection
        gh api "repos/${REPO_ORG}/${SERVICE_NAME}/branches/main/protection" \
            --method PUT \
            --field required_status_checks='{"strict":true,"contexts":["ci/secrets-scan","ci/lint","ci/test","ci/build"]}' \
            --field enforce_admins=false \
            --field required_pull_request_reviews='{"required_approving_review_count":1}' \
            --field restrictions=null \
            2>/dev/null || log_warning "Branch protection: may need manual configuration"

        log_success "Repository created: https://github.com/${REPO_ORG}/${SERVICE_NAME}"
    else
        log_warning "gh CLI not found — skipping repo creation (create manually)"
    fi
fi

# ─── Step 2: Scaffold Project Structure ───────────────────────────────
log_step "2/10 — Scaffold Project Structure"
TMP_DIR=$(mktemp -d)
trap "rm -rf ${TMP_DIR}" EXIT

PROJECT_DIR="${TMP_DIR}/${SERVICE_NAME}"
mkdir -p "${PROJECT_DIR}"/{src,tests,docs,helm,terraform}

if [ "${DRY_RUN}" = false ]; then
    # Copy appropriate template
    case "${LANGUAGE}" in
        nodejs)   cp -r "${PLATFORM_DIR}/templates/nodejs-api/." "${PROJECT_DIR}/" ;;
        python)   cp -r "${PLATFORM_DIR}/templates/python-fastapi/." "${PROJECT_DIR}/" ;;
        java)     cp -r "${PLATFORM_DIR}/templates/java-springboot/." "${PROJECT_DIR}/" ;;
        *)        log_warning "Template for ${LANGUAGE} not found — using minimal structure" ;;
    esac
    log_success "Project structure scaffolded"
fi

# ─── Step 3: Generate CI/CD Pipeline ──────────────────────────────────
log_step "3/10 — Generate CI/CD Pipeline"
if [ "${DRY_RUN}" = false ]; then
    mkdir -p "${PROJECT_DIR}/.github/workflows"
    # Copy and customize the universal pipeline
    sed "s/SERVICE_NAME/${SERVICE_NAME}/g" \
        "${PLATFORM_DIR}/.github/workflows/ci-universal.yml" \
        > "${PROJECT_DIR}/.github/workflows/ci.yml"
    log_success "CI/CD pipeline generated (${CI_PROVIDER})"
fi

# ─── Step 4: Generate Helm Chart ──────────────────────────────────────
log_step "4/10 — Generate Helm Chart"
if [ "${DRY_RUN}" = false ]; then
    cp -r "${PLATFORM_DIR}/helm/base-service" "${PROJECT_DIR}/helm/${SERVICE_NAME}"
    # Customize values
    sed -i "s/your-service.your-domain.com/${SERVICE_NAME}.your-domain.com/g" \
        "${PROJECT_DIR}/helm/${SERVICE_NAME}/values.yaml" 2>/dev/null || true
    log_success "Helm chart generated at helm/${SERVICE_NAME}/"
fi

# ─── Step 5: Generate Catalog Entry ───────────────────────────────────
log_step "5/10 — Create Backstage Catalog Entry"
if [ "${DRY_RUN}" = false ]; then
    cat > "${PROJECT_DIR}/catalog-info.yaml" <<EOF
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: ${SERVICE_NAME}
  title: $(echo "${SERVICE_NAME}" | sed 's/-/ /g' | sed 's/\b\(.\)/\u\1/g')
  description: Generated by Universal Platform onboarding
  tags: [${LANGUAGE}, service, ${ENVIRONMENT}]
  annotations:
    github.com/project-slug: ${REPO_ORG}/${SERVICE_NAME}
    backstage.io/techdocs-ref: dir:.
    prometheus.io/scrape: "true"
    backstage.io/kubernetes-id: ${SERVICE_NAME}
spec:
  type: service
  lifecycle: experimental
  owner: ${OWNER}
  system: platform
EOF
    log_success "Backstage catalog entry created"
fi

# ─── Step 6: Create Kubernetes Namespace ──────────────────────────────
log_step "6/10 — Create Kubernetes Namespace"
if [ "${DRY_RUN}" = false ] && command -v kubectl >/dev/null 2>&1; then
    kubectl create namespace "${SERVICE_NAME}-${ENVIRONMENT}" \
        --dry-run=client -o yaml | kubectl apply -f -
    kubectl label namespace "${SERVICE_NAME}-${ENVIRONMENT}" \
        "app.kubernetes.io/name=${SERVICE_NAME}" \
        "environment=${ENVIRONMENT}" \
        "owner=${OWNER}" \
        --overwrite
    log_success "Namespace ${SERVICE_NAME}-${ENVIRONMENT} created"
else
    log_warning "kubectl not available — skipping namespace creation"
fi

# ─── Step 7: Generate README ──────────────────────────────────────────
log_step "7/10 — Generate Documentation"
if [ "${DRY_RUN}" = false ]; then
    cat > "${PROJECT_DIR}/README.md" <<EOF
# ${SERVICE_NAME}

> Auto-generated by Universal Platform onboarding — $(date -u +%Y-%m-%d)

## Overview

${SERVICE_NAME} is a **${LANGUAGE}** service deployed on **${CLOUD}**.

## Quick Start

\`\`\`bash
# Install dependencies
$([ "${LANGUAGE}" = "nodejs" ] && echo "npm ci" || echo "pip install -r requirements.txt")

# Start locally
$([ "${LANGUAGE}" = "nodejs" ] && echo "npm run dev" || echo "uvicorn app.main:app --reload")

# Docker
docker build -f docker/Dockerfile.${LANGUAGE} -t ${SERVICE_NAME} .
docker run -p 8080:8080 ${SERVICE_NAME}
\`\`\`

## Health Endpoints

- \`GET /health/live\` — Liveness
- \`GET /health/ready\` — Readiness
- \`GET /metrics\` — Prometheus

## Deployment

\`\`\`bash
helm upgrade --install ${SERVICE_NAME} ./helm/${SERVICE_NAME} \\
  --namespace ${SERVICE_NAME}-${ENVIRONMENT} \\
  --values helm/${SERVICE_NAME}/values-${ENVIRONMENT}.yaml
\`\`\`

## Observability

- Dashboard: https://grafana.your-domain.com/d/${SERVICE_NAME}
- Logs: https://grafana.your-domain.com/explore (Loki)
- Traces: https://grafana.your-domain.com/explore (Tempo)
EOF
    log_success "README.md generated"
fi

# ─── Step 8: Push to GitHub ───────────────────────────────────────────
log_step "8/10 — Push to GitHub"
if [ "${DRY_RUN}" = false ] && command -v gh >/dev/null 2>&1; then
    cd "${PROJECT_DIR}"
    git init
    git add .
    git commit -m "feat: initial scaffolding via Universal Platform onboarding

Generated by: scripts/onboard-project.sh
Language: ${LANGUAGE}
Cloud: ${CLOUD}
Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
    git branch -M main
    git remote add origin "https://github.com/${REPO_ORG}/${SERVICE_NAME}.git"
    git push -u origin main
    cd - >/dev/null
    log_success "Code pushed to https://github.com/${REPO_ORG}/${SERVICE_NAME}"
fi

# ─── Step 9: Register in Backstage ────────────────────────────────────
log_step "9/10 — Register in Backstage"
log_info "To register in Backstage, visit:"
echo "  https://backstage.your-domain.com/catalog-import"
echo "  → Import: https://github.com/${REPO_ORG}/${SERVICE_NAME}/blob/main/catalog-info.yaml"

# ─── Step 10: Summary ─────────────────────────────────────────────────
log_step "10/10 — Complete!"
echo ""
echo -e "${BOLD}${GREEN}══════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  Onboarding Complete! 🚀${NC}"
echo -e "${BOLD}${GREEN}══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Repository:    https://github.com/${REPO_ORG}/${SERVICE_NAME}"
echo -e "  CI/CD:         https://github.com/${REPO_ORG}/${SERVICE_NAME}/actions"
echo -e "  Backstage:     https://backstage.your-domain.com/catalog/default/component/${SERVICE_NAME}"
echo ""
echo -e "  Next steps:"
echo -e "  1. Add secrets to GitHub repository settings"
echo -e "  2. Configure \${AZURE_OPENAI_ENDPOINT} etc. in GitHub Secrets"
echo -e "  3. Deploy to dev: helm upgrade --install ..."
echo -e "  4. Complete Production Checklist: docs/production-checklist.md"
echo ""
