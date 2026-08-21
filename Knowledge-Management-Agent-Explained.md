# Knowledge Management Agent — Complete Explanation

A from-scratch-to-advanced walkthrough of what this project is, every technology it
uses, and how they all fit together. Written so you can read top to bottom as a learning
document, or jump to any section as a reference.

---

## 1. The one-paragraph version

You have a pile of documents (runbooks, incident reports, support tickets, wiki pages).
Normally, finding the right one means keyword-searching and hoping, or bugging a senior
engineer who "just knows." This project is a system that (a) reads all your documents
and understands their *meaning*, not just their words, (b) lets you ask plain-English
questions and get answers with citations back to the real source documents, and (c) can
also *write* new documents (runbooks, SOPs, KB articles, incident summaries) for you,
grounded in what it already knows. It's exposed both as a web app and as a set of tools
an AI agent (like Claude) can call directly.

---

## 2. The problem, and why it's harder than it sounds

Keyword search fails when the words don't match: someone asks "why is the site slow"
but the runbook is titled "Redis Cache Eviction Remediation" — no shared keywords, but
obviously related. You need something that understands *meaning*.

Also: you cannot just hand a general-purpose AI chatbot your internal documents and ask
it questions, because:
- It's never seen your internal docs (they're not on the public internet)
- If you paste all your docs into every question, you'd blow past the AI's input-size
  limits and pay a fortune
- The AI might confidently make things up ("hallucinate") if it doesn't actually know

The fix for all three is the architecture this project implements: **RAG**.

---

## 3. Core concept #1 — What is an LLM?

**Simple:** An LLM (Large Language Model) is a program that's very good at predicting
"what text should come next," trained on huge amounts of text. Give it a prompt, it
generates a plausible, fluent continuation. That's it — that's the whole trick, just
executed at a scale that makes it look like reasoning/understanding.

**Deeper:** It's a neural network (specifically a Transformer) with billions of
parameters, trained to predict the next word (technically "token") over and over across
essentially the entire internet plus curated data. It has no built-in memory of your
specific documents, no database, no real-time information — only whatever patterns got
baked into its weights during training, plus whatever text you put directly in its
prompt ("context window"). Everything it "knows" for a specific task has to either
already be in its training data, or be handed to it in the prompt. That second option —
handing it the right information at the right time — is exactly what RAG does.

**In this project:** the LLM is swappable (a deliberate architectural choice —
"provider-agnostic"). It currently uses **Groq**, a provider that runs open-source
models (like Llama, GPT-OSS) extremely fast on custom chips. The code
(`backend/app/llm/groq_provider.py`) talks to it via an OpenAI-compatible API — Groq
deliberately mimics OpenAI's request/response format so existing tooling works
unmodified. Other supported providers, selectable via one config value
(`LLM_PROVIDER`): OpenAI, Azure OpenAI, Anthropic (Claude), Google (Gemini), or a `mock`
provider that returns canned text for offline testing.

---

## 4. Core concept #2 — What is an embedding?

**Simple:** An embedding turns a piece of text into a list of numbers (a vector) that
captures its *meaning*. Texts with similar meaning end up as vectors that are
mathematically close together, even if they don't share a single word.

**Deeper:** An embedding model is a (usually much smaller) neural network trained
specifically to produce these vectors — typically a few hundred to a couple thousand
numbers per piece of text. "Closeness" is measured with something like **cosine
similarity** (the angle between two vectors — smaller angle = more similar meaning).
This is what lets "why is the site slow" and "Redis Cache Eviction" end up near each
other in this number-space, because they're topically related, even with zero
overlapping words.

**In this project:** the embedding model is also swappable
(`EMBEDDING_PROVIDER`). It currently uses a **local, open-source model**
(`sentence-transformers/all-MiniLM-L6-v2`, via the `sentence-transformers` Python
library) that runs entirely in-process on CPU — no API key, no external network call, no
per-request cost, no rate limit (`backend/app/llm/local_provider.py`). Other options:
OpenAI's or Google's hosted embedding APIs. Note Groq itself has no embeddings API at
all (it's chat-only) — which is exactly why this project pairs Groq (LLM) with a
*separate* local embedding provider; LLM and embedding provider are independent knobs.

---

## 5. Core concept #3 — What is a vector database?

**Simple:** A normal database is great at "find the row where `id = 42`." A vector
database is built for a different question: "find the N stored items whose vector is
*closest* to this query vector" — i.e., semantic nearest-neighbor search, at speed, over
potentially millions of items.

**Deeper:** Under the hood these typically use an approximate-nearest-neighbor index
(e.g. HNSW — Hierarchical Navigable Small World graphs) so a similarity search doesn't
require comparing your query against every single stored vector one by one, which would
be too slow at scale.

**In this project:** the vector database is **ChromaDB**, running as an embedded,
self-hosted store (no separate server process to manage) — chosen for a PoC specifically
because it's the lowest-ops-overhead option (vs. e.g. Pinecone, a hosted commercial
service, or FAISS, a lower-level library without built-in metadata storage).
`backend/app/rag/store.py` wraps it: `chromadb.PersistentClient` writes to disk (so data
survives restarts), with `hnsw:space: cosine` configuring cosine similarity as the
distance metric. One important real-world constraint this creates: ChromaDB's
`PersistentClient` is a **single-writer** store — only one process can safely write to
it at a time, which is why the backend is deliberately capped at 1 replica when deployed
(see §11).

---

## 6. Core concept #4 — What is RAG (Retrieval-Augmented Generation)?

**Simple:** Instead of asking the LLM to answer purely from what it memorized during
training, you first *retrieve* the most relevant snippets from your own documents, then
hand those snippets to the LLM along with the question, and say "answer using only
this." The LLM's job shrinks from "know everything" to "read this specific evidence and
summarize/reason over it" — which it's much better and more honest at.

**Deeper — the two phases:**

**Phase A — Ingestion (happens once per document, ahead of time):**
1. **Parse**: extract raw text from a PDF/DOCX/HTML/Markdown file
   (`backend/app/ingestion/parsers.py`)
2. **Chunk**: split the text into smaller pieces (`backend/app/ingestion/chunker.py`).
   This project uses *structure-aware* chunking: if the document has Markdown/HTML-style
   `#` headings, it splits along those section boundaries first (so a chunk is a
   coherent section, not an arbitrary slice); if a section is still too long, or there
   are no headings at all (e.g. a PDF body), it falls back to fixed-size word windows
   (~700 words) with ~100 words of overlap between consecutive windows, so an idea that
   spans a chunk boundary isn't completely lost on either side.
3. **Embed**: run each chunk through the embedding model to get its vector.
4. **Store**: save `(chunk text, its vector, metadata like source filename/section)` into
   ChromaDB.

**Phase B — Query (happens per user question, in real time):**
1. Embed the *question* using the same embedding model (critical — query and documents
   must live in the same vector space to be comparable).
2. Ask ChromaDB for the top-K closest chunks by cosine similarity (K=5 by default,
   `RETRIEVAL_TOP_K`).
3. Build a prompt: system instructions + the retrieved chunks (labeled with their
   source) + the user's question.
4. Send that prompt to the LLM.
5. Return the LLM's answer *plus* the list of source documents actually used, so the
   user can verify/click through — this is the "citations" feature
   (`backend/app/rag/qa.py`).

The system prompt used here (`backend/app/rag/prompts.py`) is explicit: *"Answer the
user's question using ONLY the provided CONTEXT... if the context does not contain the
answer, say you don't have enough information — do not make anything up."* That
instruction is the actual anti-hallucination mechanism — it doesn't eliminate the risk
entirely, but it constrains the LLM to a much narrower, checkable task.

---

## 7. What is MCP (Model Context Protocol), and how is it used here?

**Simple:** Normally, to use this Knowledge Management Agent, a human opens a web page,
clicks around, types questions into a chat box. MCP is a standard that lets an *AI agent*
(like Claude) use the same capabilities directly, as callable "tools," without a human
driving a browser — so Claude itself can look things up in your knowledge base, or file
a new runbook, as part of a larger conversation or workflow.

**Deeper:** MCP is an open protocol (originated by Anthropic, now broadly adopted) for
connecting AI models to external tools and data sources in a standardized way — instead
of every app inventing its own bespoke "how do I let an AI call my API" integration, MCP
defines one consistent shape: an **MCP server** exposes a list of **tools** (each with a
name, description, and typed input schema); an **MCP client** (the AI agent host —
Claude Desktop, Claude Code, etc.) discovers those tools and can invoke them mid-conversation,
with the AI model deciding *when* to call which tool based on the user's request.

**In this project** (`backend/app/mcp/server.py`): a small MCP server exposes exactly 4
tools, mapping directly onto the app's core capabilities:
- `query_knowledge_base(question, top_k)` — runs the RAG query flow above
- `generate_document(doc_type, input_text, use_retrieval)` — generates a runbook/SOP/KB
  article/RCA summary (§8)
- `ingest_document(file_path)` — parses/chunks/embeds/stores a local file
- `list_documents()` — lists what's currently indexed

**How it actually works, mechanically:** the MCP server does *not* talk to ChromaDB or
the LLM directly. It's a thin wrapper that logs into the deployed REST API (same
`/auth/login` endpoint the web UI uses) and calls the same `/query`, `/generate`,
`/ingest`, `/ingest/documents` HTTP endpoints, using a real JWT token. This was a
deliberate design choice: it means the MCP server automatically inherits the exact same
role-based access control (viewer vs. author) as the web app — there's no separate,
possibly-weaker authorization path to accidentally leave open. It runs locally on your
machine over **stdio** (standard input/output — the simplest possible transport,
literally just piping text between two processes), launched directly by Claude
Desktop/Claude Code (`step.md` §8 has the exact registration commands) — it is
*not* deployed to the Kubernetes cluster; it's a client-side tool, not a server-side
service.

---

## 8. What is a "runbook"? And SOPs, KB articles, RCA summaries?

These are the four types of operational documents this project can *generate*, each with
its own prompt template and expected structure (`backend/app/rag/prompts.py`):

- **Runbook** — a step-by-step procedure an on-call engineer follows *during* an
  incident, under time pressure. Example: "Redis eviction rate is high → here are the
  exact commands to check, and the exact steps to fix it." Generated as numbered,
  actionable steps, nothing invented that isn't grounded in retrieved context.

- **SOP (Standard Operating Procedure)** — a more general, formal procedure for routine
  (not necessarily urgent) work, following a fixed structure: *Purpose, Scope,
  Prerequisites, Procedure, Rollback/Exceptions*. Example: "how to onboard a new
  employee's AWS access."

- **KB (Knowledge Base) article** — written *after* a support ticket or troubleshooting
  session, so the next person who hits the same problem doesn't have to rediscover the
  fix. Structure: *Title, Symptoms, Cause, Resolution, Related Links*.

- **RCA (Root Cause Analysis) summary** — written *after* an incident, structured as:
  *Incident Summary, Timeline, Root Cause, Impact, Remediation, Lessons Learned*. This is
  the formal "what happened, why, and what are we changing" document orgs use for
  postmortems.

All four go through the **same retrieval step** as Q&A (pull relevant existing docs from
the knowledge base first) before applying their specific prompt template — so a
generated RCA summary, for instance, can reference and stay consistent with an existing
related runbook, rather than being written in a vacuum.

There's also a **write-back loop**: once a human reviews and approves a generated
document, it can be pushed back through the same ingestion pipeline (`/generate/approve`
in `backend/app/api/generate.py`) so it becomes part of the searchable knowledge base
itself — closing the loop from "lessons learned" back into "things the system can now
retrieve and cite."

---

## 9. Putting it together — this project's architecture

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────────────────┐
│   Web UI      │────▶│  FastAPI backend  │────▶│  RAG pipeline                 │
│  (React)      │◀────│  (REST API)       │◀────│  retriever + prompts + LLM    │
└──────────────┘     └──────────────────┘     └──────────────┬────────────────┘
                              ▲                                │
                              │ same REST API                  ▼
                     ┌──────────────────┐             ┌─────────────────┐
                     │   MCP server      │             │   ChromaDB       │
                     │  (local, stdio)    │             │  (vector store)  │
                     │  used by Claude    │             └─────────────────┘
                     └──────────────────┘                      ▲
                                                                 │ embeds
                                                        ┌─────────────────┐
                                                        │ Embedding model  │
                                                        │ (local, CPU)     │
                                                        └─────────────────┘
                              LLM calls go to:
                     ┌──────────────────┐
                     │  Groq (chat API)  │
                     └──────────────────┘
```

**Backend** (`backend/`, Python/FastAPI): the API layer. Routers for `/auth`, `/query`,
`/generate`, `/ingest`, `/health`. Internally organized so the actual logic (`app/rag/`,
`app/llm/`, `app/ingestion/`) doesn't know or care whether it's being called from a REST
route or the MCP server — both are thin interfaces over the same core functions.

**Frontend** (`frontend/`, React + Vite, served via nginx in production): tabs for Q&A
(chat-style), Generate (form per document type), and Ingest (file upload), gated by role.

**Auth/RBAC**: JWT-based sessions, two roles — `viewer` (Q&A only) and `author` (Q&A +
generate + ingest + approve). Explicitly documented as non-production-grade (demo
users/passwords via env vars, not real SSO/IAM) — appropriate for a PoC, not for handling
real sensitive data as-is.

**Evaluation harness** (`eval/`): a curated set of synthetic test documents
(`eval/corpus/`) and questions with known-correct sources (`eval/questions.jsonl`), plus
`eval/run_eval.py` which measures: retrieval accuracy (is the right doc in the top-3
results?), grounding (does an LLM-as-judge agree the answer is actually supported by the
retrieved context?), and latency — checked against the project's target metrics (≥85%
retrieval accuracy, ≥90% grounding, ≤8s response time).

---

## 10. A full example, end to end

Say you ingest `redis-cache-eviction-kb.md`, then ask "why do users get logged out
randomly?"

1. **Ingestion** (happened earlier): the file gets parsed to plain text, split into ~5
   chunks along its `##` section headings (Symptoms, Cause, Resolution, etc.), each
   chunk embedded into a vector, all 5 stored in ChromaDB tagged with
   `source=redis-cache-eviction-kb.md`.
2. **You ask the question** (via web UI, or an MCP tool call from Claude): the backend
   embeds *your question* with the same embedding model.
3. **Retrieval**: ChromaDB compares your question's vector against every stored chunk's
   vector, returns the 5 closest. The "Symptoms" chunk (which literally says "users
   report being logged out unexpectedly") is almost certainly one of the top hits, even
   though your question didn't use the word "Redis" at all.
4. **Prompt assembly**: those chunks get formatted with source labels and stuffed into a
   template along with your question.
5. **Generation**: Groq's LLM reads that prompt and writes an answer, instructed to stick
   only to what's in the retrieved chunks.
6. **Response**: you get back the answer text, a de-duplicated list of citations (which
   source documents/sections were actually used), and timing info (how long retrieval
   vs. generation took) — all in `backend/app/rag/qa.py`'s response shape.

If you'd instead asked Claude Code/Desktop (with the MCP server registered) "what does
our KB say about users getting logged out," Claude would recognize this matches the
`query_knowledge_base` tool, call it with your question, get back that same JSON, and
weave the answer + citations into its own reply — same underlying pipeline, different
front door.

---

## 11. Deployment — where all of this actually runs

(Covered in depth already in `step.md`/`report.md` — summarized here for completeness.)

- **Kubernetes on AWS EKS**: the backend and frontend run as separate Deployments in a
  `km-agent` namespace. The backend is pinned to **1 replica** specifically because of
  ChromaDB's single-writer constraint (§5) — scaling it would require first migrating to
  a proper multi-writer/clustered vector database.
- **Terraform** (`terraform/`) provisions the actual cloud infrastructure: VPC, the EKS
  cluster itself, the worker node group, IAM roles, the EBS CSI driver (so a
  PersistentVolume can back ChromaDB's on-disk data, surviving pod restarts), the AWS
  Load Balancer Controller, and the two ECR (container registry) repos.
- **CI/CD** (`.github/workflows/`): two manually-triggered GitHub Actions pipelines —
  one to apply/destroy the Terraform infrastructure, one to build+push Docker images and
  deploy/smoke-test the app — both authenticate to AWS via OIDC (no long-lived AWS keys
  stored in GitHub).
- **MCP server**: deliberately *not* deployed to the cluster — it runs locally on
  whoever's machine has Claude Desktop/Code open, calling the deployed backend over the
  network (§7).

---

## 12. Glossary (quick reference)

| Term | Plain-English meaning |
|---|---|
| **LLM** | A model that generates fluent text by predicting what comes next; the "brain" that writes answers/documents. |
| **RAG** | Retrieval-Augmented Generation — look up relevant facts first, then have the LLM answer *using* those facts, instead of relying purely on what it memorized. |
| **Embedding** | A list of numbers representing a piece of text's *meaning*, so similar meanings end up as similar numbers. |
| **Vector database** | A database built to quickly find "the stored items whose embedding is closest to this one" — how semantic search works. |
| **Chunking** | Splitting a long document into smaller pieces before embedding, since you retrieve/cite at the chunk level, not the whole-document level. |
| **Cosine similarity** | The specific math (angle between two vectors) used to measure how "close" two embeddings are. |
| **MCP** | Model Context Protocol — a standard way for AI agents to call external tools/data sources, instead of every integration being bespoke. |
| **MCP server / tool / client** | Server = exposes capabilities as callable tools; tool = one specific callable action (e.g. `query_knowledge_base`); client = the AI agent host (e.g. Claude Code) that discovers and calls those tools. |
| **JWT** | JSON Web Token — a signed token proving "this user logged in and has this role," used for auth without a server-side session store. |
| **RBAC** | Role-Based Access Control — permissions based on a user's role (here: `viewer` vs `author`). |
| **Grounding** | Whether an AI's answer is actually supported by the retrieved source material, vs. made up. |
| **Hallucination** | When an LLM confidently states something false/unsupported. RAG + grounding instructions are the main defenses against it here. |
| **Runbook / SOP / KB article / RCA** | The four generated document types — see §8. |
