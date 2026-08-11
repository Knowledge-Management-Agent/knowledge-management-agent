# Knowledge Management Agent — Requirements Validation Report

**Date:** 2026-08-11
**Validated against:** [`requirements.md`](./requirements.md)
**Scope of analysis:** `backend/`, `frontend/`, `eval/` as currently committed on `main`

## 1. Executive Summary

The codebase implements a working, locally-runnable RAG pipeline (FastAPI + ChromaDB +
React) that covers **all baseline functional requirements** (FR-1..FR-11) and the
**evaluation harness** (EVAL-1..3) from the original scope doc. Provider-agnostic LLM/
embedding abstractions and a minimal RBAC model are in place and match the plan's
decisions.

The two additions in the updated requirements — **MCP integration (MCP-1..6)** and
**AWS EKS deployment (DEPLOY-1..10)** — have **no implementation yet**. There is no MCP
server code, no Dockerfile/manifest targeting Kubernetes, and no registry/secrets/
ingress configuration anywhere in the repo. These are net-new build items, not gaps in
existing code.

| Category | Requirements | Implemented | Partial | Missing | N/A |
|---|---|---|---|---|---|
| Functional (FR) | 11 | 11 | 0 | 0 | 0 |
| Non-Functional (NFR) | 7 | 4 | 3 | 0 | 0 |
| Architecture (ARCH) | 8 | 7 | 1 | 0 | 0 |
| Security (SEC) | 3 | 3 | 0 | 0 | 0 |
| Evaluation (EVAL) | 3 | 3 | 0 | 0 | 0 |
| **MCP** | 6 | 0 | 0 | 6 | 0 |
| **Deployment/EKS** | 10 | 0 | 2 | 7 | 1 |
| **Total** | **48** | **28 (58%)** | **6 (13%)** | **13 (27%)** | **1 (2%)** |

Bottom line: the RAG/generation core is PoC-complete and evaluable today. MCP exposure
and EKS deployment are the two open workstreams needed to satisfy the updated scope.

---

## 2. Functional Requirements

| REQ-ID | Status | Evidence | Notes |
|---|---|---|---|
| FR-1 Ingest PDF/DOCX/HTML/MD | ✅ Implemented | [backend/app/ingestion/parsers.py](backend/app/ingestion/parsers.py), [backend/app/ingestion/loader.py](backend/app/ingestion/loader.py), [backend/app/api/ingest.py](backend/app/api/ingest.py) | `_SUPPORTED_SUFFIXES` covers pdf/docx/html/htm/md/markdown/txt. |
| FR-2 Semantic retrieval | ✅ Implemented | [backend/app/rag/retriever.py](backend/app/rag/retriever.py) | Embeds query, queries Chroma via cosine similarity. |
| FR-3 Grounded Q&A with citations | ✅ Implemented | [backend/app/rag/qa.py](backend/app/rag/qa.py) | Returns `answer` + deduped `citations` + per-stage `timings_ms`. |
| FR-4..FR-7 Generate runbook/SOP/KB/RCA | ✅ Implemented | [backend/app/rag/generation.py](backend/app/rag/generation.py), [backend/app/rag/prompts.py](backend/app/rag/prompts.py) | `DOC_TYPES = ("runbook", "sop", "kb_article", "rca_summary")`, one system prompt per type — matches Plan §1.4's call for distinct templates. |
| FR-8 Approve & re-ingest | ✅ Implemented | [backend/app/api/generate.py:33-57](backend/app/api/generate.py) | `/generate/approve` writes reviewed content back through `IngestionService`. |
| FR-9 RBAC (viewer/author) | ✅ Implemented | [backend/app/auth/security.py](backend/app/auth/security.py) | `require_role()` dependency gates ingest/generate to `author`. |
| FR-10 Web conversational UI | ✅ Implemented | [frontend/src/components/Chat.jsx](frontend/src/components/Chat.jsx), [frontend/src/App.jsx](frontend/src/App.jsx) | Tabbed UI: Q&A / Generate / Ingest, role-gated tab visibility. |
| FR-11 Ingestion UI | ✅ Implemented | [frontend/src/components/IngestPanel.jsx](frontend/src/components/IngestPanel.jsx) | |

## 3. Non-Functional Requirements

| REQ-ID | Status | Evidence | Notes |
|---|---|---|---|
| NFR-1 ≤8s response | ⚠️ Partial | [backend/app/rag/qa.py:18-24](backend/app/rag/qa.py), [eval/run_eval.py:132-134](eval/run_eval.py) | Instrumented and measured (p95 vs. 8000ms), but actual pass/fail depends on which LLM provider is configured — not yet run against a real (non-mock) provider to confirm. |
| NFR-2 Retrieval accuracy ≥85% top-3 | ⚠️ Partial | [eval/run_eval.py:88-113](eval/run_eval.py) | Methodology implemented and runnable; only 16 questions currently in `eval/questions.jsonl` against 10 corpus docs (target was ~15-30 per Plan §3E — close but on the low end, and result has not been captured/recorded anywhere in-repo). |
| NFR-3 Grounding ≥90% (LLM-judge) | ⚠️ Partial | [eval/run_eval.py:54-61](eval/run_eval.py), [backend/app/rag/prompts.py](backend/app/rag/prompts.py) | Same caveat as NFR-2 — implemented, not yet run-and-recorded with a real LLM provider (mock provider would trivially pass/fail without meaning). |
| NFR-4 English-only | ✅ Implemented (by omission) | [eval/corpus/](eval/corpus) | No language handling exists; corpus and prompts are English-only, consistent with requirement (nothing to build, requirement is a constraint not a feature). |
| NFR-5 Synthetic data, no PII | ✅ Implemented | [eval/corpus/*.md](eval/corpus) | Corpus is synthetic ops runbooks/SOPs/KB articles (e.g., fake hostnames, fake service names) — no evidence of real customer/PII data. |
| NFR-6 Non-production RBAC | ✅ Implemented | [backend/app/auth/security.py:1-6](backend/app/auth/security.py) | Explicitly documented as such in the module docstring; hardcoded demo users via env vars. |
| NFR-7 Provider-agnostic LLM/embedding | ✅ Implemented | [backend/app/llm/factory.py](backend/app/llm/factory.py), [backend/app/llm/base.py](backend/app/llm/base.py) | Adapters for OpenAI, Azure OpenAI, Claude, Gemini, plus offline `mock` — selected via `LLM_PROVIDER`/`EMBEDDING_PROVIDER` env vars. |

## 4. Architecture Components

| REQ-ID | Status | Evidence | Notes |
|---|---|---|---|
| ARCH-1 Web UI | ✅ Implemented | [frontend/src/App.jsx](frontend/src/App.jsx) | |
| ARCH-2 KM API | ✅ Implemented | [backend/app/main.py](backend/app/main.py) | Routers: health, auth, ingest, query, generate. |
| ARCH-3 RAG Pipeline, per-type templates | ✅ Implemented | [backend/app/rag/prompts.py](backend/app/rag/prompts.py) | |
| ARCH-4 Embedding Model (pluggable) | ✅ Implemented | [backend/app/llm/base.py](backend/app/llm/base.py), [backend/app/llm/factory.py](backend/app/llm/factory.py) | |
| ARCH-5 Vector DB (ChromaDB) | ✅ Implemented | [backend/app/rag/store.py](backend/app/rag/store.py) | `PersistentClient` at `CHROMA_PERSIST_DIR`, single collection. |
| ARCH-6 LLM Provider adapters | ✅ Implemented | [backend/app/llm/openai_provider.py](backend/app/llm/openai_provider.py), [claude_provider.py](backend/app/llm/claude_provider.py), [gemini_provider.py](backend/app/llm/gemini_provider.py), [mock_provider.py](backend/app/llm/mock_provider.py) | |
| ARCH-7 Document repo / object storage | ✅ Implemented (PoC scope) | [backend/app/api/ingest.py](backend/app/api/ingest.py) | Local file upload only, per confirmed Plan decision — no SharePoint/Confluence connector (explicitly deferred, not a gap against current requirements). |
| ARCH-8 Monitoring | ⚠️ Partial | [backend/app/main.py:26-38](backend/app/main.py) | Structured request logging (method/path/status/latency) exists; no aggregation of retrieval/generation *quality* signals beyond what `eval/run_eval.py` produces offline. Acceptable for PoC per Plan §1.8, but worth flagging since EKS deployment (DEPLOY-*) will want this wired to cluster-level logging. |

## 5. Security / Access Control

| REQ-ID | Status | Evidence | Notes |
|---|---|---|---|
| SEC-1 JWT sessions | ✅ Implemented | [backend/app/api/auth.py](backend/app/api/auth.py), [backend/app/auth/security.py:42-48](backend/app/auth/security.py) | |
| SEC-2 viewer/author roles | ✅ Implemented | [backend/app/auth/security.py:17-31](backend/app/auth/security.py) | Enforced per-route via `require_role()` dependency on ingest/generate routers; query is viewer+author. |
| SEC-3 No prod-grade controls required (PoC) | ✅ Implemented (as intended) | [backend/.env.example](backend/.env.example) | `JWT_SECRET` default is a placeholder flagged "change-me-in-real-deployment" — appropriate for PoC baseline; becomes a DEPLOY-5 concern for EKS. |

## 6. Evaluation

| REQ-ID | Status | Evidence | Notes |
|---|---|---|---|
| EVAL-1 Synthetic corpus | ✅ Implemented | [eval/corpus/](eval/corpus) | 10 documents (runbooks, RCAs, KB articles, SOPs) — below the 15-30 target range in Plan §3E, though functional. |
| EVAL-2 Question set w/ expected sources | ✅ Implemented | [eval/questions.jsonl](eval/questions.jsonl) | 16 questions, each with `query`, `expected_sources`, `reference_answer`. |
| EVAL-3 Automated harness | ✅ Implemented | [eval/run_eval.py](eval/run_eval.py) | Reports retrieval accuracy, LLM-judge grounding, p95 latency vs. targets; PASS/FAIL per metric. |

---

## 7. MCP Integration — Gap Analysis

**Status: 0/6 implemented — new workstream, no existing code to build on.**

| REQ-ID | Status | Gap |
|---|---|---|
| MCP-1 MCP server exposing core tools | ❌ Missing | No MCP server package, no `mcp` SDK dependency in [backend/requirements.txt](backend/requirements.txt), no tool definitions anywhere in the repo. |
| MCP-2 MCP calls enforce RBAC | ❌ Missing | Cannot be partially satisfied without MCP-1 first. |
| MCP-3 Reuse existing RAG/LLM/store abstractions | ❌ Missing | N/A until MCP-1 exists — but the existing `app/rag`, `app/llm`, `app/ingestion` modules are already structured as importable services independent of the FastAPI layer ([backend/app/rag/qa.py](backend/app/rag/qa.py), [generation.py](backend/app/rag/generation.py) take injectable `retriever`/`llm` args), so this is a **low-risk integration point** — an MCP server can call `answer_question()`, `generate_document()`, `IngestionService.ingest_file()` directly. |
| MCP-4 Externalized MCP config | ❌ Missing | Would extend the existing `Settings` pattern in [backend/app/config.py](backend/app/config.py). |
| MCP-5 Independently containerized | ❌ Missing | No Dockerfile for an MCP server; [docker-compose.yml](docker-compose.yml) has only `backend` and `frontend` services. |
| MCP-6 (stretch) Consume external MCP servers for ingestion | ❌ Missing | Explicitly a stretch goal; no action needed for initial PoC pass. |

**Recommendation:** Build the MCP server as a thin new module (e.g., `backend/app/mcp/server.py`)
using the official `mcp` Python SDK, wrapping the same service functions the REST routers
already call (`answer_question`, `generate_document`, `IngestionService.ingest_file`,
`get_store().list_documents`). This avoids duplicating business logic (satisfies MCP-3
by construction) and keeps the REST API and MCP server as two thin interface layers over
one shared core — the existing code is already factored this way (dependency-injected
`retriever`/`llm`/`store` params throughout), so this is additive, not a refactor.

---

## 8. Deployment / AWS EKS — Gap Analysis

**Status: ~0.5/10 implemented — Docker images exist (local-runtime target), but nothing Kubernetes/EKS-specific.**

| REQ-ID | Status | Gap |
|---|---|---|
| DEPLOY-1 Containers runnable independent of Compose | ⚠️ Partial | [backend/Dockerfile](backend/Dockerfile) and [frontend/Dockerfile](frontend/Dockerfile) build standalone images and don't depend on Compose networking to build — but they've only ever been exercised via `docker-compose.yml`, not deployed standalone; no MCP server image exists at all (see MCP-5). |
| DEPLOY-2 Registry (ECR) push | ❌ Missing | No CI/CD, no ECR repo reference, no image tagging/push scripting anywhere in repo. |
| DEPLOY-3 K8s manifests / Helm chart | ❌ Missing | No `k8s/`, `helm/`, or `manifests/` directory exists. |
| DEPLOY-4 PVC-backed vector store persistence | ❌ Missing | [backend/Dockerfile:10-11](backend/Dockerfile) declares a `VOLUME /data/chroma` (Docker-level only); no PVC/StorageClass definition. Single-pod ChromaDB via `PersistentClient` ([backend/app/rag/store.py:10](backend/app/rag/store.py)) will not tolerate multi-replica backend pods without a shared volume — a real constraint to flag before scaling replicas > 1 on EKS. |
| DEPLOY-5 K8s Secrets / External Secrets | ❌ Missing | Current secret handling is a git-ignored `.env` file consumed via `env_file:` in Compose ([docker-compose.yml:6-7](docker-compose.yml)) — this pattern doesn't transfer to EKS as-is and needs to become K8s Secrets or an External Secrets Operator binding to AWS Secrets Manager. |
| DEPLOY-6 Ingress + TLS | ❌ Missing | No ingress resource, no TLS cert config. |
| DEPLOY-7 Resource requests/limits | ❌ Missing | Cannot exist without DEPLOY-3 manifests. |
| DEPLOY-8 Liveness/readiness probes | ⚠️ Partial | Backend already exposes [`GET /health`](backend/app/api/health.py) returning provider config + indexed chunk count — directly usable as a K8s probe target once a Deployment manifest exists. Frontend (nginx) and MCP server have no equivalent health endpoint yet. |
| DEPLOY-9 Repeatable deployment process | ❌ Missing | No manifests/Helm chart checked in yet (depends on DEPLOY-3). |
| DEPLOY-10 Namespace-scoped, non-HA acceptable | 🔲 N/A (policy, not code) | No action required — this REQ just bounds scope; nothing to validate in code. |

**Recommendation:** Sequence as (a) add a Dockerfile for the MCP server, (b) author a
Helm chart or plain manifests for backend/frontend/MCP-server Deployments + Services +
Ingress, reusing `/health` for probes, (c) decide PVC vs. managed vector DB **before**
setting backend `replicas > 1`, since the current ChromaDB `PersistentClient` is a
single-writer local store — this is the one architectural decision that isn't just
"add a manifest," it affects `app/rag/store.py`.

---

## 9. Prioritized Next Steps

1. **Decide Chroma's EKS story first** (DEPLOY-4) — single-replica PVC-backed pod is
   the low-effort path consistent with the PoC's existing single-process `ChromaStore`;
   only revisit if concurrent-write/multi-replica needs emerge.
2. **Build the MCP server** (MCP-1..5) as a thin wrapper over existing `app/rag` /
   `app/ingestion` services — no core logic changes needed.
3. **Author K8s manifests/Helm chart** (DEPLOY-2, 3, 6, 7, 9) for backend, frontend, and
   the new MCP server; wire `/health` into readiness/liveness probes (DEPLOY-8).
4. **Move secrets out of `.env`** into K8s Secrets or AWS Secrets Manager (DEPLOY-5)
   before first cluster deployment — current `.env` pattern is dev-only by design
   (already git-ignored, per [.gitignore](.gitignore)) and shouldn't be copied into
   cluster config as plain env values without at least K8s Secret indirection.
5. **Run and record one full `eval/run_eval.py` pass against a real (non-mock) LLM
   provider** and commit the output — NFR-1/2/3 are implemented but their PASS/FAIL
   status against real targets isn't yet captured anywhere in the repo.
6. Optionally grow `eval/` corpus from 10 → 15-30 documents to fully match Plan §3E's
   target range (minor, non-blocking).

---

*End of Report*
