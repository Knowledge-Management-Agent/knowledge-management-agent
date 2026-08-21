# Backend Code Walkthrough — File by File, Function by Function

Every file in `backend/app/`, explained in plain language. Organized in the order a
request actually flows through the system: config → app startup → auth → API routes →
the RAG pipeline → LLM providers → ingestion → MCP. Read top to bottom for the full
picture, or jump to any file as a reference.

---

## `app/config.py` — the one place every setting lives

```python
class Settings(BaseSettings):
    llm_provider: str = "mock"
    embedding_provider: str = "mock"
    ...

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**What it is:** a single class listing every configurable value in the whole app —
which LLM/embedding provider to use, API keys, chunk size, JWT secret, demo passwords,
CORS origins. It's built on `pydantic-settings`, which means each field automatically
reads from an environment variable of the same name (uppercased) — e.g. `llm_provider`
reads from `LLM_PROVIDER`. That's the entire mechanism behind "change one env var to
swap providers."

**`get_settings()`**: wrapped in `@lru_cache`, meaning it only actually constructs the
`Settings` object once and hands back the same cached instance every time after —
avoids re-reading environment variables on every single request.

---

## `app/main.py` — the actual FastAPI application

**What it does:** creates the `FastAPI` app object, wires up CORS (which browser origins
are allowed to call this API — read from `settings.cors_origins`), adds a logging
middleware, and registers every route group ("router") the app exposes.

**`log_requests(request, call_next)`**: runs on *every* request. Notes the start time,
lets the request actually execute (`call_next`), then logs method + path + response
status + how many milliseconds it took. This is the "structured logging" mentioned
elsewhere in the project docs — simple, but it's what lets you `kubectl logs` the
backend pod and see real request activity.

**The 5 routers it registers** (each is its own file under `app/api/`, covered below):
`health`, `auth`, `ingest`, `query`, `generate`.

---

## `app/auth/security.py` — login and permission-checking

This is the *only* file that knows about passwords, JWTs, or roles. Every API route
that needs auth depends on functions from here — nothing duplicates this logic.

**`_demo_users(settings)`**: builds a dict of `{username: {password, role}}` from two
hardcoded demo accounts read out of `Settings` — one `viewer`, one `author`. This is
explicitly *not* a real user database — it's how the docstring itself describes it:
"non-production-grade."

**`authenticate(username, password, settings)`**: looks up the username, checks the
password matches, returns the role (`"viewer"` or `"author"`) if correct, `None` if not.

**`create_access_token(username, role, settings)`**: builds a JWT — a signed token
containing the username, role, and an expiry time — using the app's `jwt_secret`. This
is what gets handed back after a successful login.

**`decode_token(token, settings)`**: the reverse — takes a JWT, verifies its signature
is valid and it hasn't expired, and returns the data inside it. Raises a 401 error if
the token is invalid/expired.

**`get_current_user(credentials, settings)`**: a FastAPI "dependency" — every protected
route asks for this, and FastAPI automatically extracts the `Authorization: Bearer ...`
header, runs it through `decode_token`, and hands the route the resulting
`{username, role}`. If there's no token at all, it raises 401 immediately.

**`require_role(*allowed_roles)`**: a dependency *factory* — you call it with which
roles are allowed (e.g. `require_role(ROLE_AUTHOR)`), and it returns a dependency
function that checks `get_current_user()`'s role is in that allowed list, raising 403
if not. This is the actual RBAC enforcement mechanism — every route that needs
`author`-only access just adds `Depends(require_role(ROLE_AUTHOR))`.

---

## `app/api/` — the 5 route groups (what the outside world calls)

### `health.py`
One route: `GET /health`. Returns `{status, llm_provider, embedding_provider,
indexed_chunks}`. No auth required — this exists purely so Kubernetes (or you, via
`curl`) can check "is this thing alive and what's it configured with." Also used as the
readiness/liveness probe target in the K8s Deployment.

### `auth.py`
One route: `POST /auth/login`. Takes `{username, password}`, calls `authenticate()`; if
valid, calls `create_access_token()` and returns `{access_token, role}`. This is the
very first call any client (browser, `curl`, or the MCP server) makes.

### `query.py`
One route: `POST /query`, gated to `viewer` or `author` via `require_role`. Takes
`{question, top_k}`, calls `answer_question()` (the actual RAG logic, in `app/rag/qa.py`
— see below), returns the result as-is. This route itself contains almost no logic — it's
purely "check auth, call the real function, return the result."

### `generate.py`
Two routes, both `author`-only:
- `POST /generate` — takes `{doc_type, input_text, use_retrieval}`, validates `doc_type`
  is one of the 4 known types, calls `generate_document()` (in `app/rag/generation.py`).
- `POST /generate/approve` — takes `{doc_type, title, content}` (a *reviewed* generated
  document), writes it to a temporary `.md` file on disk, then feeds that file through
  the same ingestion pipeline used for uploads (`IngestionService.ingest_file`) so it
  becomes searchable. This is the "lessons learned feed back into the KB" loop — a
  generated document, once approved, re-enters the system as a real source document.

### `ingest.py`
Two routes:
- `POST /ingest` (`author`-only) — accepts an uploaded file, checks its extension is
  supported, saves it to a temp file, runs it through `IngestionService.ingest_file()`,
  cleans up the temp file afterward (in a `finally` block, so it's deleted even if
  ingestion fails).
- `GET /ingest/documents` (`viewer` or `author`) — returns the list of currently indexed
  source documents and total chunk count, via `get_store().list_documents()`.

---

## `app/rag/` — the actual "agent" logic

This is the heart of the whole system — everything above this is just plumbing to reach
these functions.

### `retriever.py`

**`Retriever.retrieve(query, top_k)`**: the entire retrieval step in one function.
1. Embeds the query text into a vector (`self._embedder.embed([query])`)
2. Asks the vector store for the `top_k` closest chunks (`self._store.query(...)`)
3. Wraps each raw result into a `RetrievedChunk` dataclass (text, source, title, section,
   distance) — a clean, typed object the rest of the code works with instead of raw
   dicts.

`top_k` defaults to `settings.retrieval_top_k` (5) if not explicitly passed.

### `store.py`

**`ChromaStore.__init__`**: opens (or creates) a ChromaDB `PersistentClient` pointed at
`settings.chroma_persist_dir`, and gets/creates a collection configured for cosine
similarity (`hnsw:space: cosine`).

**`.add(ids, embeddings, documents, metadatas)`**: writes new chunks into Chroma — called
once per ingested document, with one entry per chunk.

**`.query(embedding, top_k)`**: the actual similarity search — hands Chroma a vector,
gets back the `top_k` nearest chunks (text + metadata + distance score), reshapes
Chroma's slightly awkward parallel-list response format into a clean list of dicts.

**`.count()`**: total number of chunks currently stored — what `/health` reports.

**`.list_documents()`**: walks every stored chunk's metadata, groups by `source`
filename, returns one entry per *document* (not per chunk) with a chunk count — this is
what powers the "Indexed documents" list in the UI.

**`get_store()`**: `@lru_cache`'d singleton, same pattern as `get_settings()` — one
shared `ChromaStore` instance for the whole app process.

### `prompts.py`

Not code logic — this is the file that defines *what the AI is told to do*. Contains:

- `QA_SYSTEM` / `QA_TEMPLATE` — the system instruction and prompt shape for Q&A: "answer
  using ONLY the provided context... don't make anything up."
- `GENERATION_SYSTEM` — a dict of 4 different system prompts, one per document type
  (`runbook`, `sop`, `kb_article`, `rca_summary`), each specifying that type's exact
  expected structure (e.g. RCA = Incident Summary/Timeline/Root Cause/Impact/Remediation/
  Lessons Learned).
- `GENERATION_TEMPLATE` — the shared prompt shape used for all 4 generation types:
  context + raw input.
- `GROUNDING_JUDGE_SYSTEM` / `_TEMPLATE` — used only by the evaluation harness
  (`eval/run_eval.py`), not the live app — asks an LLM to judge whether a given answer's
  claims are actually supported by the given context, outputting just `GROUNDED` or
  `UNGROUNDED`.
- **`format_context(chunks)`**: turns a list of `RetrievedChunk` objects into the actual
  text block that gets pasted into a prompt — each chunk labeled with `[source: title /
  section]`, chunks separated by `---`. If there are no chunks at all, returns
  `"(no relevant documents retrieved)"` instead of an empty string, so the LLM has
  something explicit to react to.

### `qa.py` — the Q&A flow, start to finish

**`answer_question(question, retriever, llm, top_k)`**:
1. Times and calls `retriever.retrieve(question, top_k)` — gets back relevant chunks
2. Builds the final prompt: `QA_TEMPLATE.format(context=format_context(chunks),
   question=question)`
3. Times and calls `llm.generate(prompt, system=QA_SYSTEM)` — the actual AI call
4. Builds a `citations` list from the chunks used, **de-duplicated by source** (so if 3
   chunks came from the same document, you see that document once, not 3 times)
5. Returns `{answer, citations, timings_ms}` — timings broken down by retrieval vs.
   generation vs. total, in milliseconds

If `retriever`/`llm` aren't passed in, it builds default ones itself (`Retriever()`,
`get_llm_client()`) — this "accept an optional instance, build a default if none given"
pattern is what makes the code testable (tests pass in fake/mock objects) and what makes
the MCP server able to reuse this exact function unmodified... except the MCP server
actually doesn't call this directly — it calls the *REST API*, which calls this. Worth
knowing: this function has zero awareness that MCP exists at all.

### `generation.py` — the document-generation flow

**`generate_document(doc_type, input_text, use_retrieval, retriever, llm, top_k)`**:
1. Validates `doc_type` is one of the 4 known `DOC_TYPES` — raises `ValueError`
   otherwise
2. If `use_retrieval` is true, runs the *same* `retriever.retrieve()` call as Q&A does —
   but embedding `input_text` (the raw notes) instead of a question, to find related
   existing documents
3. Builds the prompt via `GENERATION_TEMPLATE`, using the type-specific system prompt
   from `GENERATION_SYSTEM[doc_type]`
4. Calls the LLM, returns `{doc_type, content, citations}`

Notice this is almost identical in shape to `answer_question()` — same
retrieve-then-generate pattern, just a different prompt template and no timing
breakdown. That's intentional: Q&A and generation are the same underlying mechanism
applied to two different prompt shapes.

---

## `app/llm/` — the swappable AI provider layer

### `base.py`
Two abstract base classes, both with exactly one method each:
```python
class LLMClient(ABC):
    def generate(self, prompt: str, system: str = "") -> str: ...

class Embedder(ABC):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```
This is the entire abstraction that makes "swap providers via one env var" possible —
every piece of code above this (retriever, qa, generation) only ever calls `.generate()`
or `.embed()`, never anything provider-specific.

### `factory.py`
**`build_llm_client(settings)`** / **`build_embedder(settings)`**: a big if/elif chain —
reads `settings.llm_provider` (or `embedding_provider`), and returns an instance of the
matching class (`MockLLM`, `OpenAILLM`, `ClaudeLLM`, `GeminiLLM`, `GroqLLM`, ...). Each
provider's SDK is imported *inside* its branch (`from openai import OpenAI` sits inside
the `if provider == "openai"` block) — so if you're running with `groq`, the `anthropic`
and `google-generativeai` packages never even need to be importable.

**`get_llm_client()`** / **`get_embedder()`**: `@lru_cache`'d singletons, same pattern
as `get_settings()`/`get_store()` — build once, reuse for the process lifetime.

### `mock_provider.py`
Already covered in detail earlier — `MockEmbedder` hashes words into a fake vector
(zero real semantic understanding), `MockLLM` regex-extracts and echoes back the first
retrieved chunk. Purely for offline pipeline testing.

### `openai_provider.py`
Four classes: `OpenAILLM`, `OpenAIEmbedder`, `AzureOpenAILLM`, `AzureOpenAIEmbedder`.
Each is a thin wrapper: construct the official `openai` SDK client with the right
API key/endpoint, call `.chat.completions.create(...)` or `.embeddings.create(...)`,
unwrap the response down to just the text/vectors the rest of the app cares about.
Azure's versions differ only in using `deployment` names instead of model names, and
needing an `azure_endpoint` + `api_version`.

### `claude_provider.py`
`ClaudeLLM` only (Anthropic has no public embeddings API, so no `ClaudeEmbedder`
exists). Uses the `anthropic` SDK's `messages.create()`. Note Claude's API shape differs
slightly from OpenAI's — `system` is a separate top-level parameter, not a message in
the list, and the response content is a list of typed blocks you have to filter down to
just the text ones (`block.type == "text"`).

### `gemini_provider.py`
`GeminiLLM` + `GeminiEmbedder`, using `google.generativeai`. Gemini's chat API doesn't
have a distinct system-prompt parameter the way OpenAI/Claude do, so `GeminiLLM` just
concatenates system + prompt into one string before sending.

### `groq_provider.py`
`GroqLLM` only (Groq has no embeddings API). The interesting bit: it reuses the `openai`
SDK entirely, just pointed at a different `base_url`
(`https://api.groq.com/openai/v1`) — Groq deliberately mimics OpenAI's API shape so
existing OpenAI-compatible tooling works against it unmodified. This is currently the
LLM provider actually deployed.

### `local_provider.py`
`LocalEmbedder` only. Uses `sentence-transformers` to run an open-source embedding
model **in-process, on CPU** — no API key, no network call, no external service at all.
`_load_model()` is `@lru_cache`'d so the (fairly large) model only gets loaded into
memory once, not on every single embed call. This is currently the embedding provider
actually deployed.

---

## `app/ingestion/` — turning a raw file into searchable chunks

### `parsers.py`

**`parse_file(path)`**: looks at the file extension, dispatches to the matching parser,
then calls `_extract_title()` on the result. Returns `(text, title)`.

- **`_parse_pdf`**: uses `pypdf` to extract raw text page by page, joins with blank
  lines. No heading detection — PDFs don't reliably expose structure, which is exactly
  why the chunker has a fallback mode for unstructured text.
- **`_parse_docx`**: walks every paragraph; if a paragraph's Word *style* is a heading
  (e.g. "Heading 2"), converts it into Markdown-style `##` syntax so the chunker can
  later recognize it as a section boundary — this is the one parser that actively
  reconstructs document structure rather than just dumping text.
- **`_parse_html`**: uses BeautifulSoup to walk heading tags (`h1`-`h6`), paragraphs, and
  list items in document order, converting headings to `#`-style Markdown the same way.
- Markdown/plain text: no parsing needed at all — read the file as-is, since it's
  already either structured (Markdown headings) or just plain text.

**`_extract_title(text)`**: looks at the first non-empty line; if it's a Markdown
heading, uses that (stripped of `#`s) as the title; otherwise uses the first 120
characters of the first line as a fallback.

### `chunker.py`
Already covered in detail earlier — tries heading-based splitting first
(`_chunk_by_sections`), falls back to fixed-size overlapping word windows
(`_chunk_by_words`) either when there are no headings at all, or when an individual
section is still too long on its own.

### `loader.py`

**`IngestionService.ingest_file(path, source_label)`**: the function that ties the
*entire* ingestion pipeline together, called by both the `/ingest` route and the
`/generate/approve` route:
1. `parse_file(path)` → raw text + title
2. `chunk_text(text, chunk_size, overlap)` → list of chunks
3. `self._embedder.embed([c.text for c in chunks])` → one vector per chunk
4. Builds a unique ID per chunk (`f"{source}::{random_hex}"`) and a metadata dict
   (source filename, title, section, chunk index)
5. `self._store.add(ids, embeddings, texts, metadatas)` → writes everything into Chroma
6. Returns `{source, title, chunks_ingested}`

If chunking produces zero chunks (e.g. an empty file), it short-circuits and returns
early without calling the embedder or store at all — avoids embedding an empty list.

---

## `app/mcp/` — the MCP server (already covered in detail separately)

Quick recap in this file's context, since it's a genuinely different *kind* of code from
everything above — it's a client, not a server, relative to the rest of the backend:

- **`config.py`**: reads `KM_API_BASE_URL`/`KM_MCP_USERNAME`/`KM_MCP_PASSWORD`/
  `KM_MCP_TOKEN` from env vars into a small dataclass — independent of `app/config.py`,
  since this process may be pointed at a totally different (e.g. remote/deployed)
  instance of the API than whatever `app/config.py` would describe locally.
- **`client.py`**: `KMApiClient` — logs into `/auth/login`, caches the JWT, retries once
  on a 401 (token expired), wraps `/query`, `/generate`, `/generate/approve`, `/ingest`,
  `/ingest/documents` as plain Python methods.
- **`server.py`**: uses the `mcp` SDK's `FastMCP` to declare 4 `@mcp.tool()`-decorated
  functions (`query_knowledge_base`, `generate_document`, `ingest_document`,
  `list_documents`), each just calling the matching `KMApiClient` method and returning
  the result (or an `{"error": ...}` dict if the API call failed). `mcp.run()` starts it
  listening on stdio.

---

## The full call chain for one real request

To tie it all together — here's *every function that actually runs*, in order, for one
`POST /query` call:

```
main.py (log_requests middleware starts timer)
  → api/query.py: query()
      → auth/security.py: get_current_user() → decode_token()   [verifies JWT]
      → auth/security.py: require_role()                         [checks role allowed]
      → rag/qa.py: answer_question()
          → rag/retriever.py: Retriever.retrieve()
              → llm/factory.py: get_embedder() → (e.g.) local_provider.py: LocalEmbedder.embed()
              → rag/store.py: ChromaStore.query()                 [actual Chroma search]
          → rag/prompts.py: format_context()
          → llm/factory.py: get_llm_client() → (e.g.) groq_provider.py: GroqLLM.generate()
main.py (log_requests logs the final status + elapsed time)
```

Every box in that chain is a function documented above — nothing else happens.
