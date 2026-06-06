# OPA Gatekeeper — Universal Platform Admission Policies
# Deploy via: kubectl apply -f security/opa/

package platform.admission

import future.keywords.contains
import future.keywords.if
import future.keywords.in

# ─── Deny Privileged Containers ───────────────────────────────────────
deny contains msg if {
    input.review.object.kind == "Pod"
    container := input.review.object.spec.containers[_]
    container.securityContext.privileged == true
    msg := sprintf("Container '%v' must not run as privileged", [container.name])
}

deny contains msg if {
    input.review.object.kind == "Pod"
    container := input.review.object.spec.initContainers[_]
    container.securityContext.privileged == true
    msg := sprintf("InitContainer '%v' must not run as privileged", [container.name])
}

# ─── Require Non-Root ─────────────────────────────────────────────────
deny contains msg if {
    input.review.object.kind == "Pod"
    not input.review.object.spec.securityContext.runAsNonRoot == true
    msg := "Pod must set securityContext.runAsNonRoot: true"
}

deny contains msg if {
    input.review.object.kind == "Pod"
    container := input.review.object.spec.containers[_]
    not container.securityContext.runAsNonRoot == true
    msg := sprintf("Container '%v' must set securityContext.runAsNonRoot: true", [container.name])
}

# ─── Require Read-Only Root Filesystem ───────────────────────────────
deny contains msg if {
    input.review.object.kind == "Pod"
    container := input.review.object.spec.containers[_]
    not container.securityContext.readOnlyRootFilesystem == true
    msg := sprintf("Container '%v' must set readOnlyRootFilesystem: true", [container.name])
}

# ─── Require Resource Limits ──────────────────────────────────────────
deny contains msg if {
    input.review.object.kind == "Pod"
    container := input.review.object.spec.containers[_]
    not container.resources.limits.memory
    msg := sprintf("Container '%v' must set resources.limits.memory", [container.name])
}

deny contains msg if {
    input.review.object.kind == "Pod"
    container := input.review.object.spec.containers[_]
    not container.resources.limits.cpu
    msg := sprintf("Container '%v' must set resources.limits.cpu", [container.name])
}

deny contains msg if {
    input.review.object.kind == "Pod"
    container := input.review.object.spec.containers[_]
    not container.resources.requests.memory
    msg := sprintf("Container '%v' must set resources.requests.memory", [container.name])
}

# ─── Require Dropped Capabilities ────────────────────────────────────
deny contains msg if {
    input.review.object.kind == "Pod"
    container := input.review.object.spec.containers[_]
    not "ALL" in container.securityContext.capabilities.drop
    msg := sprintf("Container '%v' must drop ALL capabilities", [container.name])
}

# ─── Deny Privilege Escalation ────────────────────────────────────────
deny contains msg if {
    input.review.object.kind == "Pod"
    container := input.review.object.spec.containers[_]
    container.securityContext.allowPrivilegeEscalation == true
    msg := sprintf("Container '%v' must set allowPrivilegeEscalation: false", [container.name])
}

# ─── Require Seccomp Profile ──────────────────────────────────────────
deny contains msg if {
    input.review.object.kind == "Pod"
    not input.review.object.spec.securityContext.seccompProfile
    msg := "Pod must set a seccompProfile (RuntimeDefault or Localhost)"
}

# ─── Deny Host Namespaces ─────────────────────────────────────────────
deny contains msg if {
    input.review.object.kind == "Pod"
    input.review.object.spec.hostPID == true
    msg := "Pod must not use hostPID"
}

deny contains msg if {
    input.review.object.kind == "Pod"
    input.review.object.spec.hostIPC == true
    msg := "Pod must not use hostIPC"
}

deny contains msg if {
    input.review.object.kind == "Pod"
    input.review.object.spec.hostNetwork == true
    not input.review.object.metadata.namespace in ["kube-system", "monitoring", "cert-manager"]
    msg := "Pod must not use hostNetwork (unless in exempt namespace)"
}

# ─── Require Labels ───────────────────────────────────────────────────
required_labels := {"app.kubernetes.io/name", "app.kubernetes.io/instance", "app.kubernetes.io/version"}

deny contains msg if {
    input.review.object.kind in ["Deployment", "StatefulSet", "DaemonSet"]
    label := required_labels[_]
    not input.review.object.metadata.labels[label]
    msg := sprintf("Resource must have label: '%v'", [label])
}

# ─── Require Image Tag (not latest) ──────────────────────────────────
deny contains msg if {
    input.review.object.kind == "Pod"
    container := input.review.object.spec.containers[_]
    namespace := input.review.object.metadata.namespace
    namespace in ["production", "staging"]
    endswith(container.image, ":latest")
    msg := sprintf("Container '%v' must not use 'latest' tag in %v", [container.name, namespace])
}

# ─── Ingress TLS Required in Production ──────────────────────────────
deny contains msg if {
    input.review.object.kind == "Ingress"
    input.review.object.metadata.namespace == "production"
    count(input.review.object.spec.tls) == 0
    msg := "Ingress in production namespace must configure TLS"
}
