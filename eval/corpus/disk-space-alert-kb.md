# KB: Disk Space Critical Alert on Log-Forwarding Nodes

## Symptoms
The `disk-space-critical` alert fires for hosts in the `log-forwarder`
fleet, typically at 90% utilization on the `/var/log` partition.

## Cause
The `fluentd` buffer directory fills up when the downstream log sink
(Elasticsearch) is slow to ingest, and the default buffer retention of 7
days is too long for the 100GB `/var/log` partition size on these hosts.

## Resolution
1. SSH to the affected host and check buffer size:
   `du -sh /var/log/fluentd/buffer`.
2. If Elasticsearch ingestion is confirmed healthy, safely clear old
   buffer chunks older than 24 hours:
   `find /var/log/fluentd/buffer -mtime +1 -delete`.
3. If Elasticsearch ingestion is degraded, do not delete buffer data —
   escalate to the Search Platform team instead, since deleting the
   buffer would cause permanent log loss.
4. As a longer-term fix, file a ticket to reduce `fluentd` buffer
   retention from 7 days to 2 days on this fleet.

## Related Links
- Fluentd config: `ops/fluentd/log-forwarder.conf`
