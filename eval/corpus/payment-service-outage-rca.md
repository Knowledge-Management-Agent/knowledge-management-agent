# RCA: Payment Service Full Outage — 2026-01-19

## Incident Summary
The `payment-service` was fully unavailable for 12 minutes (09:31-09:43
UTC) on 2026-01-19, blocking all checkout completions.

## Timeline
- 09:31 UTC: `payment-service` pods begin failing readiness probes after a
  routine credential rotation for the `payments-db` user.
- 09:34 UTC: PagerDuty pages the payments on-call engineer.
- 09:40 UTC: Engineer identifies that the rotated database password was
  not synced to the `payment-service` Kubernetes secret.
- 09:43 UTC: Secret updated and pods restarted; service recovers.

## Root Cause
The credential rotation automation updated the password in the secrets
manager but the sync job that propagates it into
`k8s://platform/payment-db-credentials` had been silently failing for 3
days due to an expired service account token.

## Impact
100% of checkout attempts failed for 12 minutes; an estimated $18,000 in
gross merchandise value was affected.

## Remediation
- Renewed the sync job's service account token.
- Added a monitoring alert on sync job failures (previously unmonitored).

## Lessons Learned
Credential rotation runbooks must include a verification step confirming
the new credential is live in the consuming service, not just written to
the secrets manager.
