import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.knowledge.rag_store import VectorStore, KnowledgeChunk
from src.knowledge.chunker import KnowledgeChunker
from src.adapters.embedding import get_embedding_adapter, GoogleAIStudioEmbedding
from src.config import VECTOR_STORE_PATH, KNOWLEDGE_DIR, EMBEDDINGS_DIR

class KnowledgeRAG:
    """
    Unified RAG Engine for Vien Chi Bao Customer Concierge.
    Embeds all project knowledge onto Google AI Studio server and performs
    high-speed semantic retrieval.
    """
    def __init__(
        self,
        vector_store_path: Optional[Path] = None,
        embedding_adapter: Optional[GoogleAIStudioEmbedding] = None
    ):
        self.vector_store_path = vector_store_path or VECTOR_STORE_PATH
        self.embedding_adapter = embedding_adapter or get_embedding_adapter()
        self.chunker = KnowledgeChunker()
        self.vector_store = VectorStore(storage_path=self.vector_store_path)
        self._is_initialized = False

    def initialize(self, auto_index: bool = True):
        if self._is_initialized:
            return

        # Attempt to load existing vector store
        loaded = self.vector_store.load_from_file(self.vector_store_path)
        if not loaded and auto_index:
            print("[RAG] Vector store not found on disk. Indexing all knowledge with Google AI Studio...")
            self.index_all(force=False)
        self._is_initialized = True

    def index_all(self, force: bool = False) -> Dict[str, Any]:
        """
        Extracts chunks from all project knowledge files, checks for changes,
        and embeds missing/updated chunks via Google AI Studio API.
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
            print(f"[RAG] Embedding {embedded_count} chunks using Google AI Studio ({self.embedding_adapter.model_name})...")
            texts = [c.content for c in chunks_to_embed]
            vectors = self.embedding_adapter.embed_batch(texts, batch_size=15)

            for ch, vec in zip(chunks_to_embed, vectors):
                self.vector_store.add_chunk(ch, vec)

            # Ensure removed chunks from deleted files are pruned
            current_ids = {c.id for c in all_chunks}
            stale_ids = [cid for cid in list(self.vector_store.chunks.keys()) if cid not in current_ids]
            for sid in stale_ids:
                self.vector_store.chunks.pop(sid, None)
                self.vector_store.vectors.pop(sid, None)

            # Save updated vectors to disk
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
        min_score: float = 0.35
    ) -> List[Dict[str, Any]]:
        """
        Embeds customer query on Google AI Studio and performs cosine similarity search.
        """
        if not self._is_initialized:
            self.initialize(auto_index=True)

        if not query or not query.strip():
            return []

        # Embed query using Google AI Studio
        try:
            q_vec = self.embedding_adapter.embed_query(query.strip())
        except Exception as e:
            print(f"Warning: Failed to embed query with Google AI Studio: {e}")
            return []

        results = self.vector_store.search(
            query_vector=q_vec,
            top_k=top_k,
            category=category,
            channel=channel,
            min_score=min_score
        )
        return results

    def get_stats(self) -> Dict[str, Any]:
        if not self._is_initialized:
            self.vector_store.load_from_file(self.vector_store_path)
        stats = self.vector_store.get_stats()
        stats["is_initialized"] = self._is_initialized
        stats["api_available"] = self.embedding_adapter.is_available()
        return stats

_rag_instance: Optional[KnowledgeRAG] = None

def get_rag_service() -> KnowledgeRAG:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = KnowledgeRAG()
    return _rag_instance
