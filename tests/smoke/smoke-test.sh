#!/usr/bin/env bash
# Platform Smoke Tests
# Usage: ./tests/smoke/smoke-test.sh [environment] [base_url]
# Examples:
#   ./tests/smoke/smoke-test.sh production https://api.your-domain.com
#   TARGET_ENV=dev BASE_URL=https://dev.your-domain.com ./tests/smoke/smoke-test.sh

set -euo pipefail

ENVIRONMENT="${1:-${TARGET_ENV:-staging}}"
BASE_URL="${2:-${BASE_URL:-http://localhost:8080}}"
TIMEOUT=10
PASS=0
FAIL=0
SKIP=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_pass() { echo -e "${GREEN}✓ PASS${NC}: $1"; ((PASS++)); }
log_fail() { echo -e "${RED}✗ FAIL${NC}: $1"; ((FAIL++)); }
log_skip() { echo -e "${YELLOW}⊘ SKIP${NC}: $1"; ((SKIP++)); }
log_info() { echo -e "  → $1"; }

echo "════════════════════════════════════════"
echo "  Platform Smoke Tests"
echo "  Environment: ${ENVIRONMENT}"
echo "  Base URL:    ${BASE_URL}"
echo "════════════════════════════════════════"

# ─── Helper Functions ─────────────────────────────────────────────────
http_check() {
    local name="$1"
    local url="$2"
    local expected_status="${3:-200}"
    local expected_body="${4:-}"

    response=$(curl -s -o /tmp/smoke_body -w "%{http_code}" \
        --max-time "${TIMEOUT}" \
        --retry 3 \
        --retry-delay 2 \
        "${url}" 2>&1) || { log_fail "${name}: Connection refused or timeout"; return; }

    if [ "${response}" = "${expected_status}" ]; then
        if [ -n "${expected_body}" ]; then
            if grep -q "${expected_body}" /tmp/smoke_body 2>/dev/null; then
                log_pass "${name} (${response})"
            else
                log_fail "${name}: Expected body '${expected_body}' not found (HTTP ${response})"
                log_info "Body: $(cat /tmp/smoke_body | head -c 200)"
            fi
        else
            log_pass "${name} (HTTP ${response})"
        fi
    else
        log_fail "${name}: Expected HTTP ${expected_status}, got ${response}"
        log_info "Body: $(cat /tmp/smoke_body | head -c 200)"
    fi
}

k8s_check() {
    local name="$1"
    local namespace="$2"
    local resource="$3"

    if ! command -v kubectl >/dev/null 2>&1; then
        log_skip "${name}: kubectl not available"
        return
    fi

    if kubectl get "${resource}" -n "${namespace}" >/dev/null 2>&1; then
        ready=$(kubectl get "${resource}" -n "${namespace}" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
        desired=$(kubectl get "${resource}" -n "${namespace}" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")
        if [ "${ready}" = "${desired}" ]; then
            log_pass "${name} (${ready}/${desired} ready)"
        else
            log_fail "${name}: Only ${ready}/${desired} replicas ready"
        fi
    else
        log_fail "${name}: Resource not found"
    fi
}

# ─── Health Check Tests ───────────────────────────────────────────────
echo ""
echo "── Health Endpoints ──────────────────────"

http_check "Liveness probe" "${BASE_URL}/health/live" "200"
http_check "Readiness probe" "${BASE_URL}/health/ready" "200"
http_check "Health check" "${BASE_URL}/health" "200" "ok"
http_check "Metrics endpoint" "${BASE_URL}/metrics" "200"

# ─── API Tests ────────────────────────────────────────────────────────
echo ""
echo "── API Endpoints ─────────────────────────"

http_check "API version" "${BASE_URL}/api/version" "200"
http_check "API root" "${BASE_URL}/api" "200"

# ─── Auth Tests ───────────────────────────────────────────────────────
echo ""
echo "── Authentication ────────────────────────"

# Unauthorized access should return 401
http_check "Unauthorized returns 401" "${BASE_URL}/api/protected" "401"

# ─── Kubernetes Tests ────────────────────────────────────────────────
if [ "${ENVIRONMENT}" != "local" ]; then
    echo ""
    echo "── Kubernetes Health ─────────────────────"
    K8S_NS="${ENVIRONMENT}"
    k8s_check "Main deployment ready" "${K8S_NS}" "deployment/myapp"
    k8s_check "HPA configured" "${K8S_NS}" "hpa/myapp"
fi

# ─── Observability Tests ──────────────────────────────────────────────
if [ "${ENVIRONMENT}" != "production" ]; then
    echo ""
    echo "── Observability ─────────────────────────"
    PROMETHEUS_URL="${PROMETHEUS_URL:-http://prometheus:9090}"
    http_check "Prometheus healthy" "${PROMETHEUS_URL}/-/healthy" "200" || log_skip "Prometheus: not accessible"
    GRAFANA_URL="${GRAFANA_URL:-http://grafana:3000}"
    http_check "Grafana healthy" "${GRAFANA_URL}/api/health" "200" || log_skip "Grafana: not accessible"
fi

# ─── Results ─────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════"
echo "  Results: ${PASS} passed, ${FAIL} failed, ${SKIP} skipped"
echo "════════════════════════════════════════"

if [ "${FAIL}" -gt 0 ]; then
    echo -e "${RED}SMOKE TESTS FAILED${NC}"
    exit 1
else
    echo -e "${GREEN}ALL SMOKE TESTS PASSED${NC}"
    exit 0
fi
