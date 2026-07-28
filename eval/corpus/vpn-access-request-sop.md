# SOP: VPN Access Request for Contractors

## Purpose
Define the approval and provisioning process for granting VPN access to
short-term contractors.

## Scope
Applies to non-employee contractors requiring access to internal
non-production systems only; production VPN access requires a separate
process (see `prod-vpn-access-sop`).

## Prerequisites
- Signed NDA on file with Legal.
- Sponsoring manager has approved the request in the `Contractor-Access`
  ticket queue.

## Procedure
1. Sponsoring manager submits a `Contractor-Access` ticket including the
   contractor's engagement end date.
2. Security team reviews the request within 2 business days.
3. On approval, IT provisions a time-boxed VPN account in Okta scoped to
   the `contractors-nonprod` group, expiring automatically on the
   engagement end date.
4. Contractor completes VPN setup using the `contractor-vpn-guide` wiki
   page.

## Rollback / Exceptions
If the engagement end date changes, the sponsoring manager must submit an
extension request at least 3 business days before the original
expiration; access is not auto-renewed.
