# Knowledge Management Agent — Requirements Validation Report

**Date:** 2026-08-11 (MCP/EKS sections revised same day, branch `feature/mcp-server-eks-deployment`)
**Validated against:** [`requirements.md`](./requirements.md)
**Scope of analysis:** `backend/`, `frontend/`, `eval/`, `k8s/`, `step.md` on branch `feature/mcp-server-eks-deployment` (not yet merged to `main`)

## 1. Executive Summary

The codebase implements a working, locally-runnable RAG pipeline (FastAPI + ChromaDB +
React) that covers **all baseline functional requirements** (FR-1..FR-11) and the
**evaluation harness** (EVAL-1..3) from the original scope doc. Provider-agnostic LLM/
embedding abstractions and a minimal RBAC model are in place and match the plan's
decisions.

The two additions in the updated requirements — **MCP integration (MCP-1..6)** and
**AWS EKS deployment (DEPLOY-1..10)** — are now built: a local stdio MCP server
(`backend/app/mcp/`) and a full set of EKS manifests + runbook (`k8s/`, `step.md`). See
§7–8 for per-requirement status. Caveat that applies to every "Implemented" verdict in
those two sections: this was built and locally validated (Python compiles, YAML
parses) in an environment with no Docker or `kubectl` available — **none of it has been
applied against a live EKS cluster yet**. Treat §7–8 as "code/artifact complete," not
"verified running in AWS."

| Category | Requirements | Implemented | Partial | Missing | N/A |
|---|---|---|---|---|---|
| Functional (FR) | 11 | 11 | 0 | 0 | 0 |
| Non-Functional (NFR) | 7 | 4 | 3 | 0 | 0 |
| Architecture (ARCH) | 8 | 7 | 1 | 0 | 0 |
| Security (SEC) | 3 | 3 | 0 | 0 | 0 |
| Evaluation (EVAL) | 3 | 3 | 0 | 0 | 0 |
| **MCP** | 6 | 4 | 1 | 0 | 1 |
| **Deployment/EKS** | 10 | 6 | 3 | 0 | 1 |
| **Total** | **48** | **38 (79%)** | **8 (17%)** | **0 (0%)** | **2 (4%)** |

Bottom line: the RAG/generation core is PoC-complete and evaluable today. MCP exposure
and EKS deployment now have complete, reviewed artifacts on a feature branch; the
remaining work is executing them against real AWS/EKS infrastructure and merging.

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

**Status: 4/6 implemented, 1 partial (deliberate scope decision), 1 N/A (stretch goal).**

Design decision confirmed with the user: the MCP server runs **locally over stdio only**
(launched by Claude Desktop/Claude Code), not deployed to the cluster. It is a thin REST
client — [backend/app/mcp/client.py](backend/app/mcp/client.py) — that logs into the
same `/auth/login` endpoint the web UI uses and calls `/query`, `/generate`,
`/generate/approve`, `/ingest`, `/ingest/documents` with the resulting bearer token. This
means it inherits RBAC by construction rather than reimplementing it, at the cost of not
satisfying MCP-5's "independently containerized" framing as originally written.

| REQ-ID | Status | Evidence |
|---|---|---|
| MCP-1 MCP server exposing core tools | ✅ Implemented | [backend/app/mcp/server.py](backend/app/mcp/server.py) — `FastMCP` server exposing `query_knowledge_base`, `generate_document`, `ingest_document`, `list_documents`. |
| MCP-2 MCP calls enforce RBAC | ✅ Implemented | [backend/app/mcp/client.py](backend/app/mcp/client.py) — every tool call carries a JWT obtained via `/auth/login`; the REST API's own `require_role()` (unchanged) does the actual enforcement, so there is no separate/weaker auth path to bypass. |
| MCP-3 Reuse existing RAG/LLM/store abstractions | ✅ Implemented | The MCP server has zero imports from `app/rag`, `app/llm`, or `app/ingestion` except the `DOC_TYPES` constant ([backend/app/mcp/server.py](backend/app/mcp/server.py)) — it calls the deployed REST API, so there is no duplicated pipeline logic by construction. |
| MCP-4 Externalized MCP config | ✅ Implemented | [backend/app/mcp/config.py](backend/app/mcp/config.py) reads `KM_API_BASE_URL`, `KM_MCP_USERNAME`/`KM_MCP_PASSWORD` (or `KM_MCP_TOKEN`), `KM_MCP_TIMEOUT_SECONDS` from env; template at [backend/app/mcp/.env.example](backend/app/mcp/.env.example). |
| MCP-5 Independently containerized | ⚠️ Partial — deliberate deviation | Confirmed decision: stdio-only, run locally, not containerized or deployed to EKS. Satisfies MCP-1..4 and is simpler/lower-risk for a PoC, but does not satisfy the literal "independently containerized... deploys as part of the same container pipeline" wording. If a remote/always-on MCP endpoint is needed later, `backend/app/mcp/server.py` can switch `mcp.run()` to `mcp.run(transport="streamable-http")` and gain a Deployment+Service — no logic rewrite needed. |
| MCP-6 (stretch) Consume external MCP servers for ingestion | 🔲 N/A | Explicitly a stretch goal; no action taken, none required for this pass. |

**Verification performed:** ran the backend locally (`backend/.venv`, mock LLM/embedding
providers, `pytest tests/` — 4/4 pass, no regressions from the `pydantic-settings` bump
below) and drove the MCP server as a real subprocess over stdio using the `mcp` SDK's
`ClientSession` (full `initialize()` handshake, not just the underlying HTTP calls):
`list_tools` returned all 4 tools; `ingest_document` → `list_documents` →
`query_knowledge_base` → `generate_document` all completed successfully end-to-end
against a live backend instance with a real ingested document. Separately confirmed
RBAC (MCP-2): a `viewer`-role MCP identity could call `query_knowledge_base` (200) but
got a `403 Forbidden` from `generate_document` — the same `require_role()` check the
REST API always enforced, with no separate/weaker path through MCP. Not yet exercised
through an actual MCP host (Claude Desktop/Code) in this session, only the SDK's client
library directly.

**Note:** this pass also surfaced and fixed a real dependency conflict —
`mcp==1.2.1` requires `pydantic-settings>=2.6.1`, but `backend/requirements.txt` pinned
`==2.5.2` (pre-existing, unrelated to this feature). Bumped to `2.6.1`;
`pip install -r requirements.txt` now resolves cleanly and all existing tests still pass.

---

## 8. Deployment / AWS EKS — Gap Analysis

**Status: 6/10 implemented, 3 partial, 1 N/A — manifests and runbook exist on branch
`feature/mcp-server-eks-deployment`; nothing has been applied to a live cluster yet
(no AWS account/Docker/kubectl available in the environment this was built in).**

| REQ-ID | Status | Evidence |
|---|---|---|
| DEPLOY-1 Containers runnable independent of Compose | ⚠️ Partial | [backend/Dockerfile](backend/Dockerfile)/[frontend/Dockerfile](frontend/Dockerfile) unchanged; `step.md` §4 now documents building and pushing them standalone to ECR. Still not actually run standalone in this session, and MCP server is deliberately excluded from containerization (see MCP-5) — not a gap, a confirmed decision, but it means DEPLOY-1 as literally written ("all services... packaged as container images") isn't fully met by design. |
| DEPLOY-2 Registry (ECR) push | ⚠️ Partial | [step.md](step.md) §4 fully scripts `aws ecr create-repository` + `docker build`/`push`; not executed against a real AWS account in this session. |
| DEPLOY-3 K8s manifests / Helm chart | ✅ Implemented | [k8s/](k8s) — namespace, configmap, secret template, storageclass, PVC, backend/frontend Deployments+Services, Ingress (plain manifests, per confirmed decision — Helm deferred). |
| DEPLOY-4 PVC-backed vector store persistence | ✅ Implemented | [k8s/03-storageclass.yaml](k8s/03-storageclass.yaml) (gp3 via `ebs.csi.aws.com`) + [k8s/04-pvc.yaml](k8s/04-pvc.yaml) (ReadWriteOnce); [k8s/10-backend-deployment.yaml](k8s/10-backend-deployment.yaml) pins `replicas: 1` + `strategy: Recreate` to respect ChromaDB's single-writer `PersistentClient` ([backend/app/rag/store.py](backend/app/rag/store.py)) — do not scale without migrating the store first. Not yet verified against a live cluster (pod restart/reschedule behavior unconfirmed). |
| DEPLOY-5 K8s Secrets / External Secrets | ✅ Implemented | [k8s/02-secret.example.yaml](k8s/02-secret.example.yaml) is a placeholder template only (never applied as-is); `step.md` §5 creates the real Secret imperatively via `kubectl create secret generic` so real values never sit in a committed/local YAML file. Cloud secret-manager integration (External Secrets Operator) explicitly deferred per confirmed decision — plain K8s Secrets judged sufficient for this PoC's security posture (SEC-3). |
| DEPLOY-6 Ingress + TLS | ✅ Implemented | [k8s/30-ingress.yaml](k8s/30-ingress.yaml) — AWS Load Balancer Controller ALB Ingress, ACM certificate ARN annotation, host-based routing (`app.*` / `api.*` since backend routes are unprefixed). Controller install + ACM request steps in `step.md` §3. Not yet applied/verified against a live cluster. |
| DEPLOY-7 Resource requests/limits | ✅ Implemented | Set on both [k8s/10-backend-deployment.yaml](k8s/10-backend-deployment.yaml) and [k8s/20-frontend-deployment.yaml](k8s/20-frontend-deployment.yaml). |
| DEPLOY-8 Liveness/readiness probes | ⚠️ Partial | Backend and frontend Deployments both wire probes (`/health`, `/`); MCP server has none since it's intentionally not deployed to the cluster (see MCP-5) — the original requirement assumed a deployed MCP server. |
| DEPLOY-9 Repeatable deployment process | ✅ Implemented | [step.md](step.md) + [k8s/](k8s) checked into the repo (on the feature branch); covers build → push → cluster add-ons → apply → verify → update → teardown. |
| DEPLOY-10 Namespace-scoped, non-HA acceptable | 🔲 N/A (policy, not code) | Manifests use a single `km-agent` namespace, 1 backend replica, 2 frontend replicas — consistent with this bound; no multi-AZ/DR work attempted. |

**Remaining work, in order:** (1) actually run `step.md` against a real AWS account —
create/confirm the EKS cluster, install the EBS CSI driver and AWS Load Balancer
Controller add-ons, apply the manifests, and confirm the PVC survives a pod restart; (2)
merge `feature/mcp-server-eks-deployment` once verified; (3) if a remote/always-on MCP
endpoint becomes a real requirement, add HTTP transport + a Deployment for it (see MCP-5
note in §7) rather than reworking the REST client.

---

## 9. Prioritized Next Steps

1. **Execute `step.md` against a real AWS account**: create/confirm the EKS cluster,
   install the EBS CSI driver + AWS Load Balancer Controller add-ons, request/validate
   an ACM cert, build+push images to ECR, apply `k8s/`, and confirm `/health` responds
   through the Ingress. Nothing in DEPLOY-2..9 has been verified live yet.
2. **Resolve `git push` access to `Knowledge-Management-Agent/knowledge-management-agent`**
   — the account used in this session got a 403; the MCP server and EKS work are
   committed locally on `feature/mcp-server-eks-deployment` but not pushed. Either grant
   that account write access or push from a fork.
3. **Confirm the PVC survives a pod restart/reschedule** on a live cluster (DEPLOY-4) —
   the manifest is structurally correct (`ReadWriteOnce`, `strategy: Recreate`,
   `replicas: 1`) but this is exactly the kind of thing that's only really proven at
   runtime.
4. **Exercise the MCP server through an actual MCP client** (Claude Desktop or
   `claude mcp add`, per `step.md` §8) rather than just the underlying REST client —
   confirms the stdio protocol handshake and tool schema, not just the HTTP calls
   underneath it.
5. **Run and record one full `eval/run_eval.py` pass against a real (non-mock) LLM
   provider** and commit the output — NFR-1/2/3 are implemented but their PASS/FAIL
   status against real targets isn't yet captured anywhere in the repo.
6. Optionally grow `eval/` corpus from 10 → 15-30 documents to fully match Plan §3E's
   target range (minor, non-blocking).
7. If a remote/always-on MCP endpoint is later required (vs. today's local-stdio-only
   decision), add HTTP transport to `backend/app/mcp/server.py` and a corresponding
   Deployment — see the MCP-5 note in §7.

---

*End of Report*
