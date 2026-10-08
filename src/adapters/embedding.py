import os
import time
import httpx
from typing import List, Dict, Any, Optional
from src import config

class GoogleAIStudioEmbedding:
    """
    Adapter for Google AI Studio Embeddings API.
    Supports gemini-embedding-001 (3072 dims) or gemini-embedding-2.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None
    ):
        self._api_key = api_key
        self._model_name = model_name

    @property
    def api_key(self) -> str:
        if self._api_key:
            return self._api_key
        return os.getenv("MODEL_API_KEY", config.MODEL_API_KEY or "").strip()

    @property
    def model_name(self) -> str:
        if self._model_name:
            return self._model_name
        return os.getenv("EMBEDDING_MODEL_NAME", config.EMBEDDING_MODEL_NAME or "gemini-embedding-001").strip()

    def is_available(self) -> bool:
        return bool(self.api_key)

    def embed_query(self, text: str) -> List[float]:
        """
        Embeds a single query string using Google AI Studio embedding API.
        """
        if not self.is_available():
            raise ValueError("Google AI Studio MODEL_API_KEY is not configured.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:embedContent?key={self.api_key}"
        body = {
            "content": {
                "parts": [{"text": text}]
            }
        }

        for attempt in range(4):
            try:
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(url, json=body)
                    if resp.status_code == 429 and attempt < 3:
                        sleep_s = 2.0 * (attempt + 1)
                        time.sleep(sleep_s)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    embedding = data.get("embedding", {})
                    values = embedding.get("values", [])
                    if not values:
                        raise ValueError(f"Empty embedding returned: {data}")
                    return values
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < 3:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                raise
            except Exception as e:
                if attempt < 3:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise
        return []

    def embed_batch(self, texts: List[str], batch_size: int = 15) -> List[List[float]]:
        """
        Embeds a list of texts in batches using Google AI Studio batchEmbedContents API.
        """
        if not self.is_available():
            raise ValueError("Google AI Studio MODEL_API_KEY is not configured.")

        if not texts:
            return []

        all_embeddings: List[List[float]] = []
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:batchEmbedContents?key={self.api_key}"

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            requests = [
                {
                    "model": f"models/{self.model_name}",
                    "content": {"parts": [{"text": t}]}
                }
                for t in batch
            ]
            body = {"requests": requests}

            batch_success = False
            for attempt in range(4):
                try:
                    with httpx.Client(timeout=45.0) as client:
                        resp = client.post(url, json=body)
                        if resp.status_code == 429 and attempt < 3:
                            sleep_s = 2.5 * (attempt + 1)
                            time.sleep(sleep_s)
                            continue
                        resp.raise_for_status()
                        data = resp.json()
                        embeddings_list = data.get("embeddings", [])
                        for item in embeddings_list:
                            vals = item.get("values", [])
                            all_embeddings.append(vals)
                        batch_success = True
                        break
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429 and attempt < 3:
                        time.sleep(2.5 * (attempt + 1))
                        continue
                    raise
                except Exception as e:
                    if attempt < 3:
                        time.sleep(2.0 * (attempt + 1))
                        continue
                    raise

            if not batch_success:
                raise RuntimeError(f"Failed to embed batch starting at index {i}")

            # Small delay between batches to respect rate limits
            if i + batch_size < len(texts):
                time.sleep(0.5)

        return all_embeddings

_embedding_instance: Optional[GoogleAIStudioEmbedding] = None

def get_embedding_adapter() -> GoogleAIStudioEmbedding:
    global _embedding_instance
    if _embedding_instance is None:
        _embedding_instance = GoogleAIStudioEmbedding()
    return _embedding_instance
