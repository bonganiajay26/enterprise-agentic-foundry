# OPA Policy — Cost Controls
# Prevents resource over-provisioning and enforces cost guardrails.

package platform.governance.cost

import future.keywords.contains
import future.keywords.if

# Maximum resource requests per container in non-production
max_cpu_non_prod := "4"
max_memory_non_prod_gi := 8

# ─── CPU request limit in non-production ─────────────────────────────
deny contains msg if {
    input.review.object.kind == "Pod"
    namespace := input.review.object.metadata.namespace
    namespace in {"dev", "staging", "sandbox"}
    container := input.review.object.spec.containers[_]
    cpu_request := container.resources.requests.cpu
    cpu_value := units.parse_bytes(cpu_request)
    cpu_value > units.parse_bytes("4000m")
    msg := sprintf("Container '%v' CPU request '%v' exceeds non-production limit of 4 cores",
        [container.name, cpu_request])
}

# ─── Memory request limit in non-production ───────────────────────────
deny contains msg if {
    input.review.object.kind == "Pod"
    namespace := input.review.object.metadata.namespace
    namespace in {"dev", "staging", "sandbox"}
    container := input.review.object.spec.containers[_]
    mem_request := container.resources.requests.memory
    mem_bytes := units.parse_bytes(mem_request)
    mem_bytes > 8 * 1024 * 1024 * 1024
    msg := sprintf("Container '%v' memory request '%v' exceeds non-production limit of 8Gi",
        [container.name, mem_request])
}

# ─── Require resource limits ──────────────────────────────────────────
deny contains msg if {
    input.review.object.kind == "Pod"
    container := input.review.object.spec.containers[_]
    not container.resources.limits.cpu
    msg := sprintf("Container '%v' missing CPU limit — required for cost accounting",
        [container.name])
}

deny contains msg if {
    input.review.object.kind == "Pod"
    container := input.review.object.spec.containers[_]
    not container.resources.limits.memory
    msg := sprintf("Container '%v' missing memory limit — required for cost accounting",
        [container.name])
}

# ─── Warn on missing HPA for Deployments in production ────────────────
# Note: This check requires cross-resource validation — better enforced in CI
warn contains msg if {
    input.review.object.kind == "Deployment"
    input.review.object.metadata.namespace == "production"
    replicas := input.review.object.spec.replicas
    replicas > 1
    msg := sprintf("Deployment '%v' has %v fixed replicas — consider HPA for cost optimization",
        [input.review.object.metadata.name, replicas])
}
