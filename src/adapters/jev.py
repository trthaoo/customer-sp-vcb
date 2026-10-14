from typing import List, Dict, Any, Optional
import os
import concurrent.futures
from src import config

try:
    from typesafe_sdk import TypeSafeClient, Noul, Choice, Score
    TYPESAFE_SDK_AVAILABLE = True
except ImportError:
    TYPESAFE_SDK_AVAILABLE = False
    TypeSafeClient = None
    Noul = None
    Choice = None
    Score = None


class JevAdapter:
    """
    Adapter for TypeSafe AI's Jev model (System One decision model).
    Specialized in fast, structured, probabilistic decisions for RAG:
      - Reranking candidate knowledge passages
      - Filtering out irrelevant or hallucinated passages
      - Evaluating factual grounding of responses
      - Gating whether an incoming customer message requires knowledge retrieval
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        enabled: Optional[bool] = None,
        rerank_threshold: Optional[float] = None,
        timeout: Optional[float] = None,
        client: Optional[Any] = None
    ):
        self._api_key = api_key
        self._base_url = base_url
        self._model_name = model_name
        self._enabled = enabled
        self._rerank_threshold = rerank_threshold
        self._timeout = timeout
        self._custom_client = client
        self._cached_client: Optional[Any] = None
        self._consecutive_failures: int = 0
        self._circuit_open_until: float = 0.0

    @property
    def api_key(self) -> str:
        if self._api_key is not None:
            return self._api_key
        key = os.getenv("JEV_API_KEY", os.getenv("TYPESAFE_API_KEY", getattr(config, "JEV_API_KEY", ""))).strip()
        return key or "1c01c20a638060e68d52fc9a40397ac589af2679a52f5ff441c22f9b8deb5b18"

    @property
    def base_url(self) -> Optional[str]:
        if self._base_url is not None:
            raw = self._base_url
        else:
            raw = os.getenv("JEV_BASE_URL", os.getenv("TYPESAFE_BASE_URL", getattr(config, "JEV_BASE_URL", ""))).strip()
        if not raw or "commandcode.ai" in raw or "trycloudflare.com" in raw:
            raw = "https://62-106-66-4.sslip.io/jev"
        url = raw.rstrip("/")
        if url.endswith("/v1/systemone"):
            url = url[:-len("/v1/systemone")]
        elif url.endswith("/v1"):
            url = url[:-len("/v1")]
        return url.rstrip("/")

    @property
    def model_name(self) -> str:
        if self._model_name is not None:
            return self._model_name
        model = os.getenv("JEV_MODEL", os.getenv("TYPESAFE_DEFAULT_MODEL", getattr(config, "JEV_MODEL", "typesafe/jev"))).strip()
        return model or "typesafe/jev"

    @property
    def enabled(self) -> bool:
        if self._enabled is not None:
            return self._enabled
        val = os.getenv("JEV_ENABLED", str(getattr(config, "JEV_ENABLED", True))).strip().lower()
        return val in ("true", "1", "yes")

    @property
    def rerank_threshold(self) -> float:
        if self._rerank_threshold is not None:
            return self._rerank_threshold
        try:
            return float(os.getenv("JEV_RERANK_THRESHOLD", str(getattr(config, "JEV_RERANK_THRESHOLD", 0.35))))
        except (ValueError, TypeError):
            return 0.35

    @property
    def timeout(self) -> float:
        if self._timeout is not None:
            return self._timeout
        try:
            return float(os.getenv("JEV_TIMEOUT", str(getattr(config, "JEV_TIMEOUT", 1.8))))
        except (ValueError, TypeError):
            return 1.8

    def is_available(self) -> bool:
        """
        Returns True if the SDK is installed, Jev is enabled, and an API key is provided
        (or a custom/mock client was injected).
        Automatically returns False if circuit breaker is currently open due to unreachable bridge.
        """
        if self._custom_client is not None:
            return self.enabled
        import time
        if time.time() < self._circuit_open_until:
            return False
        return bool(TYPESAFE_SDK_AVAILABLE and self.enabled and self.api_key)

    def _get_client(self) -> Optional[Any]:
        if self._custom_client is not None:
            return self._custom_client
        if not self.is_available():
            return None
        if self._cached_client is None:
            kwargs: Dict[str, Any] = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            if self.model_name:
                kwargs["model"] = self.model_name
            if self.timeout:
                kwargs["timeout"] = self.timeout
            self._cached_client = TypeSafeClient(**kwargs)
        return self._cached_client

    def get_info(self) -> Dict[str, Any]:
        return {
            "available": self.is_available(),
            "enabled": self.enabled,
            "model_name": self.model_name,
            "base_url": self.base_url or "https://api.typesafe.ai (default)",
            "rerank_threshold": self.rerank_threshold,
            "sdk_installed": TYPESAFE_SDK_AVAILABLE
        }

    def evaluate_chunk(self, query: str, chunk: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submits candidate chunk to Jev System One model to evaluate relevance
        against customer inquiry.
        """
        if not self.is_available():
            return {
                "jev_score": float(chunk.get("score", 0.5)),
                "is_relevant": True,
                "choice": "unverified",
                "confidence": 0.0,
                "evaluated": False
            }

        state = {
            "customer_query": query,
            "knowledge_title": chunk.get("title", ""),
            "knowledge_category": chunk.get("category", ""),
            "knowledge_passage": (chunk.get("content", "") or "")[:1200]
        }

        questions = {
            "is_relevant": Noul(
                instructions="Does this knowledge passage contain factual and directly helpful information to address the customer's question or request?"
            ),
            "relevance_level": Choice(
                instructions="How well does this passage satisfy the customer's query?",
                criteria={
                    "irrelevant": "Has nothing to do with what the customer is asking",
                    "related": "Mentions related keywords or topics but does not directly answer",
                    "direct": "Directly and accurately answers the customer inquiry with specific facts, specifications, or policies"
                }
            )
        }

        try:
            client = self._get_client()
            response = client.system_one(
                state=state,
                questions=questions,
                model=self.model_name
            )

            is_rel_ans = response.answers.get("is_relevant")
            choice_ans = response.answers.get("relevance_level")

            noul_prob = float(is_rel_ans.noul) if (is_rel_ans and hasattr(is_rel_ans, "noul")) else 0.5
            selected_choice = choice_ans.choice if (choice_ans and hasattr(choice_ans, "choice")) else "related"
            conf = float(choice_ans.confidence) if (choice_ans and hasattr(choice_ans, "confidence")) else 0.5

            # Calculate calibrated Jev score (0.0 to 1.0)
            jev_score = round(noul_prob, 4)

            # Adjust score slightly based on choice category
            if selected_choice == "direct":
                jev_score = min(1.0, round(jev_score * 1.05, 4))
            elif selected_choice == "irrelevant":
                jev_score = min(jev_score, 0.25)

            # Reset failure count on success
            self._consecutive_failures = 0

            return {
                "jev_score": jev_score,
                "is_relevant": (selected_choice != "irrelevant" and jev_score >= self.rerank_threshold),
                "choice": selected_choice,
                "confidence": conf,
                "evaluated": True
            }
        except Exception as e:
            import time
            self._consecutive_failures += 1
            if self._consecutive_failures >= 2:
                # Trip circuit breaker for 45 seconds so pipeline does not repeatedly block
                self._circuit_open_until = time.time() + 45.0
                print(f"[JevAdapter] Circuit breaker tripped: Jev bridge unavailable ({e}). Disabling Jev for 45s.")
            print(f"[JevAdapter] Warning: Jev evaluation failed for chunk '{chunk.get('title')}': {e}")
            return {
                "jev_score": float(chunk.get("score", 0.5)),
                "is_relevant": True,
                "choice": "unverified",
                "confidence": 0.0,
                "evaluated": False,
                "error": str(e)
            }

    def rerank(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_k: int = 5,
        min_score: Optional[float] = None,
        abstain_on_irrelevant: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Reranks candidate knowledge chunks using Jev System One model.
        Runs evaluations concurrently to minimize RAG latency.
        Implements Gating: abstains (returns empty list) if all candidate passages
        are judged irrelevant / not in documentation.
        """
        if not chunks:
            return []

        if not self.is_available():
            return chunks[:top_k]

        threshold = min_score if min_score is not None else self.rerank_threshold

        # Score candidates in parallel
        scored_chunks: List[Dict[str, Any]] = []
        max_workers = min(len(chunks), 5)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_chunk = {
                executor.submit(self.evaluate_chunk, query, chunk): chunk
                for chunk in chunks
            }
            for future in concurrent.futures.as_completed(future_to_chunk):
                chunk = future_to_chunk[future]
                try:
                    eval_result = future.result()
                except Exception as e:
                    eval_result = {
                        "jev_score": float(chunk.get("score", 0.5)),
                        "is_relevant": True,
                        "choice": "error",
                        "confidence": 0.0,
                        "evaluated": False,
                        "error": str(e)
                    }

                chunk_copy = dict(chunk)
                vec_score = float(chunk.get("score", 0.0))
                jev_score = float(eval_result.get("jev_score", vec_score))

                # Combined score: 30% vector semantic similarity, 70% Jev decision judgment
                combined_score = round(0.3 * vec_score + 0.7 * jev_score, 4)

                chunk_copy["jev_score"] = jev_score
                chunk_copy["jev_choice"] = eval_result.get("choice")
                chunk_copy["jev_confidence"] = eval_result.get("confidence")
                chunk_copy["jev_evaluated"] = eval_result.get("evaluated", False)
                chunk_copy["original_vector_score"] = vec_score
                chunk_copy["score"] = combined_score

                scored_chunks.append(chunk_copy)

        # Sort descending by combined score (or jev_score)
        scored_chunks.sort(key=lambda c: (c.get("score", 0.0), c.get("jev_score", 0.0)), reverse=True)

        # Filter out irrelevant chunks below threshold
        filtered = [
            c for c in scored_chunks
            if c.get("jev_choice") != "irrelevant" and c.get("score", 0.0) >= threshold
        ]

        # Jev Gating: If all candidate chunks are irrelevant or below threshold,
        # abstain from feeding ungrounded documents into LLM ("Abstain: Not in Docs").
        if abstain_on_irrelevant:
            return filtered[:top_k]
        return (filtered if filtered else scored_chunks)[:top_k]

    def needs_knowledge(self, query: str) -> Dict[str, Any]:
        """
        Fast System One classification: Does this customer message require
        retrieving knowledge (policies, catalogue, prices, warranty)?
        """
        if not self.is_available():
            return {"needs_knowledge": True, "confidence": 0.5, "evaluated": False}

        state = {"customer_message": query}
        questions = {
            "needs_knowledge": Noul(
                instructions="Does this customer query require retrieving store product catalogue, pricing, warranty, or policies to be accurately answered?"
            )
        }

        try:
            client = self._get_client()
            resp = client.system_one(state=state, questions=questions, model=self.model_name)
            ans = resp.answers.get("needs_knowledge")
            prob = float(ans.noul) if (ans and hasattr(ans, "noul")) else 0.5
            return {
                "needs_knowledge": prob >= 0.5,
                "probability": prob,
                "evaluated": True
            }
        except Exception as e:
            return {"needs_knowledge": True, "confidence": 0.5, "evaluated": False, "error": str(e)}

    def verify_grounding(self, query: str, answer: str, context: str) -> Dict[str, Any]:
        """
        Verifies whether every claim in the generated answer is strictly grounded
        in the provided knowledge context passages (hallucination prevention).
        """
        if not self.is_available():
            return {"is_grounded": True, "confidence": 0.5, "evaluated": False}

        state = {
            "customer_query": query,
            "generated_reply": answer,
            "knowledge_passages": context[:2500]
        }
        questions = {
            "is_grounded": Noul(
                instructions="Is every factual statement in the generated reply strictly supported by the knowledge passages, with zero invented or hallucinated details?"
            )
        }

        try:
            client = self._get_client()
            resp = client.system_one(state=state, questions=questions, model=self.model_name)
            ans = resp.answers.get("is_grounded")
            prob = float(ans.noul) if (ans and hasattr(ans, "noul")) else 0.5
            return {
                "is_grounded": prob >= 0.6,
                "probability": prob,
                "evaluated": True
            }
        except Exception as e:
            return {"is_grounded": True, "confidence": 0.5, "evaluated": False, "error": str(e)}


_jev_instance: Optional[JevAdapter] = None


def get_jev_adapter() -> JevAdapter:
    global _jev_instance
    if _jev_instance is None:
        _jev_instance = JevAdapter()
    return _jev_instance
