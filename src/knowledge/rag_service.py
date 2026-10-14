import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.knowledge.rag_store import VectorStore, KnowledgeChunk
from src.knowledge.chunker import KnowledgeChunker
from src.adapters.embedding import get_embedding_adapter, EmbeddingClient
from src.adapters.jev import get_jev_adapter, JevAdapter
from src.config import VECTOR_STORE_PATH

class KnowledgeRAG:
    """
    Unified RAG Engine for Vien Chi Bao Customer Concierge.
    Embeds all project knowledge through the configured embeddings endpoint,
    performs high-speed semantic retrieval, and reranks candidate chunks
    using TypeSafe AI's Jev System One model.
    """
    def __init__(
        self,
        vector_store_path: Optional[Path] = None,
        embedding_adapter: Optional[EmbeddingClient] = None,
        jev_adapter: Optional[JevAdapter] = None
    ):
        self.vector_store_path = vector_store_path or VECTOR_STORE_PATH
        self.embedding_adapter = embedding_adapter or get_embedding_adapter()
        self.jev_adapter = jev_adapter or get_jev_adapter()
        self.chunker = KnowledgeChunker()
        self.vector_store = VectorStore(storage_path=self.vector_store_path)
        self._is_initialized = False

    def initialize(self, auto_index: bool = True):
        if self._is_initialized:
            return

        loaded = self.vector_store.load_from_file(self.vector_store_path)
        if auto_index:
            # Incremental: only chunks whose knowledge text changed are re-embedded.
            # A store built with another embedding model is rebuilt from scratch.
            model_changed = loaded and self.vector_store.embedding_model != self.embedding_adapter.model_name
            try:
                self.index_all(force=model_changed)
            except Exception as e:
                print(f"[RAG] Indexing failed: {e}")
        self._is_initialized = True

    def index_all(self, force: bool = False) -> Dict[str, Any]:
        """
        Extracts chunks from all project knowledge files, checks for changes,
        and embeds missing/updated chunks through the embeddings endpoint.
        """
        start_time = time.time()
        
        # Load existing store if available
        if not self.vector_store.chunks and self.vector_store_path.exists():
            self.vector_store.load_from_file(self.vector_store_path)

        all_chunks = self.chunker.chunk_all()
        chunks_to_embed: List[KnowledgeChunk] = []

        for ch in all_chunks:
            existing = self.vector_store.get_chunk(ch.id)
            if force or existing is None or existing.content_hash != ch.content_hash or ch.id not in self.vector_store.vectors:
                chunks_to_embed.append(ch)

        embedded_count = len(chunks_to_embed)
        reused_count = len(all_chunks) - embedded_count

        if chunks_to_embed:
            print(f"[RAG] Embedding {embedded_count} chunks with {self.embedding_adapter.model_name}...")
            texts = [c.content for c in chunks_to_embed]
            vectors = self.embedding_adapter.embed_batch(texts)

            for ch, vec in zip(chunks_to_embed, vectors):
                self.vector_store.add_chunk(ch, vec)

            # Ensure removed chunks from deleted files are pruned
            current_ids = {c.id for c in all_chunks}
            stale_ids = [cid for cid in list(self.vector_store.chunks.keys()) if cid not in current_ids]
            for sid in stale_ids:
                self.vector_store.chunks.pop(sid, None)
                self.vector_store.vectors.pop(sid, None)

            # Save updated vectors to disk
            self.vector_store.embedding_model = self.embedding_adapter.model_name
            self.vector_store.save_to_file(self.vector_store_path)
            print(f"[RAG] Successfully saved vector store to {self.vector_store_path}")

        duration = round(time.time() - start_time, 2)
        self._is_initialized = True

        return {
            "status": "success",
            "total_chunks": len(all_chunks),
            "embedded_new": embedded_count,
            "reused_cached": reused_count,
            "duration_seconds": duration,
            "embedding_model": self.embedding_adapter.model_name,
            "dimension": self.vector_store.dimension,
            "vector_store_path": str(self.vector_store_path)
        }

    def search(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[str] = None,
        channel: Optional[str] = None,
        min_score: float = 0.35,
        use_jev: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Embeds the customer query and performs cosine similarity search.
        When Jev is available and use_jev is True, candidate chunks are evaluated
        and reranked using TypeSafe AI's Jev System One model.
        """
        if not self._is_initialized:
            self.initialize(auto_index=True)

        if not query or not query.strip():
            return []

        # Embed the query
        try:
            q_vec = self.embedding_adapter.embed_query(query.strip())
        except Exception as e:
            print(f"Warning: Failed to embed RAG query: {e}")
            return []

        should_rerank_jev = bool(use_jev and self.jev_adapter.is_available())
        candidate_k = min(top_k + 1, 4) if should_rerank_jev else top_k

        results = self.vector_store.search(
            query_vector=q_vec,
            top_k=candidate_k,
            category=category,
            channel=channel,
            min_score=min_score
        )

        if should_rerank_jev and results:
            results = self.jev_adapter.rerank(
                query=query.strip(),
                chunks=results,
                top_k=top_k,
                min_score=min_score
            )
        else:
            results = results[:top_k]

        return results

    def get_stats(self) -> Dict[str, Any]:
        if not self._is_initialized:
            self.vector_store.load_from_file(self.vector_store_path)
        stats = self.vector_store.get_stats()
        stats["is_initialized"] = self._is_initialized
        stats["api_available"] = self.embedding_adapter.is_available()
        stats["jev_available"] = self.jev_adapter.is_available()
        stats["jev_model"] = self.jev_adapter.model_name
        stats["jev_enabled"] = self.jev_adapter.enabled
        return stats

_rag_instance: Optional[KnowledgeRAG] = None

def get_rag_service() -> KnowledgeRAG:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = KnowledgeRAG()
    return _rag_instance
