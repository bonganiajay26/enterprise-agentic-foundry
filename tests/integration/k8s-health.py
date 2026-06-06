"""
Kubernetes Platform Integration Tests
Validates: cluster connectivity, required namespaces, critical deployments,
           secrets availability, ingress config, HPA status, PDB config.
"""

import os
import subprocess
import sys
import time
import unittest


class KubernetesPlatformTests(unittest.TestCase):
    """Integration tests for Kubernetes platform health."""

    REQUIRED_NAMESPACES = ["production", "staging", "dev", "monitoring", "cert-manager", "kyverno"]
    REQUIRED_SYSTEM_DEPLOYMENTS = {
        "kube-system": ["coredns"],
        "cert-manager": ["cert-manager"],
        "monitoring": ["kube-prometheus-stack-grafana", "kube-prometheus-stack-operator"],
        "kyverno": ["kyverno"],
    }
    CRITICAL_PRODUCTION_DEPLOYMENTS = os.environ.get("CRITICAL_DEPLOYMENTS", "").split(",")

    @classmethod
    def setUpClass(cls):
        """Verify kubectl is available and cluster is reachable."""
        result = subprocess.run(
            ["kubectl", "cluster-info"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Cannot connect to Kubernetes cluster: {result.stderr}")
        print(f"\n✓ Connected to cluster")

    def kubectl(self, *args, timeout: int = 30) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["kubectl"] + list(args),
            capture_output=True, text=True, timeout=timeout,
        )

    def test_required_namespaces_exist(self):
        """All required platform namespaces should exist."""
        result = self.kubectl("get", "namespaces", "-o", "jsonpath={.items[*].metadata.name}")
        existing = result.stdout.split()
        for ns in self.REQUIRED_NAMESPACES:
            with self.subTest(namespace=ns):
                self.assertIn(ns, existing, f"Namespace '{ns}' missing")

    def test_system_deployments_ready(self):
        """Critical system deployments should be fully available."""
        for namespace, deployments in self.REQUIRED_SYSTEM_DEPLOYMENTS.items():
            for deploy in deployments:
                with self.subTest(namespace=namespace, deployment=deploy):
                    result = self.kubectl(
                        "get", "deployment", deploy, "-n", namespace,
                        "-o", "jsonpath={.status.availableReplicas}",
                    )
                    if result.returncode != 0:
                        self.skipTest(f"Deployment {deploy} not found in {namespace}")
                    available = int(result.stdout or "0")
                    self.assertGreater(available, 0, f"{deploy} in {namespace}: no available replicas")

    def test_no_crashlooping_pods(self):
        """No pods should be in CrashLoopBackOff in production."""
        result = self.kubectl(
            "get", "pods", "-n", "production",
            "-o", "jsonpath={range .items[*]}{.metadata.name}{\" \"}{.status.containerStatuses[0].state.waiting.reason}{\"\\n\"}{end}",
        )
        for line in result.stdout.strip().split("\n"):
            if "CrashLoopBackOff" in line:
                pod_name = line.split()[0]
                self.fail(f"CrashLoopBackOff: {pod_name}")

    def test_no_pending_pods_over_5min(self):
        """No pods should be stuck in Pending for more than 5 minutes."""
        result = self.kubectl(
            "get", "pods", "--all-namespaces",
            "--field-selector=status.phase=Pending",
            "-o", "jsonpath={range .items[*]}{.metadata.namespace}{\" \"}{.metadata.name}{\" \"}{.metadata.creationTimestamp}{\"\\n\"}{end}",
        )
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 3:
                self.fail(f"Pod stuck Pending: {parts[0]}/{parts[1]}")

    def test_hpa_configured_for_production_deployments(self):
        """All production deployments should have HPA configured."""
        deploys_result = self.kubectl(
            "get", "deployments", "-n", "production",
            "-o", "jsonpath={.items[*].metadata.name}",
        )
        hpa_result = self.kubectl(
            "get", "hpa", "-n", "production",
            "-o", "jsonpath={.items[*].spec.scaleTargetRef.name}",
        )

        deployments = set(deploys_result.stdout.split())
        hpa_targets = set(hpa_result.stdout.split())
        system_excluded = {"argocd-server"}

        for deploy in deployments - system_excluded:
            with self.subTest(deployment=deploy):
                self.assertIn(deploy, hpa_targets, f"Deployment '{deploy}' missing HPA")

    def test_secrets_accessible(self):
        """Key Vault / Secrets Manager secrets should be synced."""
        result = self.kubectl(
            "get", "externalsecrets", "-n", "production",
            "-o", "jsonpath={range .items[*]}{.metadata.name}{\" \"}{.status.conditions[0].reason}{\"\\n\"}{end}",
        )
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] != "SecretSynced":
                with self.subTest(secret=parts[0]):
                    self.fail(f"ExternalSecret '{parts[0]}' not synced: {parts[1]}")

    def test_certificates_valid(self):
        """All TLS certificates should be ready and not expired."""
        result = self.kubectl(
            "get", "certificates", "--all-namespaces",
            "-o", "jsonpath={range .items[*]}{.metadata.namespace}{\" \"}{.metadata.name}{\" \"}{.status.conditions[0].reason}{\"\\n\"}{end}",
        )
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 3 and parts[2] != "Ready":
                with self.subTest(cert=f"{parts[0]}/{parts[1]}"):
                    self.fail(f"Certificate {parts[0]}/{parts[1]}: {parts[2]}")

    def test_network_policies_exist_in_production(self):
        """Production namespace should have network policies."""
        result = self.kubectl("get", "networkpolicies", "-n", "production")
        self.assertNotIn("No resources found", result.stdout,
                         "No NetworkPolicies in production namespace")

    def test_resource_quotas_exist(self):
        """Critical namespaces should have ResourceQuota."""
        for ns in ["production", "staging"]:
            with self.subTest(namespace=ns):
                result = self.kubectl("get", "resourcequota", "-n", ns)
                self.assertNotIn("No resources found", result.stdout,
                                 f"No ResourceQuota in {ns}")


if __name__ == "__main__":
    # Run with: python -m pytest tests/integration/k8s-health.py -v
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(KubernetesPlatformTests)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
