# KB: High Redis Eviction Rate on `session-cache` Cluster

## Symptoms
The `session-cache` Redis cluster shows a rising `evicted_keys` metric in
Grafana, and users report being logged out unexpectedly.

## Cause
The cluster's `maxmemory` is set to 4GB with the `allkeys-lru` policy,
which is undersized after the mobile app's v5.2 release increased average
session object size from 2KB to 9KB.

## Resolution
1. Confirm the current eviction rate with `redis-cli -h session-cache
   info stats | grep evicted_keys`.
2. As an immediate mitigation, raise `maxmemory` to 8GB via
   `redis-cli -h session-cache config set maxmemory 8gb`.
3. File a capacity ticket to permanently resize the cluster's node type,
   since `config set` changes do not persist across a cluster restart.
4. Confirm with the mobile team whether the 9KB session object size is
   expected or a regression before treating this as fully resolved.

## Related Links
- Grafana dashboard: `session-cache-memory`
- Capacity planning doc: `redis-capacity-2026`
