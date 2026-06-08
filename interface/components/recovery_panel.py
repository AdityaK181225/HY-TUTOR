"""
HY-TUTOR: Recovery Panel Component
Lists recoverable chapters with Retry/Skip/Restart/Clear buttons.
"""

import streamlit as st
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Ensure core_pipeline is importable (cached at module level)
_CORE_PIPELINE_PATH = str(Path(__file__).resolve().parent.parent.parent / "core_pipeline")
if _CORE_PIPELINE_PATH not in sys.path:
    sys.path.insert(0, _CORE_PIPELINE_PATH)


def render_recovery_panel(subject: str = ""):
    """
    Render the Recovery Panel showing chapters that failed during compilation.

    Uses RecoveryManager to list recoverable chapters and provides action buttons.
    The RecoveryManager is now scoped to the per-subject recovery
    state file (data_library/subject_workspaces/<subject>/recovery/
    recovery_state.json), so each subject has its own recovery ledger.
    """
    st.markdown("---")
    st.subheader("🔧 Recovery Panel")

    # Import RecoveryManager and resolve the per-subject recovery path.
    try:
        from utils.recovery import RecoveryManager
        recovery_dir = None
        if subject:
            try:
                import sys as _sys
                if "core_pipeline" not in _sys.path:
                    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "core_pipeline"))
                from utils.paths import SubjectPaths  # type: ignore
                recovery_dir = SubjectPaths.for_subject(subject).recovery.parent
            except Exception:
                recovery_dir = None
        if recovery_dir is not None:
            rm = RecoveryManager(recovery_dir=recovery_dir)
        else:
            rm = RecoveryManager()
    except ImportError:
        st.info("Recovery module not available.")
        return
    except Exception as e:
        st.warning(f"Recovery manager unavailable: {e}")
        return

    recoverable = rm.get_recoverable_chapters()

    # Filter by subject if specified
    if subject:
        recoverable = [r for r in recoverable if r.get("subject") == subject]

    if not recoverable:
        st.success("✅ No chapters need recovery. All pipelines completed successfully.")
        return

    st.caption(f"Found {len(recoverable)} chapter(s) that need attention:")

    for entry in recoverable:
        chap_id = entry["chapter_id"]
        failed_cmd = entry.get("failed_command", "unknown")
        attempts = entry.get("attempts", 0)
        max_attempts = entry.get("max_attempts", 5)
        error = entry.get("error_message", "")
        status = entry.get("status", "failed")
        can_retry = entry.get("can_retry", True)

        # Status badge
        if status == "skipped":
            badge = "⏭️ Skipped"
        elif not can_retry:
            badge = "🚫 Max Attempts"
        else:
            badge = "❌ Failed"

        with st.expander(
            f"{badge} **{chap_id}** — Failed at `{failed_cmd}` ({attempts}/{max_attempts} attempts)",
            expanded=True,
        ):
            # Error message
            if error:
                st.error(f"Error: {error[:200]}{'...' if len(error) > 200 else ''}")

            # Action buttons
            if can_retry:
                btn_cols = st.columns(4)

                with btn_cols[0]:
                    if st.button("🔄 Retry", key=f"retry_{chap_id}", use_container_width=True):
                        _run_recovery_action(rm, chap_id, entry, "retry")

                with btn_cols[1]:
                    if st.button("⏭️ Skip", key=f"skip_{chap_id}", use_container_width=True):
                        rm.skip_chapter(chap_id)
                        st.success(f"Skipped {chap_id}")
                        st.rerun()

                with btn_cols[2]:
                    if st.button("🔁 Restart", key=f"restart_{chap_id}", use_container_width=True):
                        _run_recovery_action(rm, chap_id, entry, "restart")

                with btn_cols[3]:
                    if st.button("🗑️ Clear", key=f"clear_{chap_id}", use_container_width=True):
                        rm.clear_chapter(chap_id)
                        st.success(f"Cleared {chap_id} from recovery")
                        st.rerun()
            else:
                st.warning(
                    f"Maximum attempts ({max_attempts}) reached for {chap_id}. "
                    "Click 'Clear' to remove from recovery state."
                )
                if st.button("🗑️ Clear", key=f"clear_max_{chap_id}"):
                    rm.clear_chapter(chap_id)
                    st.success(f"Cleared {chap_id} from recovery")
                    st.rerun()

    # Global actions
    if len(recoverable) > 1:
        st.markdown("---")
        if st.button("🗑️ Clear All Recovery State"):
            rm.clear_all()
            st.success("All recovery state cleared.")
            st.rerun()


def _run_recovery_action(
    rm,
    chapter_id: str,
    entry: Dict[str, Any],
    action: str,
):
    """
    Execute a recovery action (retry/restart) by re-running the orchestrator
    from the appropriate command index.
    """
    subject = entry.get("subject", "mathematics")

    # Default execution path (sequential mode)
    execution_path = [
        "command_1_blueprint.py",
        "command_2_miner.py",
        "command_3_optimizer.py",
        "command_4_bridge.py",
        "command_5_5_injector.py",
        "command_5_forge.py",
    ]

    start_idx = rm.get_next_command_index(chapter_id, execution_path, action=action)

    st.info(f"Starting recovery from index {start_idx} ({action})...")

    # Build orchestrator command with navigation
    cmd = [
        sys.executable,
        "core_pipeline/orchestrator.py",
        "--chapter", chapter_id,
        "--subject", subject,
    ]

    if action == "restart":
        cmd.extend(["--nav", "reset"])
    # For "retry", we don't use nav — we re-run from the failed command

    try:
        with st.spinner(f"Recovering {chapter_id}..."):
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode == 0:
                st.success(f"Recovery completed for {chapter_id}!")
                rm.clear_chapter(chapter_id)
                st.rerun()
            else:
                st.error(f"Recovery failed: {result.stderr[:500] if result.stderr else 'Unknown error'}")
    except subprocess.TimeoutExpired:
        st.error("Recovery timed out after 10 minutes.")
    except Exception as e:
        st.error(f"Recovery error: {e}")


__all__ = ["render_recovery_panel"]