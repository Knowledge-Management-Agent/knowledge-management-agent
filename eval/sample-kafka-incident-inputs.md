# Scratch file — NOT for ingestion

Two separate raw-notes samples to paste into the **Generate documents → Input** box,
after ingesting `eval/corpus/kafka-consumer-lag-kb.md`. Do not upload this file itself.

---

## Sample 1 — paste this for doc_type: RCA Summary

```
Black Friday sale started at 9am, by 9:40am customers started complaining
in support chat that they never got their order confirmation email.
checked and orders were actually going through fine, payment was fine,
just no email. someone noticed the notification service consumer lag
graph was climbing since the sale started. scaled up notification-service
pods from 3 to 8 replicas around 10:15am, lag started dropping, emails
caught up by 10:45am. total delay for affected customers was up to 90
minutes for some early ones.
```

## Sample 2 — paste this for doc_type: SOP

```
we need a standard procedure for whenever someone sees the kafka consumer
lag alert fire. right now people just guess what to do. should cover:
checking if its a real lag issue or a blip, checking if the consumer pods
are resource constrained or its a throughput problem, how to scale up
safely, and who to notify if it's affecting customer-facing stuff like
order emails. this should be something any on-call engineer can follow
even if they've never touched kafka before.
```

Compare each generated draft's citations — both should reference
`kafka-consumer-lag-kb.md` if retrieval is working, since both scenarios are directly
related to it (Sample 1 is a recurrence, Sample 2 is asking to formalize its Resolution
steps into a repeatable procedure).
