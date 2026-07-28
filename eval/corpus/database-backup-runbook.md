# Database Backup Runbook

## Purpose
This runbook describes how to take and verify an on-demand backup of the
`orders-postgres` primary database when the nightly automated backup fails.

## Procedure
1. Connect to the bastion host `bastion-use1-01` via SSH.
2. Run `pg_dump -h orders-db-primary -U backup_svc -Fc orders > orders_manual.dump`.
3. Upload the dump to the `s3://ops-backups/orders/manual/` bucket using the
   `backup-uploader` CLI tool.
4. Verify the backup by restoring it into the `orders-restore-check` scratch
   database and running `SELECT count(*) FROM orders;` — the count must be
   within 1% of the primary database's current row count.
5. Record the backup timestamp and S3 object key in the #ops-backups Slack
   channel.

## Rollback / Failure Handling
If `pg_dump` fails with a connection timeout, check that the
`backup_svc` role has not had its connection limit (currently capped at 5
concurrent connections) exhausted by another job.
