# Backup Strategy — Universal Agentic DevOps Platform

## Backup Matrix

| Data | Tool | Frequency | Retention | Storage | RPO | RTO |
|---|---|---|---|---|---|---|
| Kubernetes cluster state | Velero | Hourly | 7 days | S3/Blob/GCS | 1h | 30min |
| Application databases (PostgreSQL) | WAL-G / pgBackRest | Continuous WAL + daily full | 35 days | Encrypted object store | 5min | 30min |
| etcd (cluster config) | etcd snapshot | Every 6h | 14 days | Separate storage account | 6h | 15min |
| Secrets (Key Vault) | Soft delete | N/A (always available) | 90 day soft delete | Cloud-native | Near-zero | Near-zero |
| Code / Config | Git | Continuous (push) | Indefinite | GitHub enterprise | Near-zero | Minutes |
| Helm releases | ArgoCD GitOps | On every change | Git history | GitHub | Near-zero | Minutes |
| Container images | Registry replication | On push | 30 day policy | Multi-region registry | Near-zero | Minutes |
| Terraform state | Blob/S3 versioning | On every apply | 30 versions | Versioned storage | Near-zero | Minutes |
| Grafana dashboards | Git + provisioning | On change | Indefinite | GitHub | Near-zero | Minutes |
| MLflow models | Object store | On registration | 90 days | S3/Blob | Continuous | 5min |

---

## Velero Kubernetes Backup

```bash
# Install Velero (Azure example)
velero install \
  --provider azure \
  --plugins velero/velero-plugin-for-microsoft-azure:v1.8.0 \
  --bucket velero-backups \
  --secret-file ./credentials-velero \
  --backup-location-config resourceGroup=${RG},storageAccount=${STORAGE_ACCOUNT} \
  --snapshot-location-config apiTimeout=5m,resourceGroup=${RG} \
  --use-volume-snapshots=true

# Create scheduled backup
velero schedule create daily-full \
  --schedule="0 2 * * *" \
  --include-cluster-resources \
  --ttl 168h \
  --default-volumes-to-restic

velero schedule create hourly-namespaces \
  --schedule="0 * * * *" \
  --include-namespaces production,staging \
  --ttl 48h

# Verify backups
velero backup get
velero backup describe daily-full-<timestamp>

# Test restore (do quarterly)
velero restore create --from-backup daily-full-<timestamp> \
  --include-namespaces test-restore \
  --namespace-mappings production:test-restore
```

---

## PostgreSQL Backup with pgBackRest

```yaml
# pgbackrest.conf
[global]
repo1-type=azure
repo1-azure-account=${AZURE_STORAGE_ACCOUNT}
repo1-azure-key=${AZURE_STORAGE_KEY}
repo1-azure-container=pgbackrest
repo1-retention-full=7
repo1-retention-diff=14
repo1-cipher-type=aes-256-cbc
repo1-cipher-pass=${BACKUP_ENCRYPTION_KEY}

[global:archive-push]
compress-level=3

[main]
pg1-path=/var/lib/postgresql/data
pg1-host=postgres-primary
pg1-host-user=postgres
```

```bash
# Full backup (weekly)
pgbackrest --stanza=main --log-level-console=info backup --type=full

# Differential backup (daily)
pgbackrest --stanza=main backup --type=diff

# Incremental backup (hourly)
pgbackrest --stanza=main backup --type=incr

# Verify backup integrity (monthly)
pgbackrest --stanza=main check

# Test restore (quarterly DR drill)
pgbackrest --stanza=main restore \
  --set=20260101-020000F \
  --target="2026-01-15 14:00:00" \
  --target-action=promote \
  --pg1-path=/var/lib/postgresql/restore
```

---

## Backup Verification Schedule

| Test | Frequency | Responsible | Last Tested |
|---|---|---|---|
| Velero namespace restore | Monthly | SRE | |
| PostgreSQL point-in-time restore | Monthly | DBA | |
| Full DR cluster restore | Quarterly | SRE + DBA | |
| Secret recovery drill | Semi-annually | Security | |
| Terraform state recovery | Annually | Platform | |

---

## Monitoring Backup Health

```yaml
# Prometheus alert: backup older than expected
- alert: VeleroBackupNotRecent
  expr: time() - velero_backup_last_successful_timestamp{schedule="daily-full"} > 86400
  for: 1h
  labels:
    severity: warning
  annotations:
    summary: "Velero daily backup not completed in 24h"
    runbook_url: "runbooks/backup-restore.md"

- alert: PostgreSQLBackupFailed
  expr: pgbackrest_backup_last_error > 0
  labels:
    severity: critical
  annotations:
    summary: "PostgreSQL backup failed"
```
