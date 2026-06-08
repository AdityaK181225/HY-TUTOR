"""
HY-TUTOR: LEVEL 7 SIDEBAR COMPONENT (sidebar.py)
Manages dynamic subject switching, progress metrics, and weak-area indicators.
Upgraded to cross-reference the Master Syllabus directly for 100% accurate metric calculation.
"""

import streamlit as st
import json
from pathlib import Path

def render_sidebar():
    """Renders the comprehensive, state-aware navigation sidebar."""
    st.sidebar.title("🧬 HY-TUTOR")
    st.sidebar.markdown("Stateful Mesh Education Engine")
    st.sidebar.markdown("---")

    # 1. Subject Selector (Isolated Domains)
    st.sidebar.subheader("Select Subject")
    subjects = ["Physics", "Chemistry", "Mathematics", "Biology"]
    
    active_subject = st.sidebar.selectbox(
        "Active Domain",
        subjects,
        index=subjects.index(st.session_state.get("active_subject", "Physics"))
    )

    # Immediately trigger a reload and commit the UI state to disk if changed
    if active_subject != st.session_state.get("active_subject"):
        st.session_state["active_subject"] = active_subject
        st.session_state["ui_state"] = "INIT"

        # We write directly to the JSON here to ensure the state doesn't bounce back on rerun.
        # The ui_session.json is now stored per-subject under
        # data_library/subject_workspaces/<subject>/ui_session.json (so
        # each subject remembers its own last selected chapter).
        try:
            import sys
            if "core_pipeline" not in sys.path:
                sys.path.insert(
                    0,
                    str(Path(__file__).resolve().parent.parent.parent / "core_pipeline"),
                )
            from utils.paths import SubjectPaths  # type: ignore
            ui_state_file = SubjectPaths.for_subject(active_subject).ui_session
        except Exception:
            # Migration fallback: legacy flat path
            ui_state_file = Path("data_library/active_workspace/ui_session.json")
        ui_state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(ui_state_file, "w", encoding="utf-8") as f:
            json.dump({
                "active_subject": active_subject,
                "ui_state": "INIT",
                "selected_chap_id": st.session_state.get("selected_chap_id")
            }, f)

        # Pin the ambient subject pointer so any downstream C-subprocess
        # that reads the pointer (rather than receiving --subject
        # explicitly) still resolves the right subject.
        try:
            from utils.paths import set_current_subject  # type: ignore
            set_current_subject(active_subject)
        except Exception:
            pass

        st.rerun()

    st.sidebar.markdown("---")

    # 2. Perfect Metric Syncing (Cross-referencing Master Syllabus against Global Tracker)
    st.sidebar.subheader("📈 Subject Metrics")
    
    syllabus_path = Path("data_library/metadata/Master_Subject_Syllabus.json")
    tracker_path = Path("data_library/Global_Subject_Tracker.json")

    total_chapters = 1
    completed_chapters = 0
    active_subject_lower = active_subject.lower()

    if syllabus_path.exists():
        try:
            with open(syllabus_path, "r", encoding="utf-8") as f:
                syllabus_data = json.load(f)
            
            # Find the true target baseline for the active subject
            subject_metadata = syllabus_data.get(active_subject_lower, {})
            chapters = subject_metadata.get("chapters", {})
            total_chapters = len(chapters) if len(chapters) > 0 else 1

            # Match completions exclusively against the active domain
            if tracker_path.exists():
                with open(tracker_path, "r", encoding="utf-8") as f:
                    tracker_data = json.load(f)
                
                global_ledger = tracker_data.get("chapters_ledger", {})
                for chap_id in chapters.keys():
                    if chap_id in global_ledger and global_ledger[chap_id].get("status") == "COMPLETED":
                        completed_chapters += 1

            percent = int((completed_chapters / total_chapters) * 100)
            st.sidebar.metric(label="Chapters Completed", value=f"{completed_chapters} / {total_chapters}", delta=f"{percent}%")
            st.sidebar.progress(percent / 100.0)

            # Render Active Weak Area Flags (State C Triggers) specifically for this subject
            st.sidebar.markdown("---")
            st.sidebar.subheader("⚠️ Weak Areas Flagged")
            
            weak_count = 0
            for chap_id in chapters.keys():
                if chap_id in global_ledger:
                    ledger_entry = global_ledger[chap_id]
                    weak_list = [w for w in ledger_entry.get("weak_areas_flagged", []) if w.get("is_weak_area") is True]
                    
                    for weak in weak_list:
                        st.sidebar.warning(f"{weak['topic']}\n(Chapter: {chap_id}, Chunk: {weak['chunk_index']})")
                        weak_count += 1
                        
            if weak_count == 0:
                st.sidebar.success("No active weak areas! Keep it up.")

        except Exception as e:
            st.sidebar.error(f"Error syncing academic metrics: {e}")
    else:
        st.sidebar.info("Waiting for Master Syllabus compilation to initialize metrics...")