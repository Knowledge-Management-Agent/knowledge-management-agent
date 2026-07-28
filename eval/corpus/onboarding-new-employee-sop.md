# SOP: New SRE Team Member Onboarding

## Purpose
Standardize the onboarding process for new Site Reliability Engineers
joining the Platform Operations team.

## Scope
Applies to all new hires and internal transfers into the Platform
Operations team.

## Prerequisites
- Signed offer letter and completed background check.
- Manager has submitted an access request via the `IT-Access` ticket queue
  at least 5 business days before the start date.

## Procedure
1. Day 1: IT provisions a laptop and creates accounts in Okta, GitHub, and
   the internal wiki.
2. Day 1: New hire completes the mandatory security awareness training
   (approximately 2 hours).
3. Day 2-3: New hire shadows an on-call engineer for a full rotation
   without carrying the pager.
4. Day 5: New hire is granted read-only access to the `prod-readonly`
   Kubernetes cluster role.
5. Day 15: After completing the on-call runbook quiz (minimum passing
   score: 80%), the new hire is added to the secondary on-call rotation.
6. Day 30: Manager conducts a 30-day check-in and grants full on-call
   access if the quiz and shadow rotation were completed successfully.

## Rollback / Exceptions
If the background check is delayed, IT provisioning is postponed and the
new hire's start date may shift; escalate to HR Business Partner.
