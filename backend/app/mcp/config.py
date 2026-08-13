"""Config for the local MCP server process. Deliberately independent of
app.config.Settings: this process is a REST client that talks to a
(possibly remote, e.g. EKS-hosted) Knowledge Management API, not the API
process itself, so it has its own small env-var surface (MCP-4)."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MCPClientConfig:
    api_base_url: str
    username: str | None
    password: str | None
    token: str | None
    timeout_seconds: float

    @property
    def has_credentials(self) -> bool:
        return bool(self.token or (self.username and self.password))


def load_config() -> MCPClientConfig:
    return MCPClientConfig(
        api_base_url=os.environ.get("KM_API_BASE_URL", "http://localhost:8000").rstrip("/"),
        username=os.environ.get("KM_MCP_USERNAME") or None,
        password=os.environ.get("KM_MCP_PASSWORD") or None,
        token=os.environ.get("KM_MCP_TOKEN") or None,
        timeout_seconds=float(os.environ.get("KM_MCP_TIMEOUT_SECONDS", "30")),
    )
