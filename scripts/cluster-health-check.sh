#!/usr/bin/env bash
# Cluster Health Check Script
# Quick diagnostic overview of Kubernetes cluster health
# Run before deployments, post-incident, or as part of daily ops

set -euo pipefail

NAMESPACE="${1:-production}"
OUTPUT_FORMAT="${2:-text}"  # text | json | markdown

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'
BOLD='\033[1m'

issues=()
warnings=()

check() {
    local name="$1"
    local cmd="$2"
    local expected="$3"

    result=$(eval "${cmd}" 2>&1) || result="ERROR: $?"
    if echo "${result}" | grep -q "${expected}"; then
        echo -e "  ${GREEN}✓${NC} ${name}"
        return 0
    else
        echo -e "  ${RED}✗${NC} ${name}"
        issues+=("${name}: ${result}")
        return 1
    fi
}

warn_check() {
    local name="$1"
    local cmd="$2"
    local expected="$3"

    result=$(eval "${cmd}" 2>&1) || result="ERROR"
    if echo "${result}" | grep -q "${expected}"; then
        echo -e "  ${GREEN}✓${NC} ${name}"
    else
        echo -e "  ${YELLOW}⚠${NC} ${name}"
        warnings+=("${name}")
    fi
}

echo ""
echo -e "${BOLD}════════════════════════════════════════${NC}"
echo -e "${BOLD}  Cluster Health Check${NC}"
echo -e "${BOLD}  Namespace: ${NAMESPACE}${NC}"
echo -e "${BOLD}════════════════════════════════════════${NC}"

# ─── Cluster Connectivity ─────────────────────────────────────────────
echo ""
echo -e "${BLUE}── Cluster Connectivity ──────────────────${NC}"
check "kubectl available" "kubectl version --client 2>&1" "Client Version"
check "API server reachable" "kubectl cluster-info 2>&1" "is running"

# ─── Node Health ──────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}── Node Health ───────────────────────────${NC}"
total_nodes=$(kubectl get nodes --no-headers 2>/dev/null | wc -l)
ready_nodes=$(kubectl get nodes --no-headers 2>/dev/null | grep " Ready" | wc -l)
echo -e "  ${GREEN}✓${NC} Nodes: ${ready_nodes}/${total_nodes} Ready"
if [ "${ready_nodes}" -lt "${total_nodes}" ]; then
    issues+=("Nodes not ready: $((total_nodes - ready_nodes)) nodes degraded")
fi

# ─── System Components ────────────────────────────────────────────────
echo ""
echo -e "${BLUE}── System Components ─────────────────────${NC}"
warn_check "CoreDNS" "kubectl get pods -n kube-system -l k8s-app=kube-dns --no-headers" "Running"
warn_check "cert-manager" "kubectl get pods -n cert-manager --no-headers" "Running"
warn_check "kyverno" "kubectl get pods -n kyverno --no-headers" "Running"
warn_check "Prometheus" "kubectl get pods -n monitoring -l app.kubernetes.io/name=prometheus --no-headers" "Running"
warn_check "Grafana" "kubectl get pods -n monitoring -l app.kubernetes.io/name=grafana --no-headers" "Running"
warn_check "ArgoCD" "kubectl get pods -n argocd --no-headers" "Running"

# ─── Production Namespace ─────────────────────────────────────────────
echo ""
echo -e "${BLUE}── ${NAMESPACE} Namespace ────────────────────${NC}"
failing_pods=$(kubectl get pods -n "${NAMESPACE}" --field-selector='status.phase!=Running,status.phase!=Succeeded' --no-headers 2>/dev/null | grep -v "Completed" | wc -l)
total_pods=$(kubectl get pods -n "${NAMESPACE}" --no-headers 2>/dev/null | wc -l)
echo -e "  ${GREEN}✓${NC} Pods: $((total_pods - failing_pods))/${total_pods} healthy"
if [ "${failing_pods}" -gt 0 ]; then
    issues+=("${failing_pods} failing pods in ${NAMESPACE}")
    kubectl get pods -n "${NAMESPACE}" --field-selector='status.phase!=Running,status.phase!=Succeeded' --no-headers 2>/dev/null | head -10
fi

crashloop_count=$(kubectl get pods -n "${NAMESPACE}" --no-headers 2>/dev/null | grep "CrashLoop" | wc -l)
if [ "${crashloop_count}" -gt 0 ]; then
    echo -e "  ${RED}✗${NC} CrashLoopBackOff: ${crashloop_count} pods"
    issues+=("${crashloop_count} pods in CrashLoopBackOff in ${NAMESPACE}")
else
    echo -e "  ${GREEN}✓${NC} No CrashLoopBackOff"
fi

# ─── Resource Usage ───────────────────────────────────────────────────
echo ""
echo -e "${BLUE}── Resource Usage ────────────────────────${NC}"
if command -v kubectl >/dev/null && kubectl top nodes >/dev/null 2>&1; then
    echo "  Node resource utilization:"
    kubectl top nodes 2>/dev/null | awk 'NR>1 {
        cpu=$3; mem=$5;
        gsub(/%/, "", cpu); gsub(/%/, "", mem);
        status="✓";
        if (cpu+0 > 80 || mem+0 > 80) status="⚠";
        printf "    %s Node: %s — CPU: %s%% Mem: %s%%\n", status, $1, $3, $5
    }'
fi

# ─── Recent Events ────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}── Recent Warning Events ─────────────────${NC}"
recent_warnings=$(kubectl get events -n "${NAMESPACE}" --field-selector=type=Warning \
    --sort-by='.lastTimestamp' 2>/dev/null | tail -5)
if [ -n "${recent_warnings}" ]; then
    echo "${recent_warnings}"
else
    echo -e "  ${GREEN}✓${NC} No recent warning events"
fi

# ─── Summary ──────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}════════════════════════════════════════${NC}"
echo -e "${BOLD}  Summary${NC}"
echo ""

if [ ${#issues[@]} -eq 0 ] && [ ${#warnings[@]} -eq 0 ]; then
    echo -e "  ${GREEN}${BOLD}✓ CLUSTER HEALTHY${NC}"
elif [ ${#issues[@]} -eq 0 ]; then
    echo -e "  ${YELLOW}${BOLD}⚠ CLUSTER HEALTHY WITH WARNINGS${NC}"
    for w in "${warnings[@]}"; do echo -e "  ${YELLOW}⚠${NC} ${w}"; done
else
    echo -e "  ${RED}${BOLD}✗ CLUSTER HAS ISSUES${NC}"
    for i in "${issues[@]}"; do echo -e "  ${RED}✗${NC} ${i}"; done
    for w in "${warnings[@]}"; do echo -e "  ${YELLOW}⚠${NC} ${w}"; done
fi

echo -e "${BOLD}════════════════════════════════════════${NC}"
echo ""

[ ${#issues[@]} -gt 0 ] && exit 1 || exit 0
