# KB: Pods Stuck in CrashLoopBackOff on `orders` namespace

## Symptoms
Pods in the `orders` namespace repeatedly restart and show status
`CrashLoopBackOff`. `kubectl logs` shows `OOMKilled` in the previous
container's termination reason.

## Cause
The `orders-api` deployment's memory limit was left at the default
`256Mi`, which is insufficient after the v3 catalog schema migration
increased per-request memory usage.

## Resolution
1. Run `kubectl describe pod <pod-name> -n orders` and confirm
   `Reason: OOMKilled` under the last termination state.
2. Patch the deployment: `kubectl set resources deployment/orders-api -n
   orders --limits=memory=512Mi --requests=memory=256Mi`.
3. Monitor the pods for 15 minutes to confirm restarts stop.
4. If OOMKilled continues at 512Mi, escalate to the orders-api team to
   profile the memory usage rather than continuing to raise the limit.

## Related Links
- `orders-api` deployment manifest: `k8s/orders/deployment.yaml`
- Grafana dashboard: `orders-api-memory`
