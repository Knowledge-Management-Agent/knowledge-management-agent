from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Provider selection (provider-agnostic LLM layer) ---
    # One of: mock, openai, azure_openai, claude, gemini, groq
    llm_provider: str = "mock"
    # One of: mock, openai, azure_openai, gemini, local
    embedding_provider: str = "mock"

    # --- OpenAI ---
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # --- Azure OpenAI ---
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_version: str = "2024-06-01"
    azure_openai_chat_deployment: str = ""
    azure_openai_embedding_deployment: str = ""

    # --- Claude (Anthropic) ---
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"

    # --- Gemini ---
    gemini_api_key: str = ""
    gemini_chat_model: str = "gemini-2.0-flash"
    gemini_embedding_model: str = "text-embedding-004"

    # --- Groq (OpenAI-compatible API, chat-completion only, no embeddings) ---
    groq_api_key: str = ""
    groq_chat_model: str = "llama-3.3-70b-versatile"

    # --- Local embedding (open-source sentence-transformers model, runs
    # in-process on CPU -- no API key, no external service) ---
    local_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # --- Vector store (ChromaDB) ---
    chroma_persist_dir: str = "./data/chroma"
    chroma_collection: str = "kb_documents"

    # --- Ingestion / retrieval tuning ---
    chunk_size_tokens: int = 700
    chunk_overlap_tokens: int = 100
    retrieval_top_k: int = 5

    # --- Auth (non-production RBAC) ---
    jwt_secret: str = "poc-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 120
    # demo users: username -> (password, role). role in {viewer, author}
    demo_viewer_username: str = "viewer"
    demo_viewer_password: str = "viewer123"
    demo_author_username: str = "author"
    demo_author_password: str = "author123"

    # --- Misc ---
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
