# KB: Order-Confirmation Emails Delayed — Kafka Consumer Group Lag on `order-events`

## Symptoms
Customers report order-confirmation emails arriving 20-40 minutes after checkout
instead of within seconds. No errors are visible in the `checkout-service` logs, and
the order itself is created successfully in the database — only the confirmation email
is delayed. Grafana shows the `order-events` consumer group's lag metric climbing
steadily over the affected window instead of staying near zero.

## Cause
The `notification-service` consumes from the `order-events` Kafka topic to trigger
confirmation emails. A deploy two days prior increased the per-message processing time
in `notification-service` (an added synchronous call to a third-party email-template
API) without increasing the consumer group's partition count or replica count to
compensate. Under normal load this went unnoticed; during a promotional-sale traffic
spike, message production outpaced consumption, and the consumer group fell
increasingly behind — messages were being processed correctly, just very late, since
consumer lag doesn't drop pending messages, it just delays them.

## Resolution
1. Confirm the lag is real, not a false alarm: `kafka-consumer-groups.sh
   --describe --group notification-service --bootstrap-server <broker>` and check the
   `LAG` column per partition.
2. Check `notification-service` pod CPU/memory in Grafana — if pods are not
   resource-constrained, this is a throughput problem, not a capacity problem.
3. Scale `notification-service` replicas up to add more consumers to the group
   (Kafka automatically rebalances partitions across the larger consumer group,
   increasing parallel processing).
4. Once lag returns to near-zero, identify the root latency added per message (in this
   incident: the synchronous third-party API call) and make it asynchronous or
   batched so a future traffic spike doesn't reproduce the same lag.
5. Add a Grafana alert on consumer lag exceeding a threshold sustained for 5+ minutes,
   rather than relying on customer complaints to surface the problem.

## Related Links
- Runbook: `order-events` topic partition/replica sizing guidelines
- Dashboard: Kafka Consumer Group Lag (Grafana)
