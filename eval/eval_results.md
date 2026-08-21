# Eval Results — 2026-08-21

First run of `eval/run_eval.py` against a **real, non-mock provider**. Every
prior run in this project's history used `LLM_PROVIDER=mock` /
`EMBEDDING_PROVIDER=mock`, which only verifies the pipeline is wired up
correctly — it can't say anything about actual answer quality, since the
mock provider returns canned/deterministic output instead of calling a real
model. This is the first result that means anything against the scope doc's
NFR targets.

## Summary

| Metric | Result | Target | Verdict |
|---|---|---|---|
| Retrieval accuracy (top-3) | **100%** (16/16) | ≥ 85% | **PASS** |
| Response grounding (LLM-as-judge) | **93.75%** (15/16) | ≥ 90% | **PASS** |
| p95 end-to-end latency | **6529 ms** | ≤ 8000 ms | **PASS** |

(The live console output at the time rounded grounding to 94% and p95 to
6319ms from a back-to-back run with the same config — both runs are
consistent within LLM noise; the table above uses the run captured with
full per-question detail below.)

## Run configuration

| Setting | Value |
|---|---|
| `LLM_PROVIDER` | `groq` |
| `GROQ_CHAT_MODEL` | `openai/gpt-oss-120b` |
| `EMBEDDING_PROVIDER` | `local` |
| `LOCAL_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, CPU, in-process) |
| `CHUNK_SIZE_TOKENS` / `CHUNK_OVERLAP_TOKENS` | 700 / 100 (defaults, `backend/app/config.py`) |
| `RETRIEVAL_TOP_K` (used by the API) | 5 (default) |
| Vector store | ChromaDB, freshly re-ingested from `eval/corpus/` (12 docs → 63 chunks) |
| Question set | `eval/questions.jsonl`, 16 questions |
| Judge model | same as `LLM_PROVIDER` (Groq `openai/gpt-oss-120b`) — the eval has no separate judge model, it reuses the answering LLM |

Ingested corpus (12 files, 63 chunks):
`api-gateway-incident-rca.md` (7), `database-backup-runbook.md` (4),
`deployment-rollback-runbook.md` (4), `disk-space-alert-kb.md` (5),
`kafka-consumer-lag-kb.md` (5), `kubernetes-pod-crash-kb.md` (5),
`onboarding-new-employee-sop.md` (6), `payment-service-outage-rca.md` (7),
`redis-cache-eviction-kb.md` (5), `ssl-certificate-renewal-runbook.md` (4),
`sso-login-failure-runbook.md` (5), `vpn-access-request-sop.md` (6).

## How each metric is calculated

Source: `eval/run_eval.py`.

### 1. Retrieval accuracy (top-3)

For each question in `questions.jsonl` (which has an `expected_sources`
field, hand-labeled against the corpus):

```python
chunks = retriever.retrieve(q["query"], top_k=3)
retrieved_sources = {c.source for c in chunks}
hit = bool(retrieved_sources & set(q["expected_sources"]))
```

A question counts as a **hit** if *any* of its expected source documents
appears among the top-3 retrieved chunks' source files (set intersection,
not exact match — a question can have multiple acceptable sources).
`retrieval_accuracy = hits / total_questions`.

This only tests the embedding + vector-search step in isolation — it never
looks at the generated answer.

### 2. Response grounding (LLM-as-judge)

```python
result = answer_question(q["query"], top_k=5)          # the real answer, via the RAG pipeline
context = format_context(retriever.retrieve(q["query"], top_k=5))  # re-retrieved top-5, formatted
verdict = llm.generate(
    GROUNDING_JUDGE_TEMPLATE.format(context=context, answer=result["answer"]),
    system=GROUNDING_JUDGE_SYSTEM,
)
grounded = "GROUNDED" in verdict.upper() and "UNGROUNDED" not in verdict.upper()
```

The judge prompt (`backend/app/rag/prompts.py`):

> **System:** You are a strict fact-checking judge. Given a CONTEXT and an
> ANSWER, respond with exactly one word: GROUNDED if every factual claim in
> the answer is supported by the context, or UNGROUNDED if the answer makes
> claims not supported by the context.

This is an **approximation**, not a human-verified guarantee (see
`plan.md` §4) — it's the same LLM used for answering also acting as its own
judge, on a second independent call. `grounding_rate = grounded / total_questions`.

### 3. p95 end-to-end latency

Each question's `answer_question()` call returns `timings_ms.total`
(retrieval + generation, measured server-side in `backend/app/rag/qa.py`).
All 16 latencies are collected and:

```python
p95_latency = statistics.quantiles(latencies, n=20)[18]
```

i.e. the 95th of 20 percentile cut-points (linear interpolation, Python's
default `exclusive` method) — with only 16 samples this is close to just
the 2nd-highest latency, so treat it as directionally correct rather than a
statistically robust p95 (the scope doc's target sample size assumption is
much larger; see `report.md` EVAL-3 caveat about `eval/questions.jsonl`
being on the low end at 16 questions).

## Per-question detail

| # | Query | Retrieval | Grounded | Latency (total) |
|---|---|---|---|---|
| 1 | How do I take a manual backup of the orders database? | OK | yes | 2360 ms |
| 2 | What is the connection limit for the backup_svc database role? | OK | yes | 811 ms |
| 3 | What caused the API gateway 502 errors on 2026-03-11? | OK | yes | 945 ms |
| 4 | How many checkout attempts were affected by the March 2026 API gateway incident? | OK | yes | 941 ms |
| 5 | What access does a new SRE hire get on day 5 of onboarding? | OK | yes | 910 ms |
| 6 | What score do new hires need on the on-call runbook quiz? | OK | yes | 997 ms |
| 7 | Why are orders-api pods stuck in CrashLoopBackOff? | OK | yes | 832 ms |
| 8 | What kubectl command increases the memory limit for orders-api? | OK | yes | 4318 ms |
| 9 | How do I renew the wildcard TLS certificate for internal ops tools? | OK | yes | 5863 ms |
| 10 | What incident motivated the SSL certificate renewal runbook? | OK | yes | 4428 ms |
| 11 | What caused the payment service outage on 2026-01-19? | OK | **no** | 6442 ms |
| 12 | How long was the payment service fully down in January 2026? | OK | yes | 5366 ms |
| 13 | What group is a contractor's VPN account scoped to? | OK | yes | 4244 ms |
| 14 | Why is the session-cache Redis cluster evicting keys at a high rate? | OK | yes | 4229 ms |
| 15 | How do I roll back a bad production deployment? | OK | yes | 5841 ms |
| 16 | Why are log-forwarder nodes hitting critical disk space alerts? | OK | yes | 5745 ms |

Retrieval: 16/16 = 100%. Grounding: 15/16 = 93.75%.
p95 latency (script's `statistics.quantiles(..., n=20)[18]` method): 6529 ms.
Mean latency: 3392 ms · Median: 4236 ms · Min: 811 ms · Max: 6442 ms.

### The one ungrounded case

**Q11 — "What caused the payment service outage on 2026-01-19?"**
Retrieval correctly surfaced `payment-service-outage-rca.md` in the top-3,
but the model answered **"I don't have enough information"** even though
the source document does contain a root cause. The judge then marked this
`UNGROUNDED` — arguably a quirk of the judge prompt (a refusal makes no
unsupported factual claims, so "ungrounded" is a debatable label for it),
but it does correctly flag that the QA step failed to extract an answer
that was actually available in the retrieved context. Worth a manual look
at `payment-service-outage-rca.md`'s formatting/chunking if this recurs.

## Reproducing this run

```bash
cd backend
# .env needs: LLM_PROVIDER=groq, EMBEDDING_PROVIDER=local, GROQ_API_KEY=...
.venv/Scripts/python ../eval/run_eval.py
```

Note: `run_eval.py`'s own docstring says `python -m eval.run_eval` from
`backend/` — that doesn't actually work (`eval/` isn't a subpackage of
`backend/`); run it as a plain script instead, either
`python eval/run_eval.py` from the repo root or `python ../eval/run_eval.py`
from `backend/`. Either way, `.env` is loaded relative to the **current
working directory**, not the script's location — run from `backend/` (or
export `LLM_PROVIDER`/`EMBEDDING_PROVIDER`/`GROQ_API_KEY` etc. as real
environment variables) or it silently falls back to `mock`/`mock` with
near-zero latency and meaningless results, which is what happened on the
first attempt at this run before the CWD issue was caught (see the
suspiciously-fast 2-7ms "latencies" if you ever see that again — that's
the tell).

Uses a local ChromaDB at `CHROMA_PERSIST_DIR` (default `./data/chroma`
relative to CWD) — separate from the live EKS cluster's persisted store,
so running this never touches production data.
