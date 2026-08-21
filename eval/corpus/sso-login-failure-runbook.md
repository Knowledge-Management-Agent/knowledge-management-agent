# Runbook: SSO Login Failures — Expired OAuth Signing Certificate

## When to use this runbook
Users report being unable to log in via SSO (redirected back to the login page after
authenticating with the identity provider, or shown an "invalid token signature"
error), while direct/non-SSO auth paths (if any exist) continue to work normally.

## Diagnosis
1. Check the `auth-gateway` service logs for `JWT signature verification failed` or
   `certificate expired` errors around the time reports started.
2. Confirm with the identity provider (Okta) admin console whether the signing
   certificate used for this app's SAML/OIDC integration has expired — Okta shows an
   expiry countdown under Applications → Sign On → Certificate.
3. Check whether an alert was ever configured for certificate expiry — if this
   runbook is being used, it likely was not (see Lessons section of the linked RCA).

## Resolution
1. In the Okta admin console, generate a new signing certificate for the affected
   application integration.
2. Download the new certificate's metadata (X.509 cert or metadata XML, depending on
   protocol).
3. Update `auth-gateway`'s configured identity-provider certificate
   (`kubectl edit configmap auth-gateway-idp-config -n platform` or the equivalent
   secrets-manager entry, depending on environment) with the new certificate.
4. Restart `auth-gateway` pods to pick up the new certificate:
   `kubectl rollout restart deployment/auth-gateway -n platform`.
5. Verify: attempt an SSO login yourself before declaring the incident resolved.
6. Set a calendar reminder / monitoring alert at least 30 days before the new
   certificate's expiry date to avoid a repeat.

## Escalation
If the identity provider itself is unreachable (not just a certificate issue), this is
outside `auth-gateway`'s control — escalate to the IdP vendor's status page /support
channel instead of continuing this runbook.
