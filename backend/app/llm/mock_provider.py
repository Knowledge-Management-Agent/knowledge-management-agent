"""Deterministic, offline provider used for local pipeline verification and
tests when no real LLM/embedding API key is configured. Not intended for
judging actual answer quality -- swap `llm_provider` / `embedding_provider`
to a real backend in .env for that.
"""
import hashlib
import re

from app.llm.base import Embedder, LLMClient

_EMBED_DIM = 256


class MockEmbedder(Embedder):
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    @staticmethod
    def _embed_one(text: str) -> list[float]:
        vec = [0.0] * _EMBED_DIM
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        for tok in tokens:
            digest = hashlib.sha256(tok.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % _EMBED_DIM
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


class MockLLM(LLMClient):
    """Naive extractive 'generator': echoes back the most relevant part of
    the prompt's context so the retrieval -> prompt -> response wiring can
    be exercised without any external API dependency."""

    def generate(self, prompt: str, system: str = "") -> str:
        context_match = re.search(
            r"CONTEXT:\n(.*?)\n\nQUESTION:", prompt, re.DOTALL
        )
        question_match = re.search(r"QUESTION:\n(.*?)(\n\n|$)", prompt, re.DOTALL)
        if context_match:
            context = context_match.group(1).strip()
            first_chunk = context.split("\n---\n")[0].strip()
            snippet = first_chunk[:400]
            question = question_match.group(1).strip() if question_match else ""
            return (
                f"[mock-llm answer] Based on the retrieved context, here is the "
                f"most relevant excerpt for '{question}':\n\n{snippet}"
            )
        # No RAG context block found (e.g. generation templates) -- just
        # acknowledge the instruction so the endpoint still returns something
        # structurally valid for testing.
        return f"[mock-llm output]\n\n{prompt[:600]}"
