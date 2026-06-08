"""
HY-TUTOR: Vector Database Wrapper (ChromaDB)
Provides per-subject persistent ChromaDB clients with 3 collections
(lessons, problems, references) and metadata-filtered semantic search.

Phase 2.1 (CHANGES_PHASE_2.1.md):
  VectorDBManager is now subject-aware. Each subject gets its own
  ChromaDB persistent store under subject_workspaces/<subject>/vector_db/.
  The index_active_chunk() helper reads from active_chunk/ and indexes
  all content with per-chapter metadata for cross-chapter discovery.
"""

import os
import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any

# Lazy-imported ChromaDB modules (avoid import overhead if not needed)
_chromadb = None


def _ensure_chromadb():
    """Lazy-import chromadb to avoid loading it at module-import time."""
    global _chromadb
    if _chromadb is None:
        try:
            import chromadb
            _chromadb = chromadb
        except ImportError:
            raise ImportError(
                "chromadb is not installed. "
                "Install it with: pip install chromadb"
            )


class VectorDBManager:
    """
    Manages a per-subject ChromaDB persistent client with 3 collections:
    - lessons: Compiled lesson content (Unified_Lesson chunks)
    - problems: Exemplar problems with difficulty tiers
    - references: Reference material chunks

    All operations are lazy-initialized and thread-safe.
    """

    # Collection names
    COLLECTION_LESSONS = "lessons"
    COLLECTION_PROBLEMS = "problems"
    COLLECTION_REFERENCES = "references"

    def __init__(self, persist_dir: Optional[Path] = None, subject: Optional[str] = None):
        """
        Args:
            persist_dir: Directory for ChromaDB persistence.
                        Overrides subject-based resolution.
            subject: Subject name (e.g. "mathematics"). Derives persist_dir
                     from get_subject_vector_db(subject).
        """
        _ensure_chromadb()
        if persist_dir:
            self._persist_dir = str(persist_dir)
        elif subject:
            from utils.paths import get_subject_vector_db
            self._persist_dir = str(get_subject_vector_db(subject))
        else:
            raise ValueError("Either persist_dir or subject must be provided")
        self._subject = subject
        Path(self._persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = None
        self._collections: Dict[str, Any] = {}

    @property
    def client(self):
        """Lazy-initialize the persistent ChromaDB client."""
        if self._client is None:
            self._client = _chromadb.PersistentClient(path=self._persist_dir)
        return self._client

    def get_collection(self, name: str):
        """Get or create a collection by name."""
        if name not in self._collections:
            self._collections[name] = self.client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[name]

    @property
    def lessons(self):
        """Access the lessons collection."""
        return self.get_collection(self.COLLECTION_LESSONS)

    @property
    def problems(self):
        """Access the problems collection."""
        return self.get_collection(self.COLLECTION_PROBLEMS)

    @property
    def references(self):
        """Access the references collection."""
        return self.get_collection(self.COLLECTION_REFERENCES)

    # ========================================================================
    # INDEXING OPERATIONS
    # ========================================================================

    def index_lesson_chunk(
        self,
        chunk_id: str,
        text: str,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> None:
        """Index a lesson chunk into the lessons collection."""
        meta = metadata or {}
        meta.setdefault("chunk_id", chunk_id)
        upsert_kwargs = {
            "ids": [chunk_id],
            "documents": [text],
            "metadatas": [meta],
        }
        if embedding is not None:
            upsert_kwargs["embeddings"] = [embedding]
        self.lessons.upsert(**upsert_kwargs)

    def index_problem(
        self,
        problem_id: str,
        text: str,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> None:
        """Index a problem into the problems collection."""
        meta = metadata or {}
        meta.setdefault("problem_id", problem_id)
        upsert_kwargs = {
            "ids": [problem_id],
            "documents": [text],
            "metadatas": [meta],
        }
        if embedding is not None:
            upsert_kwargs["embeddings"] = [embedding]
        self.problems.upsert(**upsert_kwargs)

    def index_reference(
        self,
        ref_id: str,
        text: str,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> None:
        """Index a reference chunk into the references collection."""
        meta = metadata or {}
        meta.setdefault("ref_id", ref_id)
        upsert_kwargs = {
            "ids": [ref_id],
            "documents": [text],
            "metadatas": [meta],
        }
        if embedding is not None:
            upsert_kwargs["embeddings"] = [embedding]
        self.references.upsert(**upsert_kwargs)

    def batch_index_problems(
        self,
        problems: List[Dict[str, Any]],
    ) -> int:
        """Batch-index multiple problems. Returns count indexed."""
        if not problems:
            return 0

        ids = []
        documents = []
        metadatas = []
        embeddings = []
        has_embeddings = "embedding" in problems[0]

        for p in problems:
            ids.append(p["id"])
            documents.append(p["text"])
            metadatas.append(p.get("metadata", {}))
            if has_embeddings:
                embeddings.append(p["embedding"])

        upsert_kwargs = {
            "ids": ids,
            "documents": documents,
            "metadatas": metadatas,
        }
        if has_embeddings:
            upsert_kwargs["embeddings"] = embeddings

        self.problems.upsert(**upsert_kwargs)
        return len(ids)

    # ========================================================================
    # SEARCH OPERATIONS
    # ========================================================================

    def search(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """Semantic search with optional metadata filtering."""
        collection = self.get_collection(collection_name)

        query_kwargs: Dict[str, Any] = {
            "query_texts": [query_text],
            "n_results": n_results,
        }
        if where:
            query_kwargs["where"] = where
        if embedding is not None:
            query_kwargs["query_embeddings"] = [embedding]
            query_kwargs.pop("query_texts", None)

        try:
            results = collection.query(**query_kwargs)
        except Exception as e:
            print(f"[VECTOR_DB] Search error in '{collection_name}': {e}")
            return []

        output = []
        if results and results.get("ids") and results["ids"][0]:
            ids = results["ids"][0]
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            dists = results.get("distances", [[]])[0]

            for i, doc_id in enumerate(ids):
                output.append({
                    "id": doc_id,
                    "text": docs[i] if i < len(docs) else "",
                    "metadata": metas[i] if i < len(metas) else {},
                    "distance": dists[i] if i < len(dists) else 0.0,
                })
        return output

    def search_problems(
        self,
        query_text: str,
        n_results: int = 5,
        difficulty: Optional[str] = None,
        subject: Optional[str] = None,
        chapter_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Convenience method: search problems with optional filters."""
        where_filters = []
        if difficulty:
            where_filters.append({"difficulty": difficulty})
        if subject:
            where_filters.append({"subject": subject})
        if chapter_id:
            where_filters.append({"chapter_id": chapter_id})

        where = None
        if len(where_filters) == 1:
            where = where_filters[0]
        elif len(where_filters) > 1:
            where = {"$and": where_filters}

        return self.search(
            self.COLLECTION_PROBLEMS,
            query_text,
            n_results=n_results,
            where=where,
        )

    # ========================================================================
    # MANAGEMENT OPERATIONS
    # ========================================================================

    def get_collection_stats(self) -> Dict[str, int]:
        """Get item counts for all collections."""
        stats = {}
        for name in [self.COLLECTION_LESSONS, self.COLLECTION_PROBLEMS, self.COLLECTION_REFERENCES]:
            try:
                coll = self.get_collection(name)
                stats[name] = coll.count()
            except Exception:
                stats[name] = 0
        return stats

    def delete_chapter_data(self, chapter_id: str) -> int:
        """Delete all entries for a specific chapter from all collections."""
        total_deleted = 0
        for name in [self.COLLECTION_LESSONS, self.COLLECTION_PROBLEMS, self.COLLECTION_REFERENCES]:
            try:
                coll = self.get_collection(name)
                results = coll.get(where={"chapter_id": chapter_id})
                if results and results.get("ids"):
                    coll.delete(ids=results["ids"])
                    total_deleted += len(results["ids"])
            except Exception as e:
                print(f"[VECTOR_DB] Error deleting chapter data from '{name}': {e}")
        return total_deleted

    def clear_all(self) -> None:
        """Delete all data from all collections."""
        for name in [self.COLLECTION_LESSONS, self.COLLECTION_PROBLEMS, self.COLLECTION_REFERENCES]:
            try:
                self.client.delete_collection(name)
            except Exception:
                pass
        self._collections.clear()


# ============================================================================
# SINGLETON MANAGEMENT
# ============================================================================

_vector_db_instance: Optional[VectorDBManager] = None
_vector_db_subject: Optional[str] = None


def get_vector_db(
    persist_dir: Optional[Path] = None,
    subject: Optional[str] = None,
) -> VectorDBManager:
    """Get or create the singleton VectorDBManager instance.

    If the requested subject differs from the cached instance's subject,
    the singleton is recreated to point at the correct per-subject store.
    """
    global _vector_db_instance, _vector_db_subject

    if _vector_db_instance is not None and subject and subject != _vector_db_subject:
        # Subject changed — recreate the singleton
        _vector_db_instance = VectorDBManager(persist_dir=persist_dir, subject=subject)
        _vector_db_subject = subject
    elif _vector_db_instance is None:
        _vector_db_instance = VectorDBManager(persist_dir=persist_dir, subject=subject)
        _vector_db_subject = subject

    return _vector_db_instance


# ============================================================================
# INDEXING HELPER (Phase 2.1)
# ============================================================================

# Difficulty tier mapping
_TIER_MAP = {
    "TIER_1": "easy",
    "TIER_2": "medium",
    "TIER_3": "hard",
}


def _decompress_if_needed(embedding_value) -> Optional[List[float]]:
    """Handle both raw float lists and base64-compressed embeddings."""
    if embedding_value is None:
        return None
    if isinstance(embedding_value, list):
        return embedding_value
    if isinstance(embedding_value, str):
        # Compressed base64 string — decompress it
        try:
            from utils.embedding_utils import decompress_embedding
            return decompress_embedding(embedding_value)
        except Exception:
            return None
    return None


def _delete_chunk_entries(collection, subject: str, chapter_id: str, chunk_index: int) -> None:
    """Delete all entries matching a specific (subject, chapter_id, chunk_index) triple."""
    try:
        results = collection.get(where={
            "$and": [
                {"subject": subject},
                {"chapter_id": chapter_id},
                {"chunk_index": str(chunk_index)},
            ]
        })
        if results and results.get("ids"):
            collection.delete(ids=results["ids"])
    except Exception:
        # No matching entries or collection is empty — fine
        pass


def index_active_chunk(
    paths,
    chapter_id: str,
    subject: str,
    chunk_index: int,
) -> dict:
    """Read the active_chunk JSONs + Unified_Lesson.md and index them into
    the vector DB collections. Idempotent: deletes prior entries for the
    same (subject, chapter_id, chunk_index) before re-indexing.

    Returns a stats dict like {problems: N, references: N, lessons: N, indexed: True}.
    Best-effort: logs a warning and returns {"indexed": False, "reason": ...}
    if ChromaDB is unavailable — never raises, since the pipeline must not
    fail on vector-DB issues.
    """
    try:
        vdb = get_vector_db(subject=subject)
    except ImportError:
        print("[VECTOR_DB] ChromaDB not installed. Skipping indexing. "
              "Install with: pip install chromadb")
        return {"indexed": False, "reason": "chromadb not installed"}
    except Exception as e:
        print(f"[VECTOR_DB] Could not initialize ChromaDB: {e}")
        return {"indexed": False, "reason": str(e)}

    stats = {"problems": 0, "references": 0, "lessons": 0, "indexed": True}
    chunk_paths = paths.chunk_paths()

    # --- Index problems ---
    problems_path = chunk_paths["problems"]
    if problems_path.exists():
        try:
            with open(problems_path, "r", encoding="utf-8") as f:
                problems_data = json.load(f)

            problems = problems_data.get("problems", [])
            if problems:
                # Delete prior entries for this chunk
                _delete_chunk_entries(vdb.problems, subject, chapter_id, chunk_index)

                for p in problems:
                    problem_id = p.get("problem_id", f"{chapter_id}_chunk{chunk_index}_{stats['problems']}")
                    text = p.get("question_text_latex", "")
                    if not text:
                        continue

                    embedding = _decompress_if_needed(p.get("problem_embedding"))

                    difficulty_raw = p.get("difficulty_tier", "")
                    difficulty = _TIER_MAP.get(difficulty_raw, difficulty_raw.lower() if difficulty_raw else "")

                    source = "exemplar" if p.get("problem_type") == "EXEMPLAR_SEED" else "variant"

                    metadata = {
                        "subject": subject,
                        "chapter_id": chapter_id,
                        "chunk_index": str(chunk_index),
                        "difficulty": difficulty,
                        "source": source,
                        "problem_id": problem_id,
                    }

                    vdb.index_problem(
                        problem_id=problem_id,
                        text=text,
                        embedding=embedding,
                        metadata=metadata,
                    )
                    stats["problems"] += 1

                print(f"[VECTOR_DB] Indexed {stats['problems']} problems for {chapter_id} chunk {chunk_index}")
        except Exception as e:
            print(f"[VECTOR_DB] Error indexing problems for {chapter_id}: {e}")

    # --- Index references ---
    reference_path = chunk_paths["reference"]
    if reference_path.exists():
        try:
            with open(reference_path, "r", encoding="utf-8") as f:
                ref_data = json.load(f)

            elements = ref_data.get("extracted_elements", [])
            if elements:
                _delete_chunk_entries(vdb.references, subject, chapter_id, chunk_index)

                for idx, el in enumerate(elements):
                    content = el.get("content", "")
                    if not content:
                        continue
                    ref_id = f"{chapter_id}_ref_{chunk_index}_{idx}"
                    metadata = {
                        "subject": subject,
                        "chapter_id": chapter_id,
                        "chunk_index": str(chunk_index),
                        "source": "reference",
                        "element_type": el.get("element_type", ""),
                    }
                    vdb.index_reference(
                        ref_id=ref_id,
                        text=content,
                        embedding=None,
                        metadata=metadata,
                    )
                    stats["references"] += 1

                print(f"[VECTOR_DB] Indexed {stats['references']} reference chunks for {chapter_id} chunk {chunk_index}")
        except Exception as e:
            print(f"[VECTOR_DB] Error indexing references for {chapter_id}: {e}")

    # --- Index lesson ---
    lesson_path = chunk_paths["lesson"]
    if lesson_path.exists():
        try:
            lesson_text = lesson_path.read_text(encoding="utf-8")
            if lesson_text.strip():
                _delete_chunk_entries(vdb.lessons, subject, chapter_id, chunk_index)

                # Split by ## headers into sections
                sections = re.split(r'(?=^## )', lesson_text, flags=re.MULTILINE)
                sections = [s.strip() for s in sections if s.strip()]

                for idx, section in enumerate(sections):
                    # Extract section title from the first line
                    first_line = section.split("\n", 1)[0].strip()
                    section_title = first_line.lstrip("#").strip() if first_line.startswith("#") else f"section_{idx}"
                    lesson_id = f"{chapter_id}_lesson_{chunk_index}_{idx}"
                    metadata = {
                        "subject": subject,
                        "chapter_id": chapter_id,
                        "chunk_index": str(chunk_index),
                        "source": "lesson",
                        "section_title": section_title,
                    }
                    vdb.index_lesson_chunk(
                        chunk_id=lesson_id,
                        text=section,
                        embedding=None,
                        metadata=metadata,
                    )
                    stats["lessons"] += 1

                print(f"[VECTOR_DB] Indexed {stats['lessons']} lesson sections for {chapter_id} chunk {chunk_index}")
        except Exception as e:
            print(f"[VECTOR_DB] Error indexing lesson for {chapter_id}: {e}")

    return stats


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "VectorDBManager",
    "get_vector_db",
    "index_active_chunk",
]