"""MCP server for the Knowledge Management Agent (MCP-1).

Exposes the KM Agent's core capabilities as MCP tools by calling the
deployed REST API (KM_API_BASE_URL) -- it is a transport/interface layer,
not a parallel implementation of the RAG/ingestion pipeline (MCP-3), and it
inherits the API's viewer/author RBAC by authenticating as a real user
(MCP-2) rather than re-implementing access control.

Two transports (MCP-5):
- stdio (default) -- launched locally by Claude Desktop/Code as a
  subprocess. Run with: python -m app.mcp.server
- sse -- runs as a long-lived HTTP server so it can be deployed in-cluster
  (see k8s/12-mcp-deployment.yaml) instead of on the caller's machine.
  Select with MCP_TRANSPORT=sse; MCP_HOST/MCP_PORT control the bind
  address (default 0.0.0.0:8001). The client then connects to
  http://<host>:<port>/sse instead of spawning this file directly.

Config (MCP-4): KM_API_BASE_URL, KM_MCP_USERNAME, KM_MCP_PASSWORD
(or KM_MCP_TOKEN for a pre-issued bearer token), KM_MCP_TIMEOUT_SECONDS,
MCP_TRANSPORT, MCP_HOST, MCP_PORT.
"""
import os

from mcp.server.fastmcp import FastMCP

from app.mcp.client import KMApiClient, KMApiError
from app.mcp.config import load_config
from app.rag.generation import DOC_TYPES

_config = load_config()
_client = KMApiClient(_config)

mcp = FastMCP("km-agent")


@mcp.tool()
def query_knowledge_base(question: str, top_k: int | None = None) -> dict:
    """Answer a natural-language question using retrieval-augmented
    generation over the ingested knowledge base. Returns the answer plus
    the source documents it was grounded in.
    """
    try:
        return _client.query(question, top_k=top_k)
    except KMApiError as exc:
        return {"error": str(exc), "status_code": exc.status_code}


@mcp.tool()
def generate_document(doc_type: str, input_text: str, use_retrieval: bool = True) -> dict:
    """Generate a runbook, sop, kb_article, or rca_summary from raw
    operational input (e.g. incident notes, ticket text), optionally
    grounded in retrieved context from the knowledge base. Requires an
    author-role identity. doc_type must be one of: runbook, sop,
    kb_article, rca_summary.
    """
    if doc_type not in DOC_TYPES:
        return {"error": f"doc_type must be one of {DOC_TYPES}"}
    try:
        return _client.generate(doc_type, input_text, use_retrieval=use_retrieval)
    except KMApiError as exc:
        return {"error": str(exc), "status_code": exc.status_code}


@mcp.tool()
def ingest_document(file_path: str) -> dict:
    """Ingest a local file (PDF, DOCX, HTML, or Markdown) into the
    knowledge base: parse, chunk, embed, and store it so future queries
    can retrieve it. Requires an author-role identity. file_path must be
    readable on the machine running this MCP server.
    """
    try:
        return _client.ingest_file(file_path)
    except (KMApiError, FileNotFoundError) as exc:
        return {"error": str(exc)}


@mcp.tool()
def list_documents() -> dict:
    """List documents currently indexed in the knowledge base, with
    per-document chunk counts."""
    try:
        return _client.list_documents()
    except KMApiError as exc:
        return {"error": str(exc), "status_code": exc.status_code}


def main() -> None:
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        mcp.settings.host = os.environ.get("MCP_HOST", "0.0.0.0")
        mcp.settings.port = int(os.environ.get("MCP_PORT", "8001"))
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
