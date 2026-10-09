import os
import httpx
from typing import List, Optional
from src import config


class EmbeddingClient:
    """
    Client for any OpenAI-compatible /v1/embeddings endpoint. In production this
    is the local embedding bridge (scripts/embedding_bridge.py) on the same host.
    """
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None
    ):
        self._base_url = base_url
        self._api_key = api_key
        self._model_name = model_name

    @property
    def base_url(self) -> str:
        if self._base_url is not None:
            return self._base_url
        return os.getenv("EMBEDDING_BASE_URL", config.EMBEDDING_BASE_URL or "").strip()

    @property
    def api_key(self) -> str:
        if self._api_key is not None:
            return self._api_key
        return os.getenv("EMBEDDING_API_KEY", "").strip()

    @property
    def model_name(self) -> str:
        if self._model_name:
            return self._model_name
        return os.getenv("EMBEDDING_MODEL_NAME", config.EMBEDDING_MODEL_NAME).strip()

    def is_available(self) -> bool:
        return bool(self.base_url)

    def embed_query(self, text: str) -> List[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        if not self.is_available():
            raise ValueError("EMBEDDING_BASE_URL is not configured.")
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        url = f"{self.base_url.rstrip('/')}/embeddings"
        vectors: List[List[float]] = []
        with httpx.Client(timeout=60.0) as client:
            for i in range(0, len(texts), batch_size):
                resp = client.post(url, headers=headers, json={"model": self.model_name, "input": texts[i:i + batch_size]})
                resp.raise_for_status()
                data = sorted(resp.json()["data"], key=lambda d: d["index"])
                vectors.extend(d["embedding"] for d in data)
        return vectors


_embedding_instance: Optional[EmbeddingClient] = None

def get_embedding_adapter() -> EmbeddingClient:
    global _embedding_instance
    if _embedding_instance is None:
        _embedding_instance = EmbeddingClient()
    return _embedding_instance
