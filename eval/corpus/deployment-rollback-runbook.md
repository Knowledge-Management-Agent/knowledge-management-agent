# Runbook: Emergency Deployment Rollback

## Purpose
Roll back a production deployment quickly when a new release is causing
customer-facing errors.

## Procedure
1. Identify the affected deployment and its current revision:
   `kubectl rollout history deployment/<name> -n <namespace>`.
2. Roll back to the previous revision:
   `kubectl rollout undo deployment/<name> -n <namespace>`.
3. Watch the rollout status until it completes:
   `kubectl rollout status deployment/<name> -n <namespace>`.
4. Confirm error rates return to baseline in the `service-error-rate`
   Grafana dashboard within 5 minutes of rollback completion.
5. Post an incident summary in #incidents including the revision rolled
   back from and to.

## Rollback / Failure Handling
If `kubectl rollout undo` does not resolve the issue within 5 minutes,
the problem is likely not the code release (e.g. a downstream dependency
outage) — escalate to the incident commander rather than attempting a
second rollback.
