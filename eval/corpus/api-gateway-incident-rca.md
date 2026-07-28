# RCA: API Gateway 502 Errors — 2026-03-11

## Incident Summary
Between 14:02 and 14:47 UTC on 2026-03-11, the public API gateway
`gw-public-01` returned 502 errors for approximately 23% of requests,
affecting the mobile checkout flow.

## Timeline
- 14:02 UTC: Error rate alert fires for `gw-public-01`.
- 14:09 UTC: On-call engineer confirms upstream `checkout-service` pods are
  in `CrashLoopBackOff`.
- 14:22 UTC: Root cause identified as an unhandled null pointer in the new
  `checkout-service` v2.14.0 release, deployed at 13:55 UTC.
- 14:47 UTC: Rollback to `checkout-service` v2.13.2 completes; error rate
  returns to baseline.

## Root Cause
A missing null check in the discount-code validation path of
`checkout-service` v2.14.0 caused the pod to crash whenever a checkout
request omitted a discount code, which is the majority case.

## Impact
An estimated 4,100 checkout attempts failed during the 45-minute window.

## Remediation
- Rolled back to v2.13.2.
- Added a unit test covering the no-discount-code checkout path before
  re-attempting the v2.14.0 rollout.

## Lessons Learned
Canary deployments for `checkout-service` should route at least 5% of
production traffic for 15 minutes before full rollout; this incident
shipped directly to 100%.
