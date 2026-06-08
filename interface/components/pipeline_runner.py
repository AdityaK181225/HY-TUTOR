"""
HY-TUTOR: Pipeline Runner Component
Replaces the monolithic orchestrator subprocess with individual command execution,
providing real-time progress tracking and per-command re-run capability.
"""

import os
import re
import sys
import json
import time
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Any, Optional

import streamlit as st

# ============================================================================
# PROJECT-ROOT PATH BOOTSTRAP
# ============================================================================
# This module is loaded early in the Streamlit boot sequence. The command
# scripts inside ``core_pipeline/`` import their helpers via the flat name
# (``utils.paths``, not ``core_pipeline.utils.paths``), which only works
# when ``core_pipeline/`` itself is on ``sys.path``. ``app.py`` injects
# that path lazily, *after* this module is imported, so we set it up here
# at import time to avoid a brittle ordering dependency. This mirrors
# the defensive pattern used in ``interface/app.py`` for the same reason.
_PROJECT_ROOT_FOR_PATHS = Path(__file__).resolve().parent.parent.parent
_CORE_PIPELINE_DIR_FOR_PATHS = _PROJECT_ROOT_FOR_PATHS / "core_pipeline"
if str(_CORE_PIPELINE_DIR_FOR_PATHS) not in sys.path:
    sys.path.insert(0, str(_CORE_PIPELINE_DIR_FOR_PATHS))

# ============================================================================
# COMMAND REGISTRY — maps script names to metadata and output files
# ============================================================================

COMMAND_REGISTRY: Dict[str, Dict[str, Any]] = {
    "command_1_blueprint.py": {
        "name": "📐 Blueprint Generation",
        "description": "Build chapter-level structural blueprint from syllabus",
        "timeout": 900,
        "needs_chunk_index": False,
        "output_files": [],  # Blueprint uses chapter-level file, handled separately
        "blueprint_output": True,  # Special: creates chapter_blueprint_{chap}.json
    },
    "command_2_miner.py": {
        "name": "⛏️ NCERT Extraction",
        "description": "Extract and parse chunk content from NCERT textbook",
        "timeout": 600,
        "needs_chunk_index": True,
        "output_files": ["NCERT_chunk.json"],
    },
    "command_3_optimizer.py": {
        "name": "🔧 Reference Optimization",
        "description": "Optimize extracted content against reference materials",
        "timeout": 900,
        "needs_chunk_index": True,
        "output_files": ["Reference_chunk.json"],
    },
    "command_4_bridge.py": {
        "name": "🌉 Bridge Synthesis",
        "description": "Synthesize cross-reference bridge between sources",
        "timeout": 600,
        "needs_chunk_index": True,
        "output_files": ["Bridge_chunk.json"],
    },
    "command_5_5_injector.py": {
        "name": "💉 Exemplar Injection",
        "description": "Inject NCERT exemplar problems into the pipeline",
        "timeout": 900,
        "needs_chunk_index": True,
        "output_files": ["Active_Chunk_Problems.json"],
    },
    "command_5_forge.py": {
        "name": "🔥 Lesson Forge",
        "description": "Forge unified lesson document from all sources",
        "timeout": 600,
        "needs_chunk_index": True,
        "output_files": ["Unified_Lesson.md"],
    },
}

# ============================================================================
# FILE PATHS  (resolved per-subject inside render_pipeline_runner)
# ============================================================================

# The legacy flat paths are kept as imports for the integrity scan in
# _render_status_panel / _cleanup_command_files, but the actual data
# I/O is now done via per-subject paths. See SubjectPaths below.
import os as _os
_PROJECT_ROOT = Path(__file__).parent.parent.parent

# Lazy import to avoid a hard import-cycle when the package is imported
# during the Streamlit boot phase before the venv is fully initialised.
def _paths_for(subject: str):
    """Resolve the per-subject :class:`SubjectPaths` for ``subject``."""
    from utils.paths import SubjectPaths  # type: ignore
    # ``core_pipeline/`` is added to ``sys.path`` at import time by the
    # bootstrap block at the top of this module, so the flat
    # ``utils.paths`` import resolves correctly regardless of whether
    # ``app.py`` has run its own path injection yet.
    return SubjectPaths.for_subject(subject)


# ============================================================================
# STATUS CONSTANTS
# ============================================================================

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"


# ============================================================================
# ERROR DIAGNOSIS ENGINE
# ============================================================================

# Pattern-based error classification rules (ordered by priority)
_ERROR_PATTERNS: List[Dict[str, Any]] = [
    {
        "patterns": [r"429", r"RESOURCE_EXHAUSTED", r"rate.?limit", r"quota"],
        "category": "API_ERROR",
        "icon": "🚦",
        "title": "Rate Limit Exceeded",
        "explanation": (
            "The Google Gemini API rejected the request because too many API calls "
            "were made in a short period, or your daily quota has been reached."
        ),
        "actions": [
            "Wait 1–2 minutes, then click **🔄 Re-run** on the failed command.",
            "Check your API quota and billing at [Google AI Studio](https://aistudio.google.com/app/apikey).",
            "If this keeps happening, consider upgrading your API plan or reducing request frequency.",
        ],
    },
    {
        "patterns": [r"403", r"PERMISSION_DENIED", r"forbidden"],
        "category": "CONFIG_ERROR",
        "icon": "🔑",
        "title": "API Access Denied",
        "explanation": (
            "Your API key does not have permission to access the requested model or resource. "
            "The key may have been revoked or restricted."
        ),
        "actions": [
            "Go to [Google AI Studio](https://aistudio.google.com/app/apikey) and verify your key is active.",
            "Regenerate a new API key if the current one has been deleted.",
            "Update the key in `config/.env` → `GEMINI_API_KEY=your_new_key`.",
        ],
    },
    {
        "patterns": [r"400", r"INVALID_ARGUMENT", r"bad.?request"],
        "category": "API_ERROR",
        "icon": "📝",
        "title": "Invalid Request to API",
        "explanation": (
            "The API rejected the request due to an invalid argument. This can happen if the "
            "prompt is too long, uses unsupported features, or the model doesn't support the request format."
        ),
        "actions": [
            "Try re-running — it may be a transient issue.",
            "Check if the input chapter content is very large and consider splitting it.",
            "The pipeline's model fallback chain should handle this automatically on retry.",
        ],
    },
    {
        "patterns": [r"500", r"501", r"502", r"503", r"INTERNAL", r"UNAVAILABLE", r"SERVICE_UNAVAILABLE", r"server.?error"],
        "category": "API_ERROR",
        "icon": "🔧",
        "title": "Google API Server Error",
        "explanation": (
            "The Google Gemini API encountered an internal server error. This is a temporary "
            "issue on Google's side and is not caused by anything in your configuration."
        ),
        "actions": [
            "Wait 2–5 minutes, then click **🔄 Re-run** on the failed command.",
            "Check [Google Cloud Status](https://status.cloud.google.com/) for ongoing incidents.",
            "The pipeline's fallback models may also help — retrying will try the next model in the chain.",
        ],
    },
    {
        "patterns": [r"timed?\s*out", r"TimeoutExpired", r"timeout"],
        "category": "TIMEOUT",
        "icon": "⏱️",
        "title": "Command Timed Out",
        "explanation": (
            "The pipeline command took longer than the allowed time limit and was forcibly stopped. "
            "This usually means the AI model took too long to generate a response, or the input "
            "content was very large."
        ),
        "actions": [
            "Click **🔄 Re-run** — the timeout may have been a one-time slowdown.",
            "Check your internet connection speed — slow networks can cause API delays.",
            "If this happens repeatedly, the input content may need to be split into smaller chunks.",
        ],
    },
    {
        "patterns": [r"GEMINI_API_KEY\s+not\s+found", r"GEMINI_API_KEY.*missing", r"GEMINI_API_KEY.*empty"],
        "category": "CONFIG_ERROR",
        "icon": "❌",
        "title": "Missing API Key",
        "explanation": (
            "The `GEMINI_API_KEY` environment variable is not set. The pipeline cannot connect "
            "to the Google Gemini API without a valid key."
        ),
        "actions": [
            "Get a free API key from [Google AI Studio](https://aistudio.google.com/app/apikey).",
            "Open `config/.env` and add: `GEMINI_API_KEY=your_key_here`.",
            "Save the file and click **🔄 Re-run** on the failed command.",
        ],
    },
    {
        "patterns": [r"ollama", r"localhost:11434", r"connection refused.*ollama"],
        "category": "CONFIG_ERROR",
        "icon": "🦙",
        "title": "Local Ollama Server Unavailable",
        "explanation": (
            "The local Ollama inference server is not running or not reachable. The pipeline "
            "uses Ollama as a fallback when cloud API models are unavailable."
        ),
        "actions": [
            "Start Ollama by running `ollama serve` in a terminal.",
            "Ensure Ollama is installed: `ollama --version`.",
            "If you don't need local fallback, the pipeline will still work with just the cloud API.",
        ],
    },
    {
        "patterns": [r"No such file", r"FileNotFoundError", r"file.*not found", r"does not exist"],
        "category": "CONFIG_ERROR",
        "icon": "📂",
        "title": "Missing Input File",
        "explanation": (
            "A required input file was not found on disk. The pipeline cannot proceed without "
            "the necessary source materials."
        ),
        "actions": [
            "Go back to the Chapter Resource Status page and upload the required content.",
            "Ensure the chapter content files (NCERT textbook, etc.) are in the correct location.",
            "Check `data_library/raw_sources/` for the expected files.",
        ],
    },
    {
        "patterns": [r"ModuleNotFoundError", r"import.*error", r"module.*not found"],
        "category": "CONFIG_ERROR",
        "icon": "📦",
        "title": "Missing Python Package",
        "explanation": (
            "A required Python module is not installed. The pipeline depends on several "
            "packages that must be installed before running."
        ),
        "actions": [
            "Run: `pip install -r requirements.txt` from the project root.",
            "Ensure you're using the correct virtual environment (`.venv`).",
            "Restart the Streamlit server after installing packages.",
        ],
    },
    {
        "patterns": [r"SSL", r"ssl.*error", r"certificate", r"CERTIFICATE_VERIFY_FAILED"],
        "category": "CONFIG_ERROR",
        "icon": "🔒",
        "title": "SSL/TLS Certificate Error",
        "explanation": (
            "A secure connection to the API could not be established due to a certificate "
            "issue. This is often caused by corporate firewalls or proxy configurations."
        ),
        "actions": [
            "Check your internet connection and try again.",
            "If behind a corporate proxy, configure your proxy settings.",
            "Try: `pip install --upgrade certifi` to update certificate bundles.",
        ],
    },
]


def _diagnose_error(stderr: str, stdout: str = "") -> Dict[str, Any]:
    """
    Analyze error output and return a structured, user-friendly diagnosis.
    
    Args:
        stderr: Standard error output from the failed command
        stdout: Standard output (may contain relevant error info too)
        
    Returns:
        Dict with keys: title, explanation, category, icon, actions, raw_error
    """
    combined = f"{stderr} {stdout}".lower()
    
    for rule in _ERROR_PATTERNS:
        for pattern in rule["patterns"]:
            if re.search(pattern, combined, re.IGNORECASE):
                return {
                    "title": rule["title"],
                    "explanation": rule["explanation"],
                    "category": rule["category"],
                    "icon": rule["icon"],
                    "actions": rule["actions"],
                    "raw_error": stderr[:1000] if stderr else stdout[:1000],
                }
    
    # No known pattern matched — provide a generic but helpful diagnosis
    return {
        "title": "Unexpected Error",
        "explanation": (
            "The pipeline encountered an error that doesn't match any known failure patterns. "
            "The raw error output below may help identify the issue."
        ),
        "category": "UNKNOWN",
        "icon": "❓",
        "actions": [
            "Click **🔄 Re-run** to try again — it may be a transient issue.",
            "Expand the raw error log below and look for specific error messages.",
            "If the error persists, check the terminal output where Streamlit is running.",
        ],
        "raw_error": stderr[:1000] if stderr else stdout[:1000],
    }


def _render_error_diagnosis(diagnosis: Dict[str, Any], key_prefix: str = "main"):
    """
    Render a prominent error diagnosis box using Streamlit components.
    
    Args:
        diagnosis: Output from _diagnose_error()
        key_prefix: Unique prefix for widget keys
    """
    icon = diagnosis["icon"]
    title = diagnosis["title"]
    category = diagnosis["category"]
    explanation = diagnosis["explanation"]
    actions = diagnosis["actions"]
    raw_error = diagnosis.get("raw_error", "")
    
    # Category badge
    cat_badges = {
        "API_ERROR": "🌐 API Error",
        "CONFIG_ERROR": "⚙️ Configuration Error",
        "TIMEOUT": "⏱️ Timeout",
        "UNKNOWN": "❓ Unknown Error",
    }
    cat_badge = cat_badges.get(category, category)
    
    # Main warning container
    st.warning(f"### {icon} Pipeline Failure: {title}")
    st.caption(f"Category: **{cat_badge}**")
    
    # Explanation
    st.markdown(f"**What happened:** {explanation}")
    
    # Action steps
    st.markdown("**How to fix it:**")
    for i, action in enumerate(actions, 1):
        st.markdown(f"  {i}. {action}")
    
    # Raw error log (collapsed by default)
    if raw_error:
        # Truncate very long errors
        display_error = raw_error
        if len(display_error) > 1500:
            display_error = display_error[:750] + "\n\n... (truncated) ...\n\n" + display_error[-750:]
        
        with st.expander("📋 Raw Error Log (for debugging)", expanded=False):
            st.code(display_error, language=None)


# ============================================================================
# CORE FUNCTIONS
# ============================================================================

def _get_pipeline_status() -> Dict[str, Dict[str, Any]]:
    """Retrieve pipeline status from session state."""
    return st.session_state.get("pipeline_status", {})


def _set_pipeline_status(status: Dict[str, Dict[str, Any]]):
    """Persist pipeline status to session state."""
    st.session_state["pipeline_status"] = status


def _initialize_pipeline_status(execution_path: List[str]) -> Dict[str, Dict[str, Any]]:
    """Create initial status entries for each command in the execution path."""
    status = {}
    for script_name in execution_path:
        if script_name == "command_6_tutor.py":
            continue  # Tutor is handled by UI, not pipeline runner
        status[script_name] = {
            "state": STATUS_PENDING,
            "started_at": None,
            "completed_at": None,
            "duration_seconds": None,
            "stdout": "",
            "stderr": "",
            "return_code": None,
        }
    return status


def _cleanup_command_files(script_name: str, chapter_id: str, chunk_index: int, subject: str):
    """
    Delete output files produced by a specific command so it can be cleanly re-generated.
    Operates on per-subject paths.

    Note on the blueprint backup (``chapter_blueprint_<id>.json``):
        We intentionally do NOT delete the backup file here. The C1
        command's self-heal path can re-derive the backup from the
        active workspace in O(1) if the active workspace is intact, so
        wiping the backup only widens the window in which a partial
        re-run could leave the UI showing a "🔴 failed" blueprint
        even though the underlying data is still good. The active
        workspace is the single source of truth; the backup is just
        a redundant copy.
    """
    meta = COMMAND_REGISTRY.get(script_name, {})
    paths = _paths_for(subject)

    # Blueprint backup is intentionally preserved (see docstring above).

    # Clean chunk-level output files
    chunk_paths = paths.chunk_paths()
    for filename in meta.get("output_files", []):
        # Some filenames contain dynamic chapter/chunk references
        file_path = chunk_paths.get(
            _chunk_key_for_filename(filename), chunk_paths["ncert"].parent / filename
        )
        if file_path.exists():
            file_path.unlink()


def _chunk_key_for_filename(filename: str) -> str:
    """Map a chunk-filename to its :class:`SubjectPaths.chunk_paths` key."""
    mapping = {
        "NCERT_chunk.json": "ncert",
        "Reference_chunk.json": "reference",
        "Bridge_chunk.json": "bridge",
        "Active_Chunk_Problems.json": "problems",
        "Unified_Lesson.md": "lesson",
    }
    return mapping.get(filename, "")


def _run_single_command(
    script_name: str, chapter_id: str, chunk_index: int, subject: str
) -> tuple[bool, str, str]:
    """
    Execute a single pipeline command via subprocess. Always forwards
    ``--subject <subject>`` so the subprocess can resolve per-subject
    paths independently of the ambient pointer.
    Returns (success, stdout, stderr).
    """
    meta = COMMAND_REGISTRY.get(script_name, {})
    timeout = meta.get("timeout", 600)

    script_path = _PROJECT_ROOT / "core_pipeline" / script_name
    cmd = [sys.executable, str(script_path), "--subject", subject]

    if meta.get("needs_chunk_index", True):
        cmd.extend([chapter_id, str(chunk_index)])
    else:
        cmd.append(chapter_id)

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return True, result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired:
        return False, "", f"Command timed out after {timeout} seconds"
    except subprocess.CalledProcessError as e:
        return False, e.stdout or "", e.stderr or f"Return code: {e.returncode}"
    except Exception as e:
        return False, "", str(e)


# ============================================================================
# UI RENDERING
# ============================================================================

def _render_status_badge(state: str) -> str:
    """Return an HTML badge for a given pipeline state."""
    badges = {
        STATUS_PENDING: "⏸️ Pending",
        STATUS_RUNNING: "⏳ Running...",
        STATUS_COMPLETED: "✅ Completed",
        STATUS_FAILED: "❌ Failed",
        STATUS_SKIPPED: "⏭️ Skipped",
    }
    return badges.get(state, "❓ Unknown")


def _render_single_node(
    script_name: str,
    node_status: Dict[str, Any],
    chapter_id: str,
    chunk_index: int,
    is_current: bool,
    pipeline_finished: bool,
    subject: str,
):
    """Render a single DAG node with status and re-run capability."""
    meta = COMMAND_REGISTRY.get(script_name, {})
    display_name = meta.get("name", script_name)
    description = meta.get("description", "")
    state = node_status.get("state", STATUS_PENDING)
    paths = _paths_for(subject)
    chunk_paths = paths.chunk_paths()

    # Build the expander label
    badge = _render_status_badge(state)
    duration_str = ""
    if node_status.get("duration_seconds") is not None:
        duration_str = f" ({node_status['duration_seconds']:.1f}s)"

    label = f"{badge} — **{display_name}**{duration_str}"

    with st.expander(label, expanded=(state == STATUS_RUNNING or (is_current and state == STATUS_PENDING))):
        # Description
        st.caption(description)

        # Show output files (per-subject paths)
        output_files = meta.get("output_files", [])
        if meta.get("blueprint_output"):
            output_files = [f"chapter_blueprint_{chapter_id}.json"] + output_files

        if output_files:
            files_info = []
            for fname in output_files:
                if meta.get("blueprint_output") and fname.startswith("chapter_blueprint"):
                    fpath = paths.blueprint_path(chapter_id)
                else:
                    chunk_key = _chunk_key_for_filename(fname)
                    if chunk_key and chunk_key in chunk_paths:
                        fpath = chunk_paths[chunk_key]
                    else:
                        fpath = paths.chunk_dir / fname
                exists = fpath.exists()
                icon = "🟢" if exists else "🔴"
                files_info.append(f"{icon} `{fname}`")
            st.markdown(" ".join(files_info))

        # Show error diagnosis if failed
        if state == STATUS_FAILED and (node_status.get("stderr") or node_status.get("stdout")):
            diagnosis = _diagnose_error(
                node_status.get("stderr", ""),
                node_status.get("stdout", ""),
            )
            st.warning(f"**{diagnosis['icon']} {diagnosis['title']}**")
            st.caption(diagnosis["explanation"])
            for i, action in enumerate(diagnosis["actions"], 1):
                st.markdown(f"  {i}. {action}")
            if diagnosis.get("raw_error"):
                raw = diagnosis["raw_error"]
                if len(raw) > 500:
                    raw = "..." + raw[-500:]
                with st.expander("📋 Raw Error", expanded=False):
                    st.code(raw, language=None)

        # Show stdout snippet if completed and has output
        if state == STATUS_COMPLETED and node_status.get("stdout"):
            stdout_preview = node_status["stdout"]
            # Show last 500 chars of stdout (most relevant info)
            if len(stdout_preview) > 500:
                stdout_preview = "..." + stdout_preview[-500:]
            with st.expander("📋 Command Output", expanded=False):
                st.code(stdout_preview, language=None)

        # Re-run button — available when command is completed or failed, and pipeline is done
        if pipeline_finished and state in (STATUS_COMPLETED, STATUS_FAILED):
            if st.button(
                f"🔄 Re-run {display_name}",
                key=f"rerun_{script_name}",
                use_container_width=True,
            ):
                _execute_rerun(script_name, chapter_id, chunk_index, subject)


def _execute_rerun(script_name: str, chapter_id: str, chunk_index: int, subject: str):
    """Handle re-running a single command: cleanup → execute → update status."""
    meta = COMMAND_REGISTRY.get(script_name, {})
    display_name = meta.get("name", script_name)

    # 1. Cleanup old output files (per-subject)
    _cleanup_command_files(script_name, chapter_id, chunk_index, subject)

    # 2. Update status to running
    status = _get_pipeline_status()
    if script_name in status:
        status[script_name] = {
            "state": STATUS_RUNNING,
            "started_at": time.time(),
            "completed_at": None,
            "duration_seconds": None,
            "stdout": "",
            "stderr": "",
            "return_code": None,
        }
        _set_pipeline_status(status)

    # 3. Execute (forwards --subject to the subprocess)
    success, stdout, stderr = _run_single_command(script_name, chapter_id, chunk_index, subject)

    # 4. Update status
    elapsed = time.time() - (status[script_name].get("started_at") or time.time())
    status = _get_pipeline_status()
    if script_name in status:
        status[script_name] = {
            "state": STATUS_COMPLETED if success else STATUS_FAILED,
            "started_at": status[script_name].get("started_at"),
            "completed_at": time.time(),
            "duration_seconds": elapsed,
            "stdout": stdout,
            "stderr": stderr,
            "return_code": 0 if success else 1,
        }
        _set_pipeline_status(status)

    if success:
        st.success(f"✅ {display_name} completed successfully ({elapsed:.1f}s)")
    else:
        st.error(f"❌ {display_name} failed: {stderr[:300]}")

    st.rerun()


def _resume_pipeline(chapter_id: str, chunk_index: int, subject: str):
    """
    Resume pipeline execution from where it left off.
    Called when UI state is PIPELINE_RUNNING and status already exists.
    """
    status = _get_pipeline_status()
    commands = [s for s in status.keys() if s != "command_6_tutor.py"]

    for script_name in commands:
        node = status.get(script_name, {})
        state = node.get("state", STATUS_PENDING)

        if state == STATUS_RUNNING:
            # This is the command we need to actually execute now
            meta = COMMAND_REGISTRY.get(script_name, {})
            display_name = meta.get("name", script_name)

            success, stdout, stderr = _run_single_command(script_name, chapter_id, chunk_index, subject)
            elapsed = time.time() - (node.get("started_at") or time.time())

            status = _get_pipeline_status()
            status[script_name] = {
                "state": STATUS_COMPLETED if success else STATUS_FAILED,
                "started_at": node.get("started_at"),
                "completed_at": time.time(),
                "duration_seconds": elapsed,
                "stdout": stdout,
                "stderr": stderr,
                "return_code": 0 if success else 1,
            }
            _set_pipeline_status(status)

            if not success:
                # Pipeline failed — stop execution
                st.rerun()
                return

            # Continue to next command
            _advance_to_next_or_finish(commands, chapter_id, chunk_index, subject)
            return

        elif state == STATUS_PENDING:
            # Haven't started yet — this shouldn't happen normally, but handle it
            _advance_to_next_or_finish(commands, chapter_id, chunk_index, subject)
            return

    # All commands processed — pipeline complete
    _finalize_pipeline(chapter_id)


def _advance_to_next_or_finish(commands: List[str], chapter_id: str, chunk_index: int, subject: str):
    """Move to the next pending/running command, or finalize if all done."""
    status = _get_pipeline_status()

    for script_name in commands:
        node = status.get(script_name, {})
        state = node.get("state", STATUS_PENDING)

        if state == STATUS_PENDING:
            # Mark next command as running
            meta = COMMAND_REGISTRY.get(script_name, {})
            status[script_name] = {
                "state": STATUS_RUNNING,
                "started_at": time.time(),
                "completed_at": None,
                "duration_seconds": None,
                "stdout": "",
                "stderr": "",
                "return_code": None,
            }
            _set_pipeline_status(status)
            st.rerun()
            return

    # No more pending commands — all done
    _finalize_pipeline(chapter_id)


def _finalize_pipeline(chapter_id: str):
    """Mark pipeline as fully complete and offer transition to learning UI."""
    st.session_state["pipeline_finished"] = True
    st.rerun()


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def render_pipeline_runner(
    chapter_id: str,
    subject: str,
    on_complete: Optional[Callable] = None,
):
    """
    Main render function for the pipeline runner component.

    Args:
        chapter_id: The target chapter ID (e.g. "CH_12_03")
        subject: The active subject (e.g. "mathematics")
        on_complete: Callback when pipeline finishes successfully
    """
    st.markdown("### 🔥 Deep Learning Compilation Pipeline")

    # Resolve per-subject paths once. Prefer the per-subject router
    # state written by the wired-up Command 0.5; fall back to the
    # legacy flat router state for the migration period.
    paths = _paths_for(subject)
    router_state_path = paths.router_state
    if not router_state_path.exists():
        from utils.paths import DATA_LIBRARY  # type: ignore
        _legacy_rs = DATA_LIBRARY / "active_workspace" / "router_state.json"
        if _legacy_rs.exists():
            router_state_path = _legacy_rs
            st.info(f"ℹ️ Loaded LEGACY router state (subject inferred: '{subject}').")
        else:
            st.error("❌ Router state not found. Run Pre-Flight Route Triage first.")
            if st.button("⬅️ Return to Selection"):
                st.session_state["ui_state"] = "SELECTION"
                st.rerun()
            return

    with open(router_state_path, "r", encoding="utf-8") as f:
        router_state = json.load(f)

    execution_path = router_state.get("execution_path", [])
    active_state = router_state.get("active_state", "STATE_A")

    if not execution_path:
        st.warning("Execution path is empty. Nothing to run.")
        return

    # Get chunk index from the per-subject active workspace
    chunk_index = 0
    workspace_path = paths.active_workspace
    if workspace_path.exists():
        try:
            with open(workspace_path, "r", encoding="utf-8") as f:
                ws_data = json.load(f)
            chunk_index = ws_data.get("current_active_chunk_index", 0)
        except Exception:
            pass

    # Pipeline info header
    st.markdown(f"**📖 Chapter:** `{chapter_id}` | **🧩 Chunk:** `{chunk_index}` | **🛤️ State:** `{active_state}` | **📚 Subject:** `{subject}`")
    st.markdown("---")

    pipeline_finished = st.session_state.get("pipeline_finished", False)
    status = _get_pipeline_status()

    if not status:
        # First time — show the execution plan and start button
        commands = [s for s in execution_path if s != "command_6_tutor.py"]

        st.markdown("**Execution Plan:**")
        for i, script_name in enumerate(commands, 1):
            meta = COMMAND_REGISTRY.get(script_name, {})
            display_name = meta.get("name", script_name)
            description = meta.get("description", "")
            st.markdown(f"  {i}. {display_name} — {description}")

        st.markdown("")
        if st.button("▶️ Start Pipeline Execution", type="primary", use_container_width=True):
            # Initialize and kick off
            status = _initialize_pipeline_status(execution_path)
            first_cmd = commands[0] if commands else None
            if first_cmd:
                status[first_cmd]["state"] = STATUS_RUNNING
                status[first_cmd]["started_at"] = time.time()
            _set_pipeline_status(status)
            st.session_state["pipeline_finished"] = False
            st.rerun()

        if st.button("⬅️ Cancel & Return"):
            st.session_state["ui_state"] = "TRIAGED"
            st.rerun()
        return

    # Status already exists — render the DAG nodes
    commands = list(status.keys())

    for i, script_name in enumerate(commands):
        is_current = (
            status[script_name]["state"] == STATUS_RUNNING
            or (
                status[script_name]["state"] == STATUS_PENDING
                and all(
                    status[commands[j]]["state"] in (STATUS_COMPLETED, STATUS_SKIPPED)
                    for j in range(i)
                )
            )
        )
        _render_single_node(
            script_name,
            status[script_name],
            chapter_id,
            chunk_index,
            is_current=is_current,
            pipeline_finished=pipeline_finished,
            subject=subject,
        )

    st.markdown("---")

    # If pipeline is still running (not finished), resume execution
    if not pipeline_finished:
        _resume_pipeline(chapter_id, chunk_index, subject)
        return

    # Pipeline finished — show summary and continue button
    all_completed = all(
        s["state"] in (STATUS_COMPLETED, STATUS_SKIPPED)
        for s in status.values()
    )
    any_failed = any(s["state"] == STATUS_FAILED for s in status.values())

    if all_completed:
        total_time = sum(
            s.get("duration_seconds", 0) or 0 for s in status.values()
        )
        st.success(f"🎉 Pipeline completed successfully! Total time: {total_time:.1f}s")

        if st.button("🚀 Proceed to Learning Dashboard", type="primary", use_container_width=True):
            if on_complete:
                on_complete()
            else:
                st.session_state["ui_state"] = "LEARNING"
                st.rerun()

    elif any_failed:
        # Find the first failed command for diagnosis
        first_failed_script = None
        for s, v in status.items():
            if v["state"] == STATUS_FAILED:
                first_failed_script = s
                break
        
        failed_cmds = [
            COMMAND_REGISTRY.get(s, {}).get("name", s)
            for s, v in status.items()
            if v["state"] == STATUS_FAILED
        ]
        
        st.error(f"**❌ Pipeline halted** — Failed at: {', '.join(failed_cmds)}")
        
        # Render full diagnosis for the first failed command
        if first_failed_script:
            fs = status[first_failed_script]
            diagnosis = _diagnose_error(
                fs.get("stderr", ""),
                fs.get("stdout", ""),
            )
            _render_error_diagnosis(diagnosis, key_prefix="summary")
        
        st.markdown("---")
        
        # Action buttons
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("🔄 Retry Full Pipeline", use_container_width=True):
                commands_list = list(status.keys())
                new_status = _initialize_pipeline_status(execution_path)
                if commands_list:
                    new_status[commands_list[0]]["state"] = STATUS_RUNNING
                    new_status[commands_list[0]]["started_at"] = time.time()
                _set_pipeline_status(new_status)
                st.session_state["pipeline_finished"] = False
                st.rerun()
        
        with btn_col2:
            if st.button("🔄 Retry From Failed Command", use_container_width=True):
                # Reset only the failed command(s) and leave completed ones intact
                for s in status:
                    if status[s]["state"] == STATUS_FAILED:
                        meta = COMMAND_REGISTRY.get(s, {})
                        status[s] = {
                            "state": STATUS_RUNNING,
                            "started_at": time.time(),
                            "completed_at": None,
                            "duration_seconds": None,
                            "stdout": "",
                            "stderr": "",
                            "return_code": None,
                        }
                _set_pipeline_status(status)
                st.session_state["pipeline_finished"] = False
                st.rerun()

    if st.button("⬅️ Return to Selection"):
        st.session_state["ui_state"] = "SELECTION"
        st.session_state.pop("pipeline_status", None)
        st.session_state.pop("pipeline_finished", None)
        st.rerun()


__all__ = ["render_pipeline_runner"]