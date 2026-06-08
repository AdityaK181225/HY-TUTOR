"""
HY-TUTOR: Similar Problems Finder Component
ChromaDB semantic search with difficulty-tier filter over the problems collection.
"""

import streamlit as st
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Ensure core_pipeline is importable (cached at module level)
_CORE_PIPELINE_PATH = str(Path(__file__).resolve().parent.parent.parent / "core_pipeline")
if _CORE_PIPELINE_PATH not in sys.path:
    sys.path.insert(0, _CORE_PIPELINE_PATH)


def render_similar_problems(
    subject: str = "mathematics",
    chapter_id: str = "",
    current_problem_id: str = "",
):
    """
    Render the Similar Problems Finder panel.

    Uses VectorDBManager to perform semantic search over indexed problems.
    Displays results in a compact, filterable card layout.
    """
    st.markdown("---")
    st.subheader("🔍 Similar Problems")

    # Check if ChromaDB is available
    try:
        from utils.vector_db import get_vector_db
        vdb = get_vector_db(subject=subject)
    except ImportError:
        st.info("ChromaDB not installed. Install with `pip install chromadb` to enable similar problems search.")
        return
    except Exception as e:
        st.warning(f"Vector database unavailable: {e}")
        return

    # Search controls
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        query = st.text_input(
            "Search problems...",
            key="similar_problems_query",
            placeholder="e.g., integration by parts, derivative of sin(x)",
        )
    with col2:
        difficulty = st.selectbox(
            "Difficulty",
            ["All", "Easy", "Medium", "Hard"],
            key="similar_problems_difficulty",
        )
    with col3:
        n_results = st.selectbox(
            "Results",
            [3, 5, 10],
            index=1,
            key="similar_problems_n_results",
        )

    if not query:
        st.caption("Enter a search query to find similar problems from the chapter's exemplar set.")
        return

    # Build metadata filter
    diff_map = {"Easy": "easy", "Medium": "medium", "Hard": "hard"}
    difficulty_filter = diff_map.get(difficulty)

    try:
        results = vdb.search_problems(
            query_text=query,
            n_results=n_results,
            difficulty=difficulty_filter,
            subject=subject,
            chapter_id=chapter_id if chapter_id else None,
        )
    except Exception as e:
        st.error(f"Search failed: {e}")
        return

    if not results:
        st.info("No similar problems found. Try a different query or adjust filters.")
        return

    # Render results
    st.caption(f"Found {len(results)} similar problem(s):")
    for i, result in enumerate(results):
        meta = result.get("metadata", {})
        dist = result.get("distance", 0.0)
        # ChromaDB cosine distance: 0 = identical, 2 = opposite
        similarity_pct = max(0, (1 - dist / 2)) * 100

        with st.expander(
            f"**{i+1}.** {meta.get('difficulty', 'N/A').title()} "
            f"— {similarity_pct:.0f}% match",
            expanded=(i == 0),
        ):
            st.markdown(result.get("text", "*(no text)*"))

            # Metadata row
            meta_parts = []
            if meta.get("topic"):
                meta_parts.append(f"**Topic:** {meta['topic']}")
            if meta.get("source"):
                meta_parts.append(f"**Source:** {meta['source']}")
            if meta.get("chapter_id"):
                meta_parts.append(f"**Chapter:** {meta['chapter_id']}")
            if meta_parts:
                st.caption(" · ".join(meta_parts))


__all__ = ["render_similar_problems"]