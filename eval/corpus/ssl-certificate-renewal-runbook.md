# Runbook: SSL Certificate Renewal for `*.internal-ops.example.com`

## Purpose
Renew the wildcard TLS certificate used by internal operations tools
before it expires, avoiding an outage like the 2025-11-02 incident where
the certificate expired unnoticed.

## Procedure
1. Confirm the current certificate's expiry with
   `openssl x509 -enddate -noout -in wildcard.crt`.
2. Request a new certificate from the internal CA via the `cert-request`
   CLI: `cert-request new --cn "*.internal-ops.example.com" --days 365`.
3. Once issued, upload the new certificate and key to the
   `internal-ops-tls` secret in the `platform` namespace:
   `kubectl create secret tls internal-ops-tls --cert=new.crt --key=new.key
   -n platform --dry-run=client -o yaml | kubectl apply -f -`.
4. Restart the ingress controller pods to pick up the new secret:
   `kubectl rollout restart deployment/ingress-nginx-controller -n
   platform`.
5. Verify with `curl -vI https://grafana.internal-ops.example.com` that the
   new certificate's expiry date is ~365 days out.

## Rollback / Failure Handling
If the ingress controller fails to pick up the new certificate after
restart, check that the secret name referenced in the Ingress resource
matches `internal-ops-tls` exactly.
