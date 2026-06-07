# Issue <TYPE-YEAR-SEQUENCE>

**Severity:** P1 | P2 | P3 | P4
**Status:** open | in_progress | resolved | verified | closed
**Detected by:** <agent name | human — team/handle>
**Detection mechanism:** <alert name | manual report | scheduled audit | code review>
**Date opened:** YYYY-MM-DD
**Date resolved:** YYYY-MM-DD
**Owner:** <team or individual accountable for resolution>

---

## Description

<What happened, in plain language. Who/what was affected, for how long,
and what was the user/business impact? Avoid jargon — this section must be
readable by non-engineers (compliance auditors, leadership) two years from now.>

## Evidence

- **Logs:** `<Loki query, e.g. {service="payment-api", level="error"} |= "issue_id=INC-2026-0142"  >`
- **Metrics:** `<Grafana dashboard URL + panel, e.g. "Platform / SLOs" filtered to payment-api>`
- **Traces:** `<Tempo trace ID(s) or search query>`
- **Alerts fired:** `<Alertmanager alert name(s) and firing timestamps>`
- **Screenshots / artifacts:** `<links to attached evidence — stored in compliance-evidence bucket>`

## Root Cause

<The ACTUAL underlying cause — apply the "5 Whys" technique. Do not stop at
the first symptom. Example:
  Symptom: Pods crash-looping
  Why? -> OOMKilled
  Why? -> Memory limit too low for new feature's batch processing
  Why? -> Helm values weren't updated when the feature was merged
  Why? -> No CI gate validates resource requests against load-test results
  Why? -> Platform lacked a "resource sizing" step in the release checklist  <- ROOT CAUSE>
>

## Resolution

<What was changed, and — critically — WHY this fixes the root cause and not
just the symptom. If this was an Auto-Remediation Agent action, include the
classification (AUTOMATIC | AUTOMATIC_WITH_CANARY | APPROVAL_REQUIRED) and,
if gated, the approver(s) and approval timestamp.>

**Remediation classification:** <category — see agentic-ai/agents/remediation_agent.py>
**Approved by (if gated):** <name/role + timestamp, or "N/A — automatic">

## Files Changed

- `path/to/file1` — <one-line description of the change> ([PR #123](link))
- `path/to/file2` — <one-line description of the change> ([PR #123](link))

## Validation

- [ ] CI pipeline green (link to run)
- [ ] Security scan clean — no new findings ≥ CVSS 7.0
- [ ] Smoke tests passed (`tests/smoke/smoke-test.sh`)
- [ ] Integration tests passed (`tests/integration/`)
- [ ] SLO burn-rate normal for 30 minutes post-deploy (link to dashboard)
- [ ] Affected stakeholders notified

## Prevention

<What stops this from happening again? Must be ONE OR MORE of:
  - A new regression test (link to the test file/PR)
  - A new or updated alert rule (link to monitoring/alertmanager.yml change)
  - A new or updated OPA/Kyverno/Falco policy (link to governance/security policy PR)
  - A runbook update (link to the runbooks/ file)
  - A process/checklist change (link to docs/CONTRIBUTING.md or release checklist PR)
"We'll be more careful" is NOT an acceptable prevention measure.>

## Status

<Current status with a one-line note on what's blocking progress to the next stage,
if not yet closed. Update this line as the issue moves through its lifecycle.>

---
*Generated via the platform's Issue Management Framework — see [docs/issues/README.md](./README.md)
for the full lifecycle, SLAs, and the agents that auto-populate this template
(`remediation_agent.write_issue_record`, Incident Response Agent postmortems,
Security Agent CVSS findings, Governance Agent compliance audits).*
