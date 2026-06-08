"""
HY-TUTOR: LEVEL 7 LESSON VIEWER COMPONENT (lesson_viewer.py)
Standardizes high-contrast LaTeX compilation and reading layouts.
UPDATED: Implemented native st.container(height=...) to fix independent scrolling
and lock the content frame.

Wired up to per-subject paths (data_library/subject_workspaces/<subject>/).
"""

import streamlit as st
from pathlib import Path

def render_lesson_viewer():
    """Reads and structures the forged Unified_Lesson.md for screen rendering.
    Reads from the per-subject chunk directory for the active subject.
    """
    # Resolve the per-subject lesson path from the ambient pointer
    # (the UI always has st.session_state["active_subject"] set).
    active_subject = (st.session_state.get("active_subject") or "").strip().lower()
    lesson_path: Path
    if active_subject:
        try:
            # Lazy import: see pipeline_runner for the same pattern.
            import sys
            if "core_pipeline" not in sys.path:
                sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "core_pipeline"))
            from utils.paths import SubjectPaths  # type: ignore
            lesson_path = SubjectPaths.for_subject(active_subject).chunk_paths()["lesson"]
        except Exception:
            lesson_path = Path("data_library/subject_workspaces") / active_subject / "active_chunk" / "Unified_Lesson.md"
    else:
        # Migration fallback: legacy flat path
        lesson_path = Path("data_library/active_workspace/active_chunk/Unified_Lesson.md")

    st.markdown("### 📖 Active Study Material")

    if not lesson_path.exists():
        st.info("Headless compilation complete. Standby for lesson rendering...")
        return

    try:
        with open(lesson_path, "r", encoding="utf-8") as f:
            lesson_md = f.read()

        # Independent Scroll Lock (Height constraint limits size to viewport)
        # Using height=800 creates a scrollable div purely for the markdown
        viewer_container = st.container(height=800, border=True)

        with viewer_container:
            # Native Streamlit rendering parses inline $ and display $$ LaTeX math perfectly.
            st.markdown(lesson_md, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"[SYSTEM ERROR] Failed reading Unified Lesson cache: {e}")
