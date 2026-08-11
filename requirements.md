# Knowledge Management Agent — Consolidated Requirements

**Status:** Draft for Review | **Supersedes:** scoping intent of `Knowledge-Management-Agent-PoC.md` (kept as-is for historical reference)
**Purpose:** Single traceable requirements baseline, each item tagged with a REQ-ID, used by `report.md` to validate the current codebase and identify gaps.

This document consolidates the original scope doc with two additions the original scope
doc left open-ended and that have since been confirmed as required for this PoC:

1. **MCP (Model Context Protocol) integration** — the KM Agent's capabilities must be
   reachable as MCP tools, not only as a REST API.
2. **Deployment target is AWS EKS**, not generic "Docker/Kubernetes/PaaS" — the original
   doc's §6 listed Kubernetes as one option among several; this is now the committed
   target environment for the PoC's end state.

---

## 1. Functional Requirements

| REQ-ID | Requirement | Source |
|---|---|---|
| FR-1 | Ingest documents in PDF, DOCX, HTML, and Markdown formats: parse, chunk, embed, store. | Scope §4 |
| FR-2 | Retrieve relevant chunks by semantic similarity search over the embedded corpus. | Scope §4 |
| FR-3 | Answer natural-language questions with responses grounded in retrieved chunks, including source citations. | Scope §4 |
| FR-4 | Generate runbooks from raw operational input, using retrieval-grounded context. | Scope §2, §4 |
| FR-5 | Generate SOPs from raw operational input, using retrieval-grounded context. | Scope §2, §4 |
| FR-6 | Generate KB articles from support/troubleshooting input, using retrieval-grounded context. | Scope §2, §4 |
| FR-7 | Generate structured RCA summaries from incident input, using retrieval-grounded context. | Scope §2, §4 |
| FR-8 | Provide a write-back ("approve & re-ingest") path so a reviewed generated document re-enters the corpus. | Scope §2 (implied), Plan §1.5 |
| FR-9 | Enforce role-based access control distinguishing at minimum a viewer role (Q&A only) and an author role (Q&A + generation + ingestion). | Scope §4 |
| FR-10 | Provide a web-based conversational interface for querying and reviewing generated documents. | Scope §1 |
| FR-11 | Provide a document ingestion/upload interface for adding source material. | Scope §1 |

## 2. Non-Functional Requirements

| REQ-ID | Requirement | Source |
|---|---|---|
| NFR-1 | End-to-end query response time ≤ 8 seconds. | Scope §3, §5 |
| NFR-2 | Retrieval accuracy: expected source document appears in top-3 results ≥ 85%, measured against a labeled eval set. | Scope §3 |
| NFR-3 | Response grounding: generated answers supported by retrieved source ≥ 90%, measured via a defined methodology (human or LLM-as-judge). | Scope §3 |
| NFR-4 | English-language content only. | Scope §5 |
| NFR-5 | Non-production/synthetic data only; no PII. | Scope §5 |
| NFR-6 | RBAC is non-production grade — no enterprise IAM/SSO integration required for the PoC. | Scope §1, §5 |
| NFR-7 | LLM and embedding providers must be swappable via configuration, not hardcoded (provider-agnostic abstraction). | Scope §6 (tech stack lists 4 LLM options) |

## 3. Architecture Components

| REQ-ID | Requirement | Source |
|---|---|---|
| ARCH-1 | Web UI — captures queries, displays answers with citations, provides generation forms. | Scope §7 |
| ARCH-2 | Knowledge Management API — routes requests to retrieval or generation flows. | Scope §7 |
| ARCH-3 | RAG Pipeline — coordinates embedding, retrieval, and prompt assembly, with distinct templates per generation type (not one generic prompt). | Scope §7, Plan §1.4 |
| ARCH-4 | Embedding Model — pluggable interface, converts documents/queries to vectors. | Scope §7 |
| ARCH-5 | Vector Database — stores embeddings, returns top-matching chunks (ChromaDB per Plan decision). | Scope §7, Plan (confirmed decision) |
| ARCH-6 | LLM Provider — generates grounded answers and draft documents behind a swappable adapter interface. | Scope §7 |
| ARCH-7 | Document Repository / Object Storage — source and generated document storage (local file upload for PoC; no live SharePoint/Confluence). | Scope §7, Plan (confirmed decision) |
| ARCH-8 | Monitoring — structured logging of usage, latency, and retrieval/generation quality (PoC-level, not a full observability stack). | Scope §7, Plan §1.8 |

## 4. Authentication & Access Control

| REQ-ID | Requirement | Source |
|---|---|---|
| SEC-1 | JWT-based session issuance for demo users. | Scope §6 |
| SEC-2 | Two-role model: `viewer` (query only) and `author` (query + generate + ingest + approve/re-ingest). | Plan §1.6 |
| SEC-3 | No production-grade security controls (encryption at rest, secret rotation, audit logging) required for the PoC baseline — see DEPLOY-* for what EKS deployment adds on top of this. | Scope §9 |

## 5. Evaluation

| REQ-ID | Requirement | Source |
|---|---|---|
| EVAL-1 | Curated synthetic evaluation corpus (~15-30 documents) covering varied topics/formats. | Plan §3 Phase E |
| EVAL-2 | Curated question set mapping each query to expected source document(s). | Plan §3 Phase E |
| EVAL-3 | Automated evaluation harness reporting retrieval accuracy, grounding rate, and latency against NFR-1/2/3 targets. | Plan §3 Phase E |

## 6. MCP (Model Context Protocol) Integration — *new requirement*

The original scope doc only specified a REST API consumed by the web UI. This PoC must
additionally expose its capabilities via MCP so that MCP-capable clients (Claude Code,
Claude Desktop, other agent hosts) can invoke the Knowledge Management Agent as a set of
tools, and so the agent can be composed into broader agentic workflows without a
browser in the loop.

| REQ-ID | Requirement |
|---|---|
| MCP-1 | Provide an MCP server (local, stdio and/or HTTP transport) exposing the KM Agent's core capabilities as MCP tools: `query_knowledge_base`, `generate_document` (per doc type), `ingest_document`, `list_documents`. |
| MCP-2 | MCP tool calls must enforce the same RBAC model as the REST API (SEC-2) — no unauthenticated bypass of author-only actions. |
| MCP-3 | MCP server must reuse the existing RAG/LLM/store abstractions (`app/rag`, `app/llm`, `app/ingestion`) rather than duplicating pipeline logic — it is a new transport/interface layer, not a parallel implementation. |
| MCP-4 | MCP server configuration (transport, auth token, backend API base URL) must be externalized via environment variables, consistent with existing `Settings` config pattern. |
| MCP-5 | MCP server must be independently containerized (or included in the backend image) so it deploys as part of the same container pipeline as the rest of the stack (see DEPLOY-*). |
| MCP-6 | *(Stretch/future)* Support consuming external MCP servers (e.g., a filesystem or document-repository connector) as an ingestion source, as an alternative to direct file upload — natural extension of Scope §1's SharePoint/Confluence intent. |

## 7. Deployment — AWS EKS *(updated target)*

The original scope doc (§6) listed "Docker, Kubernetes, or cloud PaaS" as open options,
and the implementation plan (`plan.md`) narrowed the PoC to local Docker Compose. The
committed end-state deployment target for this PoC is now **AWS EKS**, replacing Compose
as the target runtime (Compose may remain for local dev only).

| REQ-ID | Requirement |
|---|---|
| DEPLOY-1 | All services (backend API, frontend, MCP server) are packaged as container images buildable and runnable independently of Docker Compose. |
| DEPLOY-2 | Container images are pushed to a registry reachable from EKS (e.g., Amazon ECR). |
| DEPLOY-3 | Kubernetes manifests or a Helm chart define Deployments, Services, and Ingress for backend, frontend, and MCP server. |
| DEPLOY-4 | Vector store persistence (ChromaDB data) survives pod restarts/rescheduling via a PersistentVolumeClaim backed by an EKS-compatible StorageClass (e.g., EBS CSI driver), or the store is migrated to a managed/clustered vector DB if PVC-backed single-pod Chroma proves insufficient. |
| DEPLOY-5 | Secrets (LLM provider API keys, JWT secret) are managed via Kubernetes Secrets (or AWS Secrets Manager / External Secrets Operator), not baked into images or committed `.env` files. |
| DEPLOY-6 | Ingress/networking exposes the frontend and API within the cluster's existing ingress/load-balancer pattern, with TLS termination. |
| DEPLOY-7 | Resource requests/limits are defined per Deployment so the PoC does not starve or overrun shared cluster capacity. |
| DEPLOY-8 | Basic liveness/readiness probes exist for backend and MCP server (backend already has a `/health` endpoint per ARCH-2 to build on). |
| DEPLOY-9 | Deployment documented as a repeatable process (manifests/Helm chart checked into the repo, not applied ad hoc). |
| DEPLOY-10 | *(PoC-level, not HA)* Namespace-scoped deployment is sufficient — multi-AZ HA, autoscaling policy tuning, and DR remain out of scope per the original Scope §1 "Out of Scope" (production deployment concerns), consistent with this being a PoC on a shared/non-production EKS cluster. |

## 8. Out of Scope (carried forward)

- Fine-tuning of LLMs or embedding models
- Multi-language support
- Multi-agent orchestration
- ITSM tool automation (ticket creation, updates, closure)
- Live integration with production systems or production data
- Enterprise IAM/SSO integration and formal security accreditation
- Production-grade HA/DR for the EKS deployment (see DEPLOY-10)

---

*End of Document*
