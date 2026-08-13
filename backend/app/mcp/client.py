"""Thin HTTP client for the Knowledge Management REST API. The MCP server
calls through this client rather than importing app.rag/app.ingestion
directly, so it enforces the exact same RBAC the REST API already enforces
(MCP-2) without duplicating auth logic (MCP-3) -- it authenticates as a
real viewer/author user and lets the API's own require_role() reject
anything the token isn't allowed to do.
"""
from pathlib import Path

import httpx

from app.mcp.config import MCPClientConfig


class KMApiError(RuntimeError):
    def __init__(self, status_code: int, detail: str):
        super().__init__(f"KM API error {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class KMApiClient:
    def __init__(self, config: MCPClientConfig):
        self._config = config
        self._token: str | None = config.token
        self._role: str | None = None
        self._client = httpx.Client(base_url=config.api_base_url, timeout=config.timeout_seconds)

    def close(self) -> None:
        self._client.close()

    # -- auth -----------------------------------------------------------

    def _login(self) -> None:
        if not (self._config.username and self._config.password):
            raise KMApiError(
                401,
                "No token and no KM_MCP_USERNAME/KM_MCP_PASSWORD configured for the MCP server",
            )
        resp = self._client.post(
            "/auth/login",
            json={"username": self._config.username, "password": self._config.password},
        )
        if resp.status_code != 200:
            raise KMApiError(resp.status_code, resp.text)
        body = resp.json()
        self._token = body["access_token"]
        self._role = body["role"]

    def _auth_headers(self) -> dict:
        if not self._token:
            self._login()
        return {"Authorization": f"Bearer {self._token}"}

    def _request(self, method: str, path: str, retry_on_401: bool = True, **kwargs) -> httpx.Response:
        headers = kwargs.pop("headers", {}) or {}
        headers.update(self._auth_headers())
        resp = self._client.request(method, path, headers=headers, **kwargs)
        if resp.status_code == 401 and retry_on_401 and self._config.username:
            # token expired/invalid -- re-authenticate once and retry
            self._token = None
            return self._request(method, path, retry_on_401=False, **kwargs)
        if resp.status_code >= 400:
            raise KMApiError(resp.status_code, resp.text)
        return resp

    # -- API calls --------------------------------------------------------

    def health(self) -> dict:
        return self._client.get("/health").json()

    def query(self, question: str, top_k: int | None = None) -> dict:
        payload = {"question": question}
        if top_k is not None:
            payload["top_k"] = top_k
        return self._request("POST", "/query", json=payload).json()

    def generate(self, doc_type: str, input_text: str, use_retrieval: bool = True) -> dict:
        payload = {"doc_type": doc_type, "input_text": input_text, "use_retrieval": use_retrieval}
        return self._request("POST", "/generate", json=payload).json()

    def approve(self, doc_type: str, title: str, content: str) -> dict:
        payload = {"doc_type": doc_type, "title": title, "content": content}
        return self._request("POST", "/generate/approve", json=payload).json()

    def ingest_file(self, file_path: str) -> dict:
        path = Path(file_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"No such file: {path}")
        with path.open("rb") as fh:
            files = {"file": (path.name, fh)}
            return self._request("POST", "/ingest", files=files).json()

    def list_documents(self) -> dict:
        return self._request("GET", "/ingest/documents").json()
