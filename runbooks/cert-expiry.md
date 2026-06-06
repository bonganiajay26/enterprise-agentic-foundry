# Runbook: Certificate Expiring / Expired

**Alert:** `CertificateExpiringSoon` — cert expires in < 14 days  
**Alert:** `CertificateExpired` — cert already expired  
**Severity:** P1 (expired), P2 (expiring soon)

---

## Investigation

```bash
# List all certificates and their expiry
kubectl get certificates --all-namespaces \
  -o custom-columns="NAMESPACE:.metadata.namespace,NAME:.metadata.name,READY:.status.conditions[0].status,EXPIRY:.status.notAfter"

# Check cert-manager managed certificates
kubectl describe certificate <cert-name> -n <namespace>

# Check certificate request status
kubectl get certificaterequests -n <namespace>

# Check cert-manager logs for renewal errors
kubectl logs -n cert-manager -l app=cert-manager --tail=100

# Check ACME challenge status (Let's Encrypt)
kubectl get challenges --all-namespaces
kubectl describe challenge <challenge-name> -n <namespace>
```

---

## cert-manager Managed Certificates

### Force Certificate Renewal

```bash
# Delete the cert secret — cert-manager will re-issue
kubectl delete secret <cert-secret-name> -n <namespace>

# OR: Delete and recreate the Certificate resource
kubectl delete certificate <cert-name> -n <namespace>
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: <cert-name>
  namespace: <namespace>
spec:
  secretName: <cert-secret-name>
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - your-domain.com
EOF
```

### Check ACME HTTP-01 Challenge

```bash
# The challenge creates a temporary pod + ingress
# Verify DNS resolves correctly
nslookup your-domain.com

# Verify challenge URL is accessible
curl -v http://your-domain.com/.well-known/acme-challenge/<token>

# If DNS/ingress issue: check ingress controller
kubectl get ingress -n cert-manager
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=50
```

---

## Manual Certificate Rotation (external certs)

```bash
# Azure Key Vault: Create new version
az keyvault certificate import \
  --vault-name <vault-name> \
  --name <cert-name> \
  --file new-cert.pem

# AWS ACM: Import new certificate
aws acm import-certificate \
  --certificate fileb://new-cert.pem \
  --private-key fileb://private-key.pem \
  --certificate-arn <existing-arn>

# Force Kubernetes secret rotation (External Secrets)
kubectl annotate externalsecret <es-name> \
  force-sync=$(date +%s) \
  -n <namespace>
```

---

## Prevent Future Expiry Issues

1. Ensure cert-manager is running: `kubectl get pods -n cert-manager`
2. Verify ClusterIssuer is configured: `kubectl get clusterissuer`
3. Set alert for 30 days before expiry (not just 14)
4. Enable cert-manager metrics in Prometheus
5. Configure renewal window to 60 days before expiry in Certificate spec
