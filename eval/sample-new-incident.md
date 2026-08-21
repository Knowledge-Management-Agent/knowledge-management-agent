# Scratch file — NOT for ingestion

This is raw, unpolished incident notes meant to be **pasted into the "Input" box on
the Generate Documents tab** (doc_type: RCA Summary), to test whether generation
grounds itself in an already-ingested related document
(`eval/corpus/payment-service-outage-rca.md`). Do not upload this file itself via
Ingest — it's intentionally messy, not a finished KB document.

---

checkout started failing today around 2:15pm UTC, payment-service pods
crashlooping. turned out someone rotated the db password again and the
same sync job broke silently, exact same issue as last time. fixed by
restarting the sync job manually and bouncing the pods, back up by 2:30pm.
about 15 min of downtime this time. on-call this time was different
engineer than last time, didn't know about the january incident until
someone mentioned it in the incident channel.
