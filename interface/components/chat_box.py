"""
HY-TUTOR: LEVEL 7 CHAT BOX COMPONENT (chat_box.py)
Integrates Command 6 & Command 7 to stream live Socratic dialogue loops.
Upgraded with st.chat_input for seamless 'Enter to Submit' and robust state transition mechanics.

Wired up to per-subject paths (data_library/subject_workspaces/<subject>/).
The chat history is now stored per-subject under the per-subject chapter_cache.
"""

import html
import streamlit as st
import subprocess
import json
import sys
from pathlib import Path
from components.icons import icon

# Lazy import helper for core_pipeline.utils (Streamlit module load order)
def _paths_for(subject: str):
    """Resolve the per-subject :class:`SubjectPaths` for ``subject``."""
    import sys
    if "core_pipeline" not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "core_pipeline"))
    from utils.paths import SubjectPaths  # type: ignore
    return SubjectPaths.for_subject(subject)


def render_chat_box(chapter_id, chunk_index):
    """Coordinates low-latency state changes for active student dialogue.
    Reads/writes the chat history under the per-subject chapter_cache.
    """
    st.markdown("### 💬 Socratic Study Co-Pilot")

    # Resolve the active subject from session state and build the
    # per-subject history path.
    active_subject = (st.session_state.get("active_subject") or "").strip().lower()
    if active_subject:
        history_path = _paths_for(active_subject).session_history()
    else:
        # Migration fallback: legacy flat chapter_cache
        history_path = Path("chapter_cache/active_session_history.json")

    # 1. Initialize Active State History inside memory
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    if history_path.exists():
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                hist_data = json.load(f)
                st.session_state["chat_history"] = hist_data.get("history", [])
        except Exception:
            pass

    # 2. Render Dialogue Bubbles inside a scrollable container
    chat_container = st.container(height=550)
    with chat_container:
        for msg in st.session_state["chat_history"]:
            bubble_class = "tutor-bubble" if msg["role"] == "tutor" else "user-bubble"
            label = "🤖 Tutor" if msg["role"] == "tutor" else "👤 You"
            safe_content = html.escape(msg['content']).replace("\n", "<br>")
            st.markdown(
                f'<div class="{bubble_class}"><strong>{label}:</strong><br>{safe_content}</div>',
                unsafe_allow_html=True
            )

    # 3. Custom Multi-line Chat Input (Enter = newline, Button = send)
    st.markdown("### ✍️ Your Response")
    col_input, col_btn = st.columns([0.88, 0.12])
    with col_input:
        student_input = st.text_area(
            "Message",
            placeholder="Type your solution or question here...",
            height=100,
            label_visibility="collapsed",
            key="custom_chat_input",
        )
    with col_btn:
        st.markdown("<div style='padding-top: 0px;'></div>", unsafe_allow_html=True)
        st.markdown(
            f"<div style='text-align:center;margin-top:2px;'>{icon('send', size=22, color='#FFFFFF')}</div>",
            unsafe_allow_html=True,
        )
        send_clicked = st.button("Send", key="send_chat_btn", use_container_width=True,
                                  help="Send message (or press Ctrl+Enter in the text box)")

    st.caption("💡 *Enter = new line • Button or Ctrl+Enter = send*")

    if send_clicked and student_input and student_input.strip():
        # Echo Student response instantly into the viewport to eliminate latency
        st.session_state["chat_history"].append({"role": "user", "content": student_input.strip()})
        st.rerun()

    # 4. Trigger Command 6 Subprocess Loop on new user message
    # Guard: Only fire if last message is from user AND we haven't already attempted processing
    if (st.session_state["chat_history"] 
        and st.session_state["chat_history"][-1]["role"] == "user"
        and not st.session_state.get("_tutor_fired_for_last_msg", False)):
        
        # Mark that we're about to fire the tutor for this message
        st.session_state["_tutor_fired_for_last_msg"] = True
        latest_input = st.session_state["chat_history"][-1]["content"]
        with st.spinner("Analyzing and routing Socratic response..."):
            try:
                cmd = [
                    sys.executable,
                    "core_pipeline/command_6_tutor.py",
                    "--subject", active_subject,
                    chapter_id,
                    str(chunk_index),
                    latest_input,
                    str(history_path)
                ]
                # Executing synchronous pass
                subprocess.run(cmd, capture_output=True, text=True, check=True)

                # Fetch output from system logs safely
                if history_path.exists():
                    with open(history_path, "r", encoding="utf-8") as f:
                        hist_data = json.load(f)
                        st.session_state["chat_history"] = hist_data.get("history", [])

                # If tutor responded, clear the guard so next user message can fire
                if (st.session_state["chat_history"]
                    and st.session_state["chat_history"][-1]["role"] != "user"):
                    st.session_state["_tutor_fired_for_last_msg"] = False

                st.rerun()
            except Exception as e:
                # On error, clear the guard after a delay to allow retry
                st.session_state["_tutor_fired_for_last_msg"] = False
                st.error(f"Socratic Triage crashed: {e}")
    
    # Reset guard when user sends a NEW message (different from the one we tracked)
    if (st.session_state["chat_history"] 
        and st.session_state["chat_history"][-1]["role"] == "user"
        and st.session_state.get("_tutor_fired_for_last_msg", False)
        and st.session_state.get("_last_user_msg") != st.session_state["chat_history"][-1]["content"]):
        st.session_state["_tutor_fired_for_last_msg"] = False
    
    # Track the last user message content for comparison
    if st.session_state["chat_history"] and st.session_state["chat_history"][-1]["role"] == "user":
        st.session_state["_last_user_msg"] = st.session_state["chat_history"][-1]["content"]

    # 5. Finish Session & Invoke Command 7 Logic
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🏁 Close Session", use_container_width=True):
            with st.spinner("Processing Session Metrics..."):
                try:
                    cmd = [
                        sys.executable,
                        "core_pipeline/command_7_ledger.py",
                        "--subject", active_subject,
                        chapter_id,
                        str(chunk_index),
                        str(history_path)
                    ]
                    subprocess.run(cmd, capture_output=True, text=True, check=True)

                    # Clear session caches and return to Selection
                    st.session_state["ui_state"] = "SELECTION"
                    if history_path.exists():
                        history_path.unlink()
                    st.session_state.pop("chat_history", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to seal ledger: {e}")

    with col2:
        # The seamless progression trigger
        if st.button("⏭️ Mastered! Next Chunk", type="primary", use_container_width=True):
            with st.spinner("Logging Mastery & Generating Next Chunk..."):
                try:
                    # Step 1: Run Command 7 to log score, update ledgers, and increment chunk index
                    cmd7 = [
                        sys.executable,
                        "core_pipeline/command_7_ledger.py",
                        "--subject", active_subject,
                        chapter_id,
                        str(chunk_index),
                        str(history_path)
                    ]
                    subprocess.run(cmd7, capture_output=True, text=True, check=True)

                    # Step 2: Clear local session parameters
                    if history_path.exists():
                        history_path.unlink()
                    st.session_state.pop("chat_history", None)

                    # Step 3: Run Command 0.5 Edge Router first to dynamically re-compile the DAG
                    # This prunes Command 1 now that chapter_blueprint is written to disk
                    active_subject_name = st.session_state.get("active_subject", "Physics")
                    cmd_router = [
                        sys.executable,
                        "core_pipeline/command_0_5_router.py",
                        active_subject_name,
                        chapter_id
                    ]
                    subprocess.run(cmd_router, capture_output=True, text=True, check=True)

                    # Step 4: Run Orchestrator to execute Level 4 mining & forge pipelines (Commands 2-5.5)
                    # The orchestrator resolves the subject from the per-subject
                    # router_state.json that C0.5 just wrote, so it doesn't
                    # need --subject here. We still export HY_TUTOR_SUBJECT
                    # for safety so the orchestrator's fallbacks pick it up.
                    import os as _os_env
                    cmd_orch_env = _os_env.environ.copy()
                    cmd_orch_env["HY_TUTOR_SUBJECT"] = active_subject_name
                    cmd_orch = [
                        sys.executable,
                        "core_pipeline/orchestrator.py"
                    ]
                    subprocess.run(cmd_orch, capture_output=True, text=True, check=True, env=cmd_orch_env)

                    # Step 5: Refresh UI to load the newly forged chunk lesson and problems
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to transition to next chunk: {e}")
