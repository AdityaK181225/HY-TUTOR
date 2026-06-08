"""
HY-TUTOR: LEVEL 7 MAIN STREAMLIT WEB APP (app.py)
Target Hardware: Asus TUF F15 Laptop | OS: Zorin OS 18.1
Serves as the absolute presentation manager coordinating Level 1-6 pipelines.
Upgraded with persistent state syncing, PDF upload support, and chunk navigation.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
import streamlit as st

# ---------------------------------------------------------------------------
# 0. First-run wizard — collects GEMINI_API_KEY if it's not yet configured.
#    Runs BEFORE the page config and main render so a missing key never
#    leads to a confusing half-loaded app. Renders a styled setup panel
#    and st.stop()s the rest of the app until the key is saved.
# ---------------------------------------------------------------------------
from components.first_run_wizard import maybe_render_first_run_wizard  # noqa: E402
if maybe_render_first_run_wizard():
    st.stop()

# Configure Pristine Layout Parameters
st.set_page_config(
    page_title="HY-TUTOR",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 1. Load Optimization CSS stylesheet
css_path = Path("interface/assets/custom_style.css")
if css_path.exists():
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# 1b. Load Google Material Icons font (required for Streamlit's internal icons
#     like expander chevrons and popover indicators to render as graphics)
st.markdown(
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap"/>',
    unsafe_allow_html=True,
)

# Import Level 7 Visual Components safely
from components.sidebar import render_sidebar
from components.lesson_viewer import render_lesson_viewer
from components.chat_box import render_chat_box
from components.similar_problems import render_similar_problems
from components.recovery_panel import render_recovery_panel
from components.pipeline_runner import render_pipeline_runner
from components.settings_panel import (
    render_settings_popover,
    build_dynamic_css,
    load_settings as load_user_settings,
)


# ----------------------------------------------------
# 2a. Multifile Upload Concatenation Helper
# ----------------------------------------------------
# All HY-TUTOR intake slots (syllabus form, chapter form) accept
# multiple files per slot. To keep the downstream pipeline
# unchanged — it reads a single canonical file per source — we
# concatenate the uploaded files into one canonical .md at save
# time. Each file's contents are separated by a clear marker so
# the LLM in Command 0 / Command 1 can see file boundaries.
def _save_uploaded_files_concatenated(uploaded_files, dest_path: Path) -> int:
    """Concatenate a Streamlit multi-file uploader's contents into
    a single canonical text file at ``dest_path``.

    ``uploaded_files`` may be ``None``, a single ``UploadedFile``,
    or a list of ``UploadedFile`` objects. Returns the number of
    source files actually written (0 on a no-op).
    """
    if not uploaded_files:
        return 0
    # Streamlit's ``accept_multiple_files=True`` always returns a
    # list, but be defensive in case a single UploadedFile sneaks
    # through (e.g. from a legacy caller that didn't set the flag).
    if not isinstance(uploaded_files, list):
        uploaded_files = [uploaded_files]

    parts = []
    for f in uploaded_files:
        try:
            raw = f.read()
            text = raw.decode("utf-8", errors="replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
        except Exception:
            text = ""
        if not text.strip():
            continue
        parts.append(f"--- {f.name} ---\n\n{text.rstrip()}")

    if not parts:
        return 0

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "w", encoding="utf-8") as fh:
        fh.write("\n\n".join(parts) + "\n")
    return len(parts)

# ----------------------------------------------------
# 2. Absolute UI State Persistence Engine
# ----------------------------------------------------
# The ui_session.json is now stored per-subject under
# data_library/subject_workspaces/<subject>/ui_session.json. The
# helper ``_ui_state_path_for(subject)`` returns the correct path,
# falling back to the legacy flat path during the migration period.
def _ui_state_path_for(subject: str) -> Path:
    try:
        import sys
        if "core_pipeline" not in sys.path:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core_pipeline"))
        from utils.paths import SubjectPaths  # type: ignore
        return SubjectPaths.for_subject(subject).ui_session
    except Exception:
        return Path("data_library/active_workspace/ui_session.json")


def sync_ui_state():
    """Ensures Streamlit survives hard F5 browser refreshes by syncing to a local JSON cache.
    The cache is stored per-subject so each subject remembers its own state.
    """
    # A. If memory is blank, load from disk (try per-subject first, then legacy)
    if "active_subject" not in st.session_state:
        # Peek at the legacy flat file to discover the last-active subject
        legacy_file = Path("data_library/active_workspace/ui_session.json")
        discovered_subject = "Physics"
        if legacy_file.exists():
            try:
                with open(legacy_file, "r") as f:
                    disk_state = json.load(f)
                    discovered_subject = disk_state.get("active_subject", "Physics")
            except Exception:
                pass
        # Then try the per-subject file for that subject
        ui_state_file = _ui_state_path_for(discovered_subject)
        if ui_state_file.exists():
            try:
                with open(ui_state_file, "r") as f:
                    disk_state = json.load(f)
                    st.session_state["active_subject"] = disk_state.get("active_subject", "Physics")
                    st.session_state["ui_state"] = disk_state.get("ui_state", "INIT")
                    st.session_state["selected_chap_id"] = disk_state.get("selected_chap_id")
            except Exception:
                pass

    # B. Set structural defaults if still empty
    if "active_subject" not in st.session_state:
        st.session_state["active_subject"] = "Physics"
    if "ui_state" not in st.session_state:
        st.session_state["ui_state"] = "INIT"

    # C. Always mirror current session memory back to disk (per-subject)
    active_subject_for_save = (st.session_state.get("active_subject") or "Physics").strip().lower()
    ui_state_file = _ui_state_path_for(active_subject_for_save)
    state_payload = {
        "active_subject": st.session_state.get("active_subject"),
        "ui_state": st.session_state.get("ui_state"),
        "selected_chap_id": st.session_state.get("selected_chap_id")
    }
    ui_state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(ui_state_file, "w") as f:
        json.dump(state_payload, f)

    # Pin the ambient subject pointer so any downstream C-subprocess that
    # reads the pointer (rather than receiving --subject explicitly)
    # still resolves the right subject.
    try:
        from utils.paths import set_current_subject  # type: ignore
        set_current_subject(active_subject_for_save)
    except Exception:
        pass

# Execute the persistence wrapper immediately on script boot
sync_ui_state()

# Physical File Paths
SYLLABUS_FILE = Path("data_library/metadata/Master_Subject_Syllabus.json")
# Per-subject helpers for the TRIAGED / LEARNING branches below. These
# are computed lazily so the per-subject :class:`SubjectPaths` is only
# constructed on demand (the Streamlit boot phase is sensitive to import
# order, so we keep the heavy import local).
def _per_subject_paths(subject: str):
    try:
        import sys as _sys
        if "core_pipeline" not in _sys.path:
            _sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core_pipeline"))
        from utils.paths import SubjectPaths  # type: ignore
        return SubjectPaths.for_subject(subject)
    except Exception:
        # Migration fallback: legacy flat paths
        class _Legacy:
            def __init__(self, ws):
                self.workspace_dir = ws
                self.router_state = ws / "router_state.json"
                self.active_workspace = ws / "active_chapter_workspace.json"
        return _Legacy(Path("data_library/active_workspace"))


active_subject = st.session_state["active_subject"].lower()
# Resolve per-subject paths once (used in the TRIAGED / LEARNING branches).
# WORKSPACE_DIR and ROUTER_STATE_PATH are kept as module-level names so
# the rest of the file (TRIAGED + LEARNING branches) can keep using
# them unchanged, but they're now resolved per-subject via
# ``_per_subject_paths()`` above.
#
# Note: SubjectPaths exposes ``root`` (not ``workspace_dir``), so we
# bind the legacy module-level names to the per-subject equivalents
# here. The LEARNING branch uses ``SUBJECT_ACTIVE_WORKSPACE`` directly
# (a per-subject alias for ``active_chapter_workspace.json``).
_subject_paths = _per_subject_paths(active_subject)
ROUTER_STATE_PATH = _subject_paths.router_state
SUBJECT_ACTIVE_WORKSPACE = _subject_paths.active_workspace
# Backwards-compat alias for any branch that still expects the flat path.
WORKSPACE_DIR = Path("data_library/active_workspace")
# Convenience alias for the per-subject active_chapter_workspace.json
SUBJECT_ACTIVE_WORKSPACE = _subject_paths.active_workspace

# Check if Master Syllabus has active domain mapped
syllabus_data = {}
subject_exists = False
if SYLLABUS_FILE.exists():
    try:
        with open(SYLLABUS_FILE, "r", encoding="utf-8") as f:
            syllabus_data = json.load(f)
        if active_subject in syllabus_data:
            subject_exists = True
    except Exception:
        pass

# Inject global progress tracking widgets
render_sidebar()

# ----------------------------------------------------------------
# Top-bar: gear-icon settings popover (always visible, all states)
# ----------------------------------------------------------------
_hytutor_settings = load_user_settings()
st.markdown(build_dynamic_css(_hytutor_settings), unsafe_allow_html=True)
_topbar_l, _topbar_r = st.columns([0.92, 0.08])
with _topbar_r:
    render_settings_popover()
st.markdown("<hr style='margin: 4px 0 12px 0; border-color: #C8D0DC;'/>", unsafe_allow_html=True)

# State Machine Branching
if not subject_exists:
    # ----------------------------------------------------
    # BRANCH 1: Multi-File Markdown & PDF Upload Mode
    # ----------------------------------------------------
    st.title("📂 System Configuration Mode")
    st.markdown(f"Domain Matrix Error: Master Syllabus map for '{st.session_state['active_subject']}' is absent.")
    st.info("To proceed, please upload the core syllabus reference materials required by Command 0.")

    st.caption("📌 PDF intake coming soon — for now use .md or .txt exports. Multi-file uploads are supported; all files in a slot are concatenated into one canonical .md on save.")

    with st.form("syllabus_upload_form"):
        st.subheader("1. Ingestion File Upload Panels")
        col1, col2, col3 = st.columns(3)
        with col1:
            cbse_file = st.file_uploader(
                "1. CBSE Syllabus Guidelines (Mandatory) (.md/.txt)",
                type=["md", "txt"],
                accept_multiple_files=True,
                help="Define core scope, boundaries, and mandatory theoretical targets."
            )
        with col2:
            ncert_file = st.file_uploader(
                "2. NCERT TOC Index (Mandatory) (.md/.txt)",
                type=["md", "txt"],
                accept_multiple_files=True,
                help="Standard academic foundation table of contents."
            )
        with col3:
            ref_file = st.file_uploader(
                "3. Reference Book TOC (Mandatory) (.md/.txt)",
                type=["md", "txt"],
                accept_multiple_files=True,
                help="High-tier competitive shortcuts and advanced extensions."
            )
            exemplar_file = st.file_uploader(
                "4. Exemplar + Question Bank (Mandatory) (.md/.txt)",
                type=["md", "txt"],
                accept_multiple_files=True,
                help="NCERT Exemplar blueprints plus any additional question bank. Both are sources of problems/structure and are processed the same way."
            )

        submit_btn = st.form_submit_button("🔨 Map & Build Master Domain Syllabus")
        if submit_btn:
            if not cbse_file or not ncert_file or not ref_file or not exemplar_file:
                st.error("[HALT] Command 0 requires all four baseline files to build a valid master map: CBSE, NCERT TOC, Reference TOC, and Exemplar + Question Bank.")
            else:
                with st.spinner("Processing structural parsing loops..."):
                    cbse_dir = Path("data_library/raw_sources/cbse_guidelines") / active_subject
                    cbse_dir.mkdir(parents=True, exist_ok=True)

                    # Concatenate any number of uploaded files in each slot
                    # into the canonical .md filenames that Command 0 reads.
                    ccount = _save_uploaded_files_concatenated(cbse_file, cbse_dir / "cbse.md")
                    ncount = _save_uploaded_files_concatenated(ncert_file, cbse_dir / "ncert_toc.md")
                    rcount = _save_uploaded_files_concatenated(ref_file, cbse_dir / "reference_toc.md")
                    ecount = _save_uploaded_files_concatenated(exemplar_file, cbse_dir / "exemplar_toc.md")

                    if not ccount or not ncount or not rcount or not ecount:
                        st.error("[HALT] One or more source files were empty after concatenation. Please check your uploads and try again.")
                    else:
                        try:
                            cmd = [sys.executable, "core_pipeline/command_0_syllabus.py", st.session_state["active_subject"]]
                            subprocess.run(cmd, capture_output=True, text=True, check=True)
                            st.success(f"Master Syllabus built successfully! Merged {ccount} CBSE, {ncount} NCERT TOC, {rcount} reference, and {ecount} exemplar files.")
                            st.session_state["ui_state"] = "SYLLABUS_REVIEW"
                            sync_ui_state()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Syllabus engine crashed: {e}")

else:
    # ----------------------------------------------------
    # BRANCH 1.5: Syllabus Review & Edit Mode
    # ----------------------------------------------------
    chapters_dict = syllabus_data[active_subject].get("chapters", {})
    
    if st.session_state["ui_state"] == "SYLLABUS_REVIEW":
        st.title("📋 Review & Finalize Domain Syllabus")
        st.markdown("Command 0 has compiled the blueprint. Review the deep-research mappings below. You can chat with the Architect to make modifications before confirming.")
        
        with st.container(height=500):
            for chap_id, chap_data in chapters_dict.items():
                with st.expander(f"📖 {chap_id}: {chap_data.get('chapter_name', 'Unnamed Chapter')}", expanded=False):
                    prereqs = chap_data.get("cross_grade_prerequisites", [])
                    if prereqs:
                        st.markdown("**🔗 Cross-Grade Prerequisites:**")
                        for req in prereqs:
                            st.markdown(f"- *{req.get('chapter_id', 'ID')}*: **{req.get('topic', 'Topic')}** ➔ {req.get('critical_for', 'Reason')}")
                    else:
                        st.markdown("**🔗 Cross-Grade Prerequisites:** None")
                    
                    st.markdown("---")
                    st.markdown("**🧠 Atomic Chunks:**")
                    
                    chunks = chap_data.get("atomic_chunks", [])
                    for chunk in chunks:
                        st.markdown(f"##### Chunk {chunk.get('chunk_index', 0)}: {chunk.get('topic', 'Topic')}")
                        st.markdown(f"**🎯 Competitive Focus:** *{chunk.get('competitive_track_focus', 'N/A')}*")
                        
                        milestones = chunk.get("core_milestones", [])
                        if milestones:
                            st.markdown("**📍 Core Milestones:**")
                            for ms in milestones:
                                st.markdown(f"  - {ms}")
                                
                        profile = chunk.get("execution_profile", {})
                        if profile:
                            st.markdown("**⚙️ Execution Profile Flags:**")
                            flags_str = ", ".join([f"`{k}: {v}`" for k, v in profile.items()])
                            st.markdown(f"  - {flags_str}")
                            
                        st.markdown("<br>", unsafe_allow_html=True)
        
        st.markdown("### 💬 Architect Modification Chat")
        col_edit_input, col_edit_btn = st.columns([0.88, 0.12])
        with col_edit_input:
            user_prompt = st.text_area(
                "Request changes (e.g., 'Add more detail to the chunk on organic mechanisms')",
                placeholder="Describe the modifications you want to the syllabus...",
                height=100,
                label_visibility="collapsed",
                key="syllabus_edit_input",
            )
        with col_edit_btn:
            st.markdown("<div style='padding-top: 0px;'></div>", unsafe_allow_html=True)
            edit_btn = st.button("➤ Submit", key="syllabus_edit_send", use_container_width=True,
                                  help="Submit modification request")

        st.caption("💡 *Enter = new line • Button or Ctrl+Enter = send*")

        if edit_btn and user_prompt and user_prompt.strip():
            with st.spinner("Re-compiling syllabus structure via Command 0.1..."):
                try:
                    clean_prompt = user_prompt.strip()
                    cmd = [
                        sys.executable,
                        "core_pipeline/command_0_1_editor.py",
                        st.session_state["active_subject"],
                        clean_prompt,
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    st.success("Syllabus updated successfully!")
                    st.rerun()
                except subprocess.CalledProcessError as e:
                    detail = (e.stderr or e.stdout or "").strip()
                    st.error(f"Syllabus editor failed (exit {e.returncode}). {detail[:400]}")
                except Exception as e:
                    st.error(f"Syllabus editor crashed: {e}")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✅ Confirm Syllabus & Proceed to Study Dashboard", type="primary", use_container_width=True):
            st.session_state["ui_state"] = "SELECTION"
            sync_ui_state()
            st.rerun()

    # ----------------------------------------------------
    # BRANCH 2: Study Selection & Active Learning Dashboard
    # ----------------------------------------------------
    elif st.session_state["ui_state"] in ["INIT", "SELECTION"]:
        st.title("🏫 Study Session Planner")
        st.markdown(f"Master Syllabus for {st.session_state['active_subject']} is loaded and ready.")
        
        if st.button("🔍 Review/Edit Master Syllabus"):
            st.session_state["ui_state"] = "SYLLABUS_REVIEW"
            sync_ui_state()
            st.rerun()

        chapter_ids = list(chapters_dict.keys())
        selected_chap_id = st.selectbox(
            "Select Chapter Node:",
            chapter_ids,
            format_func=lambda x: f"{x}: {chapters_dict[x].get('chapter_name')}"
        )
        
        st.markdown("---")
        if st.button("🚀 Run Pre-Flight Route Triage"):
            try:
                cmd = [sys.executable, "core_pipeline/command_0_5_router.py", active_subject, selected_chap_id]
                subprocess.run(cmd, check=True)
                st.session_state["selected_chap_id"] = selected_chap_id
                st.session_state["ui_state"] = "TRIAGED"
                sync_ui_state()
                st.rerun()
            except Exception as e:
                st.error(f"Edge Routing Loop crashed: {e}")

    elif st.session_state["ui_state"] == "TRIAGED":
        if ROUTER_STATE_PATH.exists():
            with open(ROUTER_STATE_PATH, "r", encoding="utf-8") as f:
                route_data = json.load(f)
            
            active_state = route_data.get("active_state")
            chap_id = st.session_state["selected_chap_id"]

            if active_state == "STATE_B":
                st.title("🔒 Prerequisite Lockout Active")
                blocker = route_data.get("blocking_prerequisite", {})
                st.warning(f"Access Blocked: Studying {chap_id} requires prerequisite understanding of {blocker.get('topic', blocker.get('chapter_id'))}.")
                st.markdown("If you have studied this topic previously, you can submit an active conversational override to bypass this blockade.")
                
                col_ov_input, col_ov_btn = st.columns([0.88, 0.12])
                with col_ov_input:
                    override_text = st.text_area(
                        "Provide details of your competency (e.g., 'I know this concept')",
                        placeholder="Describe your prior knowledge of this prerequisite topic...",
                        height=100,
                        label_visibility="collapsed",
                        key="override_input",
                    )
                with col_ov_btn:
                    st.markdown("<div style='padding-top: 0px;'></div>", unsafe_allow_html=True)
                    submit_override = st.button("➤ Submit", key="override_send", use_container_width=True,
                                                  help="Submit competency verification")

                st.caption("💡 *Enter = new line • Button or Ctrl+Enter = send*")

                if submit_override and override_text and override_text.strip():
                    with st.spinner("Prerequisite assessment loop executing..."):
                        try:
                            cmd = [
                                sys.executable,
                                "core_pipeline/command_0_5_router.py",
                                active_subject,
                                chap_id,
                                "--chat",
                                override_text
                            ]
                            subprocess.run(cmd, check=True)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Override evaluation faulted: {e}")
                            
                if st.button("⬅️ Return to Dashboard"):
                    st.session_state["ui_state"] = "SELECTION"
                    sync_ui_state()
                    st.rerun()

            else:
                st.title("📖 Chapter Resource Status")
                
                # Check for either markdown or text files in the staging area
                ncert_dir = Path("data_library/raw_sources/ncert_textbooks") / active_subject
                assets_missing = True
                if ncert_dir.exists():
                    for ext in [".md", ".txt"]:
                        if (ncert_dir / f"{chap_id}{ext}").exists():
                            assets_missing = False
                            break
                
                if assets_missing:
                    st.warning(f"📥 Heavy textbook content for chapter {chap_id} is missing.")
                    st.markdown("Please upload the core chapter content below to launch Level 4 mining pipelines.")

                    st.caption("📌 PDF intake coming soon — for now use .md or .txt exports. Multi-file uploads are supported; all files in a slot are concatenated into one canonical .md on save.")

                    with st.form("chapter_assets_upload_form"):
                        st.subheader(f"Upload Materials for {chap_id}: {chapters_dict.get(chap_id, {}).get('chapter_name', '')}")

                        up_ncert = st.file_uploader(
                            "1. Core NCERT Chapter Text (Mandatory) (.md/.txt)",
                            type=["md", "txt"],
                            accept_multiple_files=True,
                            help="Provide the baseline standard textbook text. Upload multiple files to merge sub-chapters into one canonical text."
                        )
                        up_ref = st.file_uploader(
                            "2. Reference Manual Chapter Text (Mandatory) (.md/.txt)",
                            type=["md", "txt"],
                            accept_multiple_files=True,
                            help="Upload any split sub-chapters together; they will be concatenated into one canonical file."
                        )
                        up_ex = st.file_uploader(
                            "3. Exemplar + Question Bank (Mandatory) (.md/.txt)",
                            type=["md", "txt"],
                            accept_multiple_files=True,
                            help="NCERT Exemplar problems and any additional question bank. Both are sources of practice problems and are processed the same way."
                        )

                        save_assets = st.form_submit_button("🚀 Upload & Stage Chapter Content")

                        if save_assets:
                            if not up_ncert or not up_ref or not up_ex:
                                st.error("[HALT] All three source slots are mandatory: Core NCERT, Reference Manual, and Exemplar + Question Bank.")
                            else:
                                with st.spinner("Staging textbook assets to secure directories..."):
                                    ncert_dir = Path("data_library/raw_sources/ncert_textbooks") / active_subject
                                    ref_dir = Path("data_library/raw_sources/reference_manuals") / active_subject
                                    ex_dir = Path("data_library/raw_sources/ncert_exemplars") / active_subject

                                    for d in [ncert_dir, ref_dir, ex_dir]:
                                        d.mkdir(parents=True, exist_ok=True)

                                    ncount = _save_uploaded_files_concatenated(up_ncert, ncert_dir / f"{chap_id}.md")
                                    rcount = _save_uploaded_files_concatenated(up_ref, ref_dir / f"{chap_id}.md")
                                    ecount = _save_uploaded_files_concatenated(up_ex, ex_dir / f"{chap_id}.md")

                                    st.success(f"Staged successfully! Merged {ncount} NCERT, {rcount} reference, and {ecount} exemplar files. Re-triaging state...")
                                    st.rerun()

                    if st.button("⬅️ Cancel & Return"):
                        st.session_state["ui_state"] = "SELECTION"
                        sync_ui_state()
                        st.rerun()
                else:
                    st.info("Files Verified. Standby while the Orchestrator prepares Unified Lesson plans and question variants.")
                    st.markdown(f"Target: {chap_id} | Path: {active_state}")
                    
                    if st.button("🔥 Execute Deep Learning Compilation"):
                        st.session_state["ui_state"] = "PIPELINE_RUNNING"
                        st.session_state["pipeline_status"] = {}
                        st.session_state["pipeline_finished"] = False
                        sync_ui_state()
                        st.rerun()
                                 
                    if st.button("🔄 Reset Selection"):
                        st.session_state["ui_state"] = "SELECTION"
                        sync_ui_state()
                        st.rerun()

    # ----------------------------------------------------
    # BRANCH 2.5: Pipeline Runner (Individual Command Execution)
    # ----------------------------------------------------
    elif st.session_state["ui_state"] == "PIPELINE_RUNNING":
        chap_id = st.session_state.get("selected_chap_id", "")
        
        def _on_pipeline_complete():
            st.session_state["ui_state"] = "LEARNING"
            sync_ui_state()
        
        render_pipeline_runner(
            chapter_id=chap_id,
            subject=active_subject,
            on_complete=_on_pipeline_complete,
        )
    
    # ----------------------------------------------------
    # BRANCH 3: Splitted Socratic Study Dashboard
    # ----------------------------------------------------
    elif st.session_state["ui_state"] == "LEARNING":
        chap_id = st.session_state["selected_chap_id"]

        # Read the active chunk index from the per-subject active
        # workspace file (data_library/subject_workspaces/<subject>/
        # active_chapter_workspace.json). Fall back to the legacy flat
        # path during the migration period.
        active_chunk_idx = 0
        cache_path = SUBJECT_ACTIVE_WORKSPACE
        if not cache_path.exists():
            cache_path = WORKSPACE_DIR / "active_chapter_workspace.json"
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    c_data = json.load(f)
                active_chunk_idx = c_data.get("current_active_chunk_index", 0)
            except Exception:
                pass

        # === 🧭 Interactive Chunk Navigation Bar ===
        st.markdown("### 🧭 Interactive Study Navigation")
        col_nav1, col_nav2, col_nav3 = st.columns(3)
        
        with col_nav1:
            if st.button("⏪ Previous Chunk", use_container_width=True):
                with st.spinner("Rewinding conceptual state and re-compiling..."):
                    cmd = [sys.executable, "core_pipeline/orchestrator.py", "--nav", "previous", "--chapter", chap_id, "--subject", active_subject]
                    subprocess.run(cmd, check=True)
                    st.rerun()
                    
        with col_nav2:
            if st.button("🔄 Reset Chapter Progress", use_container_width=True):
                with st.spinner("Clearing local progress. Resetting to Chunk 0..."):
                    cmd = [sys.executable, "core_pipeline/orchestrator.py", "--nav", "reset", "--chapter", chap_id, "--subject", active_subject]
                    subprocess.run(cmd, check=True)
                    st.rerun()
                    
        with col_nav3:
            if st.button("🚪 Exit to Dashboard", use_container_width=True):
                st.session_state["ui_state"] = "SELECTION"
                sync_ui_state()
                st.rerun()

        st.markdown("---")

        # Split screen viewport layout (Left: Lesson / Right: Tutor Chat)
        col_left, col_right = st.columns([0.55, 0.45])
        with col_left:
            render_lesson_viewer()
        with col_right:
            render_chat_box(chap_id, active_chunk_idx)

        # Similar Problems Finder (below the split view)
        render_similar_problems(
            subject=active_subject,
            chapter_id=chap_id,
        )

        # Recovery Panel (bottom of learning dashboard)
        render_recovery_panel(subject=active_subject)
