# OPA Policy — Mandatory Resource Tagging
# Enforces that all Kubernetes resources have required platform labels.
# Deploy via Gatekeeper ConstraintTemplate.

package platform.governance.tagging

import future.keywords.contains
import future.keywords.if
import future.keywords.in

# Required labels for all workload resources
required_labels := {
    "app.kubernetes.io/name",
    "app.kubernetes.io/version",
    "app.kubernetes.io/component",
    "environment",
    "owner",
    "cost-center",
}

# Resources that must be labeled
labeled_resources := {"Deployment", "StatefulSet", "DaemonSet", "CronJob", "Service"}

# Exempt namespaces (system)
exempt_namespaces := {"kube-system", "kube-public", "kube-node-lease", "cert-manager"}

# ─── Deny missing required labels ────────────────────────────────────
deny contains msg if {
    input.review.object.kind in labeled_resources
    not input.review.object.metadata.namespace in exempt_namespaces
    label := required_labels[_]
    not input.review.object.metadata.labels[label]
    msg := sprintf("Resource '%v/%v' missing required label: '%v'",
        [input.review.object.metadata.namespace,
         input.review.object.metadata.name,
         label])
}

# ─── Validate environment label values ───────────────────────────────
valid_environments := {"dev", "staging", "production", "sandbox"}

deny contains msg if {
    input.review.object.kind in labeled_resources
    not input.review.object.metadata.namespace in exempt_namespaces
    env := input.review.object.metadata.labels["environment"]
    not env in valid_environments
    msg := sprintf("Invalid environment label value '%v'. Must be one of: %v",
        [env, valid_environments])
}

# ─── Validate cost-center format ─────────────────────────────────────
deny contains msg if {
    input.review.object.kind in labeled_resources
    not input.review.object.metadata.namespace in exempt_namespaces
    cc := input.review.object.metadata.labels["cost-center"]
    not regex.match(`^[A-Z]{2,4}-[0-9]{4,6}$`, cc)
    msg := sprintf("cost-center label '%v' must match pattern: CC-NNNNNN (e.g. ENG-123456)", [cc])
}

# ─── Warn for missing recommended labels ─────────────────────────────
warn contains msg if {
    input.review.object.kind in labeled_resources
    not input.review.object.metadata.namespace in exempt_namespaces
    not input.review.object.metadata.labels["app.kubernetes.io/part-of"]
    msg := sprintf("Resource '%v/%v' missing recommended label: 'app.kubernetes.io/part-of'",
        [input.review.object.metadata.namespace, input.review.object.metadata.name])
}
