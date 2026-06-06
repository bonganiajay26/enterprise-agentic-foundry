#!/usr/bin/env bash
# Bootstrap script for Universal Agentic DevOps Platform
# Usage: ./scripts/bootstrap.sh --cloud azure --env dev --prefix myplatform

set -euo pipefail

# ─── Parse Arguments ──────────────────────────────────────────────────
CLOUD="azure"
ENV="dev"
PREFIX="platform"
SKIP_INFRA=false
SKIP_BACKSTAGE=false
SKIP_AGENTS=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --cloud) CLOUD="$2"; shift 2 ;;
    --env) ENV="$2"; shift 2 ;;
    --prefix) PREFIX="$2"; shift 2 ;;
    --skip-infra) SKIP_INFRA=true; shift ;;
    --skip-backstage) SKIP_BACKSTAGE=true; shift ;;
    --skip-agents) SKIP_AGENTS=true; shift ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

echo "═══════════════════════════════════════════════════════"
echo "  Universal Agentic DevOps Platform Bootstrap"
echo "  Cloud: ${CLOUD} | Environment: ${ENV} | Prefix: ${PREFIX}"
echo "═══════════════════════════════════════════════════════"

# ─── Prerequisites Check ──────────────────────────────────────────────
check_prerequisites() {
  echo "→ Checking prerequisites..."
  local missing=()

  command -v terraform >/dev/null 2>&1 || missing+=("terraform")
  command -v kubectl >/dev/null 2>&1 || missing+=("kubectl")
  command -v helm >/dev/null 2>&1 || missing+=("helm")
  command -v docker >/dev/null 2>&1 || missing+=("docker")
  command -v node >/dev/null 2>&1 || missing+=("node")
  command -v python3 >/dev/null 2>&1 || missing+=("python3")

  case $CLOUD in
    azure) command -v az >/dev/null 2>&1 || missing+=("az (azure-cli)") ;;
    aws)   command -v aws >/dev/null 2>&1 || missing+=("aws (awscli)") ;;
    gcp)   command -v gcloud >/dev/null 2>&1 || missing+=("gcloud") ;;
  esac

  if [ ${#missing[@]} -gt 0 ]; then
    echo "✗ Missing prerequisites: ${missing[*]}"
    echo "  Please install them and re-run."
    exit 1
  fi
  echo "✓ All prerequisites satisfied"
}

# ─── Infrastructure Bootstrap ─────────────────────────────────────────
bootstrap_infrastructure() {
  if [ "$SKIP_INFRA" = true ]; then
    echo "→ Skipping infrastructure bootstrap (--skip-infra)"
    return
  fi

  echo "→ Bootstrapping ${CLOUD} infrastructure..."

  TFDIR="terraform/${CLOUD}"

  if [ ! -d "$TFDIR" ]; then
    echo "✗ Terraform directory not found: $TFDIR"
    exit 1
  fi

  cd "$TFDIR"

  # Generate tfvars from template
  cat > terraform.tfvars <<EOF
prefix      = "${PREFIX}"
environment = "${ENV}"
EOF

  terraform init -upgrade
  terraform validate
  terraform plan -out=tfplan -var-file=terraform.tfvars

  echo ""
  read -p "→ Review the plan above. Apply? [y/N] " confirm
  if [[ "$confirm" =~ ^[Yy]$ ]]; then
    terraform apply tfplan
    echo "✓ Infrastructure deployed"
  else
    echo "→ Apply cancelled. Run 'terraform apply tfplan' manually."
  fi

  cd - >/dev/null
}

# ─── Kubernetes Platform Setup ────────────────────────────────────────
setup_kubernetes() {
  echo "→ Setting up Kubernetes platform..."

  # Configure kubeconfig
  case $CLOUD in
    azure)
      CLUSTER_NAME="${PREFIX}-${ENV}-aks"
      RG="${PREFIX}-${ENV}-rg"
      az aks get-credentials --resource-group "$RG" --name "$CLUSTER_NAME" --overwrite-existing
      ;;
    aws)
      CLUSTER_NAME="${PREFIX}-${ENV}-eks"
      aws eks update-kubeconfig --name "$CLUSTER_NAME" --region us-east-1
      ;;
    gcp)
      CLUSTER_NAME="${PREFIX}-${ENV}-gke"
      gcloud container clusters get-credentials "$CLUSTER_NAME" --region us-central1
      ;;
  esac

  echo "✓ Connected to Kubernetes cluster: ${CLUSTER_NAME}"

  # Install platform components
  echo "→ Installing platform Helm charts..."

  # Cert-Manager
  helm upgrade --install cert-manager jetstack/cert-manager \
    --namespace cert-manager --create-namespace \
    --set installCRDs=true \
    --wait --timeout 5m

  # Kyverno
  helm upgrade --install kyverno kyverno/kyverno \
    --namespace kyverno --create-namespace \
    --wait --timeout 5m

  # Apply security policies
  kubectl apply -f security/policies/

  # Prometheus Stack
  helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
    --namespace monitoring --create-namespace \
    --values monitoring/prometheus-stack-values.yaml \
    --wait --timeout 10m

  # Loki Stack
  helm upgrade --install loki grafana/loki-stack \
    --namespace monitoring \
    --set promtail.enabled=true \
    --wait --timeout 5m

  # OpenTelemetry Operator
  helm upgrade --install opentelemetry-operator open-telemetry/opentelemetry-operator \
    --namespace opentelemetry-operator-system --create-namespace \
    --wait --timeout 5m

  echo "✓ Kubernetes platform components installed"
}

# ─── Backstage Bootstrap ──────────────────────────────────────────────
bootstrap_backstage() {
  if [ "$SKIP_BACKSTAGE" = true ]; then
    echo "→ Skipping Backstage bootstrap (--skip-backstage)"
    return
  fi

  echo "→ Bootstrapping Backstage IDP..."

  if [ ! -d "backstage/app" ]; then
    echo "→ Creating new Backstage app..."
    npx @backstage/create-app@latest --path backstage/app --skip-install
  fi

  cd backstage/app
  yarn install
  cp ../app-config/app-config.yaml app-config.production.yaml

  echo "✓ Backstage ready. Run: cd backstage/app && yarn dev"
  cd - >/dev/null
}

# ─── Agentic AI Setup ─────────────────────────────────────────────────
setup_agents() {
  if [ "$SKIP_AGENTS" = true ]; then
    echo "→ Skipping agent setup (--skip-agents)"
    return
  fi

  echo "→ Setting up Agentic AI platform..."

  cd agentic-ai
  python3 -m venv .venv
  source .venv/bin/activate || source .venv/Scripts/activate 2>/dev/null || true
  pip install -r requirements.txt

  echo "→ Environment variables needed:"
  echo "  export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com"
  echo "  export AZURE_OPENAI_API_KEY=your-key"
  echo "  export AZURE_OPENAI_DEPLOYMENT=gpt-4o"
  echo ""
  echo "→ Test agents: python agents/supervisor.py"

  cd - >/dev/null
  echo "✓ Agentic AI platform ready"
}

# ─── Summary ──────────────────────────────────────────────────────────
print_summary() {
  echo ""
  echo "═══════════════════════════════════════════════════════"
  echo "  Bootstrap Complete!"
  echo "═══════════════════════════════════════════════════════"
  echo ""
  echo "  Next Steps:"
  echo "  1. Review infrastructure in terraform/${CLOUD}/"
  echo "  2. Connect to cluster: kubectl get nodes"
  echo "  3. Open Backstage: cd backstage/app && yarn dev"
  echo "  4. Test agents: cd agentic-ai && python agents/supervisor.py"
  echo "  5. View dashboards: kubectl port-forward svc/grafana 3000:80 -n monitoring"
  echo ""
  echo "  Documentation:"
  echo "  - Architecture: architecture/"
  echo "  - Runbooks:     runbooks/"
  echo "  - Roadmap:      docs/implementation-roadmap.md"
  echo ""
}

# ─── Main ─────────────────────────────────────────────────────────────
main() {
  check_prerequisites
  bootstrap_infrastructure
  setup_kubernetes
  bootstrap_backstage
  setup_agents
  print_summary
}

main "$@"
