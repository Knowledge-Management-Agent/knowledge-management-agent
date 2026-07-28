# Knowledge Management Agent PoC — Implementation Plan

## Context

`Knowledge-Management-Agent-PoC.md` is a scope/architecture document for a RAG-based
knowledge management agent (generates runbooks/SOPs/KB articles/RCA summaries, answers
questions over an ingested document corpus). The repo currently contains **only this
scope doc and two unrelated stray notes files** — there is no code yet. This is a
greenfield PoC.

The doc is solid as a scoping artifact but is written at a level where several
technology and process choices are left as open menus ("OpenAI, Azure OpenAI, Claude,
or Gemini", "ChromaDB, FAISS, Pinecone, or Weaviate", "SharePoint and/or Confluence").
That's fine for a proposal doc, but not enough to start building from. This plan pins
down those choices (confirmed with the user below), flags what's missing or
inconsistent in the doc itself, and lays out a concrete build workflow.

**Decisions confirmed with the user:**
- LLM provider: **provider-agnostic** — build behind a thin abstraction so the backing
  model can be swapped (OpenAI/Azure/Claude/Gemini) without touching pipeline logic.
- Vector DB: **ChromaDB** (self-hosted, embedded/local server, lowest ops overhead for a PoC).
- Document source: **local file upload** for the PoC — no live SharePoint/Confluence
  integration yet; ingest sample PDF/DOCX/HTML/Markdown files directly.
- Deployment: **local Docker Compose**.
- Generation scope: **all 4 generation types (runbooks, SOPs, KB articles, RCA summaries)
  + RAG Q&A**, built together rather than phased.
- Evaluation set: **build it as part of this PoC** — curate a synthetic test corpus and
  question set with known-correct answers/sources.

---

## 1. Problems / Gaps Found in the Scope Doc

Flag these back to the doc owner — some are fine to leave as-is for a scope doc, but
each needs a concrete answer before/while building:

1. **No chunking strategy specified.** Chunk size, overlap, and splitting method
   (fixed-token vs. structure-aware/semantic) directly determine retrieval quality.
   Not mentioned anywhere in §4/§8. → Plan picks a starting strategy (below), tunable
   during eval.

2. **Success metrics have no measurement methodology.** "Retrieval accuracy ≥85% in
   top-3" and "grounding ≥90%" are unmeasurable without a labeled eval set (query →
   expected source doc, and a way to judge grounding — human or LLM-as-judge). The doc
   states targets but never describes how they'll be computed. → Addressed in §4 below.

3. **No re-ingestion / update strategy.** If a source document changes, is it
   re-chunked and re-embedded wholesale, or incrementally? Not addressed. Out of scope
   for this PoC given local-file-upload ingestion, but worth a one-line note in the doc.

4. **Generation vs. retrieval are conflated in the architecture diagram.** §7 shows one
   RAG Pipeline feeding both Q&A and document generation, but generation (runbooks,
   SOPs, KB articles, RCA summaries) needs distinct prompt templates and output
   structures per type — this isn't a single "answer with citations" flow. The doc
   doesn't call this out. → Plan treats generation as parallel prompt-template flows
   that reuse the same retrieval step, not one generic prompt.

5. **"Lessons learned...feed back into runbooks/SOPs" (§2) has no supporting
   architecture.** This implies a write-back path (generated/edited content re-entering
   the corpus) that isn't reflected in §7's diagram or §8's workflow, which are both
   one-directional (ingest → query → answer). → Plan adds a minimal "approve & re-ingest"
   loop.

6. **RBAC is listed as a functional requirement (§4) but "non-production grade" (§1) is
   never defined.** What roles exist? What do they gate — document visibility,
   generation actions, or both? → Plan defines a minimal 2-role model (viewer/author)
   scoped to what's buildable in a PoC.

7. **No conversation/session model.** The Web UI is described as accepting "queries"
   (§7) with no mention of multi-turn chat history, yet a "conversational interface"
   (§1) implies follow-up questions need context. → Plan scopes this explicitly (single
   session, no persistent multi-user history) rather than leaving it implicit.

8. **Monitoring (§7) is a box with no detail.** "Logs usage, latency, and
   retrieval/generation quality" — no tool named. For a PoC this can be simple
   structured logging; calling it "Monitoring" in the architecture diagram overstates it.

9. **No document volume / scale assumption.** Affects nothing about correctness, but
   without even a rough number ("~20-50 docs for PoC") it's hard to size Chroma config
   or ingestion pipeline batch behavior. → Plan assumes small corpus (matches the
   eval-set decision above: ~15-30 curated docs).

None of these block starting the PoC — they're addressed with concrete defaults in the
plan below — but worth surfacing to whoever owns the doc since a couple (RBAC scope,
the write-back loop) affect the "Functional Requirements" section's completeness.

---

## 2. Proposed Repo Structure

```
PoC-Project/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app entrypoint
│   │   ├── api/                     # routers: ingest, query, generate, health
│   │   ├── ingestion/               # parsers, chunker, embedder, loader
│   │   ├── rag/                     # retriever, prompt assembly, generation templates
│   │   ├── llm/                     # provider-agnostic LLM client abstraction
│   │   ├── auth/                    # minimal RBAC (JWT-based)
│   │   └── config.py
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/                         # React chat + generation UI
│   ├── package.json
│   └── Dockerfile
├── eval/
│   ├── corpus/                      # curated synthetic test documents
│   ├── questions.jsonl               # query -> expected source(s) / expected answer
│   └── run_eval.py                  # retrieval accuracy + grounding scoring
├── docker-compose.yml               # backend + frontend + chroma
└── Knowledge-Management-Agent-PoC.md
```

---

## 3. Core Workflow (Build Order)

**Phase A — Ingestion pipeline**
1. Parsers for PDF, DOCX, HTML, Markdown → normalized plain text + metadata
   (source filename, title, section headers where available).
2. Chunker: start with structure-aware splitting (by heading/section where the format
   allows, e.g. Markdown/HTML), falling back to ~500-800 token windows with ~15%
   overlap for unstructured text (PDF/DOCX). Keep this parameterized — it's the first
   thing to tune once eval numbers come in.
3. Embedder: pluggable interface (`embed(texts: list[str]) -> list[vector]`) so the
   embedding model can swap independently of the LLM provider choice.
4. Loader: writes chunks + metadata + vectors into a local ChromaDB collection.
5. CLI/API endpoint to trigger ingestion of an uploaded file.

**Phase B — Retrieval + Q&A (RAG core)**
1. Query embedding using the same embedder as ingestion.
2. Chroma similarity search, top-k retrieval (start k=5, tune during eval).
3. Prompt assembly: retrieved chunks + citations metadata + user question →
   grounded-answer prompt template.
4. LLM abstraction layer: single interface (`generate(prompt, system) -> text`) with
   swappable backend adapters (OpenAI/Azure OpenAI/Claude/Gemini) selected via config —
   this is what makes the "provider-agnostic" decision real rather than aspirational.
5. Response formatting: answer text + list of cited source chunks/documents.
6. FastAPI `/query` endpoint; target the doc's ≤8s response budget — instrument timing
   per stage (embed/retrieve/generate) so a slow stage is identifiable.

**Phase C — Document generation (runbooks / SOPs / KB articles / RCA summaries)**
1. One prompt template + output schema per generation type (they have genuinely
   different structures — a runbook is procedural steps, an RCA summary is
   timeline+root-cause+impact+remediation).
2. Each generation flow reuses Phase B's retrieval step to ground the draft in relevant
   ingested content, then applies its own template.
3. `/generate/{type}` endpoints (runbook, sop, kb-article, rca-summary), each accepting
   raw input (e.g., ticket text, incident notes) + optional retrieval context.
4. Minimal "approve & re-ingest" action: a generated doc, once reviewed, can be pushed
   back through the Phase A ingestion pipeline — closing the "lessons learned feed
   back into the KB" loop from the doc's objectives.

**Phase D — Web UI**
1. Chat-style interface for Q&A with inline source citations.
2. Simple form-based interface for each generation type (input → generated draft →
   accept/edit/re-ingest).
3. Basic auth (JWT) gating: viewer role (Q&A only) vs. author role (Q&A + generation +
   re-ingest).

**Phase E — Evaluation**
1. Curate ~15-30 synthetic documents (non-production, no PII) covering varied topics/
   formats, placed in `eval/corpus/`.
2. Curate a matching question set (`eval/questions.jsonl`): each entry has a query,
   the expected source document(s), and a reference answer.
3. `run_eval.py`:
   - Retrieval accuracy: for each query, check whether an expected source document
     appears in the top-3 retrieved chunks.
   - Grounding: for each generated answer, check whether its claims are supported by
     the retrieved chunks — start with an LLM-as-judge prompt (using the same LLM
     abstraction from Phase B) comparing answer against retrieved context; note this
     as an approximation, not a human-verified guarantee.
   - Latency: measure end-to-end query time against the 8s target.
4. Output a simple report (pass/fail per metric vs. the doc's targets).

**Phase F — Containerization**
1. `docker-compose.yml` wiring backend, frontend, and a Chroma service (or embedded
   Chroma persisted to a mounted volume — simpler for a PoC, avoids running Chroma as
   a separate service).
2. `.env`-based config for LLM provider selection/API keys, kept out of git (extend
   `.gitignore`).

---

## 4. Addressing the Vague Success Metrics

- **Retrieval accuracy ≥85% (top-3):** computed directly from `eval/questions.jsonl`
  once the eval set exists — this was the missing piece the doc didn't specify, now
  covered by Phase E.
- **Response grounding ≥90%:** approximated via LLM-as-judge scoring in `run_eval.py`;
  flag in the PoC results that this is an automated approximation, and true validation
  would need human review at production scale (matches the doc's own "Constraints"
  section, which already admits no production-grade guarantees).
- **≤8s response time:** measured via per-stage timing instrumentation in Phase B,
  reported per query in the eval run.

---

## 5. Verification

- Ingest the curated `eval/corpus/` documents and confirm chunk counts / metadata look
  sane before running full eval.
- Run `eval/run_eval.py` and confirm it reports retrieval accuracy, grounding
  approximation, and latency against the doc's three target metrics.
- Manually exercise the Web UI: ask a question with a known-correct source, confirm the
  citation matches; run one of each generation type end-to-end and confirm output
  structure matches the intended template; test the approve→re-ingest loop.
- Confirm `docker-compose up` brings up backend + frontend + Chroma cleanly on a clean
  checkout.
