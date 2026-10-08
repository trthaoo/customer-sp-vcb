import json
import hashlib
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional
import numpy as np

def compute_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

@dataclass
class KnowledgeChunk:
    id: str
    category: str  # catalogue, policy, shared, meta_rule, meta_edge_case, tiktok_rule, tiktok_edge_case
    source_file: str
    title: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""

    def __post_init__(self):
        if not self.content_hash and self.content:
            self.content_hash = compute_text_hash(self.content)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeChunk":
        return cls(
            id=data["id"],
            category=data.get("category", "shared"),
            source_file=data.get("source_file", ""),
            title=data.get("title", ""),
            content=data.get("content", ""),
            metadata=data.get("metadata", {}),
            content_hash=data.get("content_hash", "")
        )

class VectorStore:
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path
        self.chunks: Dict[str, KnowledgeChunk] = {}
        self.vectors: Dict[str, np.ndarray] = {}  # id -> normalized 1D np.ndarray
        self._cached_matrix: Optional[np.ndarray] = None
        self._cached_ids: List[str] = []
        self.embedding_model: str = "gemini-embedding-001"
        self.dimension: int = 3072

    def clear(self):
        self.chunks.clear()
        self.vectors.clear()
        self._cached_matrix = None
        self._cached_ids = []

    def add_chunk(self, chunk: KnowledgeChunk, vector: List[float]):
        vec = np.array(vector, dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 1e-9:
            vec = vec / norm
        else:
            vec = np.zeros_like(vec)

        self.chunks[chunk.id] = chunk
        self.vectors[chunk.id] = vec
        self.dimension = len(vector)
        self._cached_matrix = None
        self._cached_ids = []

    def get_chunk(self, chunk_id: str) -> Optional[KnowledgeChunk]:
        return self.chunks.get(chunk_id)

    def _rebuild_cache_matrix(self):
        self._cached_ids = list(self.vectors.keys())
        if self._cached_ids:
            matrix_list = [self.vectors[cid] for cid in self._cached_ids]
            self._cached_matrix = np.vstack(matrix_list)  # (N, D)
        else:
            self._cached_matrix = np.zeros((0, self.dimension), dtype=np.float32)

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        category: Optional[str] = None,
        channel: Optional[str] = None,
        min_score: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Fast cosine similarity search using numpy matrix multiplication.
        Returns ranked list of items: { 'chunk': KnowledgeChunk, 'score': float }
        """
        if not self.vectors:
            return []

        q_vec = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm < 1e-9:
            return []
        q_normed = q_vec / q_norm

        if self._cached_matrix is None or len(self._cached_ids) != len(self.vectors):
            self._rebuild_cache_matrix()

        # Dot product with all normalized vectors gives exact cosine similarity
        scores = np.dot(self._cached_matrix, q_normed)  # (N,)

        # Sort descending
        top_indices = np.argsort(-scores)

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score < min_score:
                continue

            cid = self._cached_ids[idx]
            chunk = self.chunks.get(cid)
            if not chunk:
                continue

            # Filtering
            if category and chunk.category != category:
                continue

            if channel:
                chunk_channel = chunk.metadata.get("channel")
                if chunk_channel and chunk_channel != "any" and chunk_channel != channel:
                    continue

            results.append({
                "id": chunk.id,
                "score": round(score, 4),
                "title": chunk.title,
                "category": chunk.category,
                "source_file": chunk.source_file,
                "content": chunk.content,
                "metadata": chunk.metadata
            })

            if len(results) >= top_k:
                break

        return results

    def save_to_file(self, path: Optional[Path] = None):
        target_path = path or self.storage_path
        if not target_path:
            raise ValueError("No storage path provided for VectorStore")

        target_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "embedding_model": self.embedding_model,
            "dimension": self.dimension,
            "count": len(self.chunks),
            "chunks": [chunk.to_dict() for chunk in self.chunks.values()],
            "vectors": {cid: vec.tolist() for cid, vec in self.vectors.items()}
        }

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_from_file(self, path: Optional[Path] = None) -> bool:
        target_path = path or self.storage_path
        if not target_path or not target_path.exists():
            return False

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.embedding_model = data.get("embedding_model", "gemini-embedding-001")
            self.dimension = data.get("dimension", 3072)
            self.clear()

            chunks_list = data.get("chunks", [])
            vectors_dict = data.get("vectors", {})

            for ch_data in chunks_list:
                chunk = KnowledgeChunk.from_dict(ch_data)
                self.chunks[chunk.id] = chunk

            for cid, vec_list in vectors_dict.items():
                vec = np.array(vec_list, dtype=np.float32)
                norm = np.linalg.norm(vec)
                if norm > 1e-9:
                    vec = vec / norm
                self.vectors[cid] = vec

            self._rebuild_cache_matrix()
            return True
        except Exception as e:
            print(f"Warning: Failed to load VectorStore from {target_path}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        cat_counts: Dict[str, int] = {}
        for ch in self.chunks.values():
            cat_counts[ch.category] = cat_counts.get(ch.category, 0) + 1

        return {
            "total_chunks": len(self.chunks),
            "total_vectors": len(self.vectors),
            "embedding_model": self.embedding_model,
            "dimension": self.dimension,
            "categories": cat_counts,
            "storage_path": str(self.storage_path) if self.storage_path else None
        }
