"""
HY-TUTOR: LEVEL 6 SYSTEM ORCHESTRATOR (orchestrator.py)
Target Hardware: Asus TUF F15 (RTX 2050 4GB VRAM, 8GB System RAM)

Mandate: Master shell execution wrapper managing Phase 1 to Phase 5.5 transitions.
Upgraded with DAG Navigation arguments to support backward traversal and complete progress resets.
"""

import os
import sys
import json
import shutil
import argparse
import subprocess
from pathlib import Path
from typing import Optional

def get_active_chunk_index(chapter_id: str, subject: Optional[str] = None) -> int:
    """
    Retrieves the active chunk index from the per-subject volatile workspace.
    Defaults to 0 for a fresh chapter initialization.
    """
    from utils.paths import SubjectPaths, resolve_subject
    try:
        resolved = resolve_subject(subject)
    except ValueError:
        return 0
    paths = SubjectPaths.for_subject(resolved)
    try:
        if paths.active_workspace.exists():
            with open(paths.active_workspace, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Ensure we are pulling the chunk index for the correct active chapter
            if data.get("active_chapter_id") == chapter_id:
                return data.get("current_active_chunk_index", 0)
    except Exception as e:
        print(f"[WARNING] Could not read active chunk index: {e}")
    return 0

def handle_navigation(nav_action: str, chapter_id: str, subject: str):
    """
    Intercepts the execution flow to rewind or reset chunk progress,
    wiping physical caches and re-triaging the edge router.
    Operates on per-subject paths (data_library/subject_workspaces/<subject>/).
    """
    from utils.paths import SubjectPaths, resolve_subject

    # Resolve subject (CLI arg is the source of truth for nav)
    try:
        resolved = resolve_subject(subject)
    except ValueError as e:
        print(f"[FATAL ERROR] {e}")
        sys.exit(1)

    paths = SubjectPaths.for_subject(resolved)
    print(f"\n[ORCHESTRATOR] Nav-Override Triggered: {nav_action.upper()} for {chapter_id} (subject: {resolved})")

    # 1. Modify the per-subject Volatile Ledger
    if paths.active_workspace.exists():
        try:
            with open(paths.active_workspace, "r", encoding="utf-8") as f:
                data = json.load(f)

            if data.get("active_chapter_id") == chapter_id:
                current_idx = data.get("current_active_chunk_index", 0)

                if nav_action == "previous":
                    data["current_active_chunk_index"] = max(0, current_idx - 1)
                elif nav_action == "reset":
                    data["current_active_chunk_index"] = 0

                with open(paths.active_workspace, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                print(f"[STATE ADVANCEMENT] Rewound chunk index to: {data['current_active_chunk_index']}")
        except Exception as e:
            print(f"[ERROR] Failed to modify active workspace for navigation: {e}")

    # 2. Wipe the per-subject Physical Content Cache
    if paths.chunk_dir.exists():
        try:
            # Remove all files in active_chunk directory
            for item in paths.chunk_dir.iterdir():
                if item.is_file():
                    item.unlink()
            print("[STATE ADVANCEMENT] Physical chunk cache purged.")
        except Exception as e:
            print(f"[ERROR] Failed to clear active chunk directory: {e}")

    # 3. Invalidate per-subject router state to prevent stale state issues
    if paths.router_state.exists():
        try:
            paths.router_state.unlink()
            print("[STATE ADVANCEMENT] Router state invalidated.")
        except Exception as e:
            print(f"[ERROR] Failed to remove router state: {e}")

    # 4. Re-invoke Command 0.5 to refresh the execution graph
    print("[PROCESS] Triggering Edge Router to rebuild the DAG...")
    try:
        cmd = [sys.executable, "core_pipeline/command_0_5_router.py", resolved, chapter_id]
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.stdout:
            print(result.stdout)
    except subprocess.TimeoutExpired:
        print("[FATAL ERROR] Edge Router timed out during navigation override.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"[FATAL ERROR] Edge Router failed: {e}")
        print(f"[STDOUT]\n{e.stdout}")
        print(f"[STDERR]\n{e.stderr}")
        sys.exit(1)
    except Exception as e:
        print(f"[FATAL ERROR] Edge Router failed during navigation override: {e}")
        sys.exit(1)

def _load_router_state() -> tuple[dict, str]:
    """Locate and parse the active router state. Prefers the per-subject
    ``data_library/subject_workspaces/<subject>/router_state.json`` (the
    location the wired-up Command 0.5 writes to). Falls back to the
    legacy flat ``data_library/active_workspace/router_state.json``
    for the migration period.

    Returns ``(router_state_dict, resolved_subject)``. Exits the
    process on failure.
    """
    from utils.paths import (
        SubjectPaths, DATA_LIBRARY, set_current_subject,
        resolve_subject,
    )
    # Legacy fallback path (the old flat layout before the per-subject refactor)
    _LEGACY_ROUTER_STATE = DATA_LIBRARY / "active_workspace" / "router_state.json"

    # 1. Try the per-subject router state (preferred).
    try:
        resolved = resolve_subject()
    except ValueError:
        resolved = None

    if resolved:
        paths = SubjectPaths.for_subject(resolved)
        if paths.router_state.exists():
            try:
                with open(paths.router_state, "r", encoding="utf-8") as f:
                    state = json.load(f)
                print(f"[ORCHESTRATOR] Loaded per-subject router state: {paths.router_state}")
                return state, resolved
            except Exception as e:
                print(f"[WARNING] Failed to parse per-subject router state: {e}")

    # 2. Migration fallback: legacy flat router state.
    if _LEGACY_ROUTER_STATE.exists():
        try:
            with open(_LEGACY_ROUTER_STATE, "r", encoding="utf-8") as f:
                state = json.load(f)
            # The legacy router state has no embedded subject — try to
            # infer it from the legacy ui_session.json (which carries
            # active_subject) and pin the pointer for downstream cmds.
            try:
                resolved = resolve_subject()
            except ValueError:
                resolved = None
            if resolved:
                set_current_subject(resolved)
                print(f"[ORCHESTRATOR] Loaded LEGACY router state; resolved subject='{resolved}'")
                return state, resolved
            print("[ORCHESTRATOR] Loaded LEGACY router state; subject unknown.")
            return state, ""
        except Exception as e:
            print(f"[FATAL ERROR] Failed to parse legacy router_state.json: {e}")
            sys.exit(1)

    print("[FATAL ERROR] router_state.json not found in any known location.")
    print("[HALT] Run command_0_5_router.py first to compile the execution graph.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Phase 2 — Per-Chapter Archive Copy Helper
# ---------------------------------------------------------------------------

# Maps orchestrator script names to (active_chunk_filename, archive_method_name)
_ARCHIVE_MAP = {
    "command_2_miner.py":    ("NCERT_chunk.json",     "ncert_chunk_path"),
    "command_3_optimizer.py": ("Reference_chunk.json", "reference_chunk_path"),
    "command_4_bridge.py":   ("Bridge_chunk.json",    "bridge_chunk_path"),
    "command_5_forge.py":    ("Unified_Lesson.md",    "lesson_chunk_path"),
    "command_5_5_injector.py": ("Active_Chunk_Problems.json", "problems_chunk_path"),
}


def _archive_chunk_output(script_name: str, chapter_id: str, chunk_index: int, subject: str):
    """After a pipeline node succeeds, copy its ``active_chunk/`` output
    into the per-chapter archive folder ``chapters/<chapter_id>/``.

    This is a silent no-op if the source file does not exist (e.g. the
    command wrote nothing).  Errors are logged but never abort the pipeline.
    """
    from utils.paths import SubjectPaths
    try:
        resolved = (subject or "").strip().lower() or None
        if not resolved:
            return
        paths = SubjectPaths.for_subject(resolved)

        mapping = _ARCHIVE_MAP.get(script_name)
        if mapping is None:
            return  # blueprint (C1) and tutor (C6) have no active_chunk output

        src_filename, method_name = mapping
        src = paths.chunk_dir / src_filename
        if not src.exists():
            return

        archive_method = getattr(paths, method_name)
        dst = archive_method(chapter_id, chunk_index)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"[ARCHIVE] {src_filename} -> {dst}")
    except Exception as e:
        print(f"[WARNING] Archive copy failed for {script_name}: {e}")


def run_pipeline():
    print("\n==============================================")
    print("         HY-TUTOR MASTER ORCHESTRATOR ENGINE  ")
    print("==============================================")

    router_state, subject = _load_router_state()
    if not subject:
        print("[FATAL ERROR] Could not resolve an active subject for the orchestrator.")
        print("[HALT] Pass --subject <name>, set HY_TUTOR_SUBJECT, or run command_0_5_router.py first.")
        sys.exit(1)

    active_state = router_state.get("active_state")
    chapter_id = router_state.get("target_chapter_id")
    execution_path = router_state.get("execution_path", [])

    # Pin the ambient pointer so any downstream C-subprocess that reads
    # the pointer (rather than receiving --subject explicitly) still
    # resolves the right subject.
    from utils.paths import set_current_subject
    set_current_subject(subject)

    print(f"[ORCHESTRATOR] Active State: {active_state} | Target Chapter: {chapter_id} | Subject: {subject}")

    # 2. Enforce Prerequisite Blockade (State B)
    if active_state == "STATE_B":
        blocked_by = router_state.get("blocking_prerequisite", {})
        print(f"[ORCHESTRATOR] HALT: Prerequisite Blockade Active ({blocked_by.get('chapter_id')}).")
        print("[PROCESS] Orchestrator standing by. Awaiting UI conversational override.")
        sys.exit(0)

    # 3. Resolve Volatile Workspace State
    chunk_index = get_active_chunk_index(chapter_id)
    print(f"[ORCHESTRATOR] Active Chunk Index Resolved: {chunk_index}")

    base_dir = Path("core_pipeline")

    # Per-command timeout overrides (in seconds). Default is 600s (10 min).
    # Override via env var: ORCHESTRATOR_DEFAULT_TIMEOUT=900
    import os as _os
    DEFAULT_TIMEOUT = int(_os.getenv("ORCHESTRATOR_DEFAULT_TIMEOUT", "600"))
    COMMAND_TIMEOUTS = {
        "command_1_blueprint.py": 900,    # 15 min - heavy blueprint generation
        "command_2_miner.py": 600,        # 10 min - NCERT extraction
        "command_3_optimizer.py": 900,    # 15 min - reference optimization (multi-phase)
        "command_4_bridge.py": 600,       # 10 min - bridge synthesis
        "command_5_forge.py": 600,        # 10 min - lesson forge
        "command_5_5_injector.py": 900,   # 15 min - exemplar injection (multi-phase)
    }

    # 4. Execute the Directed Acyclic Graph (DAG)
    for script_name in execution_path:
        script_path = base_dir / script_name

        # Stop headless execution before entering live UI loops
        if script_name == "command_6_tutor.py":
            print(f"\n[ORCHESTRATOR] Handoff reached at {script_name}.")
            print("[PROCESS] Delegating Live Socratic Tutor to Level 7 UI Event Loop.")
            break

        print(f"\n>>>>> EXECUTING DAG NODE: {script_name} >>>>>")

        # Map dynamic terminal arguments based on the script footprint.
        # Every command receives --subject so it can resolve per-subject
        # paths independently (no reliance on the ambient pointer).
        cmd = [sys.executable, str(script_path), "--subject", subject]
        if script_name == "command_1_blueprint.py":
            cmd.append(chapter_id)
        else:
            # Commands 2, 3, 4, 5, and 5.5 require both Chapter ID and Chunk Index
            cmd.extend([chapter_id, str(chunk_index)])

        # Resolve timeout: per-command override > env default > 600s
        cmd_timeout = COMMAND_TIMEOUTS.get(script_name, DEFAULT_TIMEOUT)
        print(f"[TIMEOUT] {script_name} allowed {cmd_timeout}s")

        # Dispatch Subprocess with full error capture and timeout
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=cmd_timeout
            )
            # Note: check=True means CalledProcessError is raised on non-zero exit,
            # so the unreachable `if result.returncode != 0` block has been removed.
            if result.stdout:
                print(result.stdout)

            # --- Phase 2: Copy completed output to per-chapter archive ------
            _archive_chunk_output(script_name, chapter_id, chunk_index, subject)
        except subprocess.TimeoutExpired as e:
            print(f"\n[FATAL ERROR] Node {script_name} timed out after {cmd_timeout} seconds.")
            print(f"[ERROR] {e}")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"\n[FATAL ERROR] Pipeline crash at {script_name}.")
            print(f"[RETURN CODE] {e.returncode}")
            print(f"[STDOUT]\n{e.stdout}")
            print(f"[STDERR]\n{e.stderr}")
            sys.exit(1)
        except Exception as e:
            print(f"\n[FATAL ERROR] Unexpected error executing {script_name}: {e}")
            sys.exit(1)

    print("\n==============================================")
    print("      ORCHESTRATOR HEADLESS PIPELINE COMPLETE ")
    print("==============================================")
    print(f"[SYSTEM] Backend staging complete for {chapter_id}.")
    print("[SYSTEM] Ready for Streamlit UI (Level 7) rendering.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HY-TUTOR Master Orchestrator")
    parser.add_argument("--nav", type=str, choices=["previous", "reset"], help="Override to rewind or reset chunk index.")
    parser.add_argument("--chapter", type=str, help="Target Chapter ID for navigation override.")
    parser.add_argument("--subject", type=str, help="Active Subject Domain for navigation override.")
    
    args = parser.parse_args()

    # Trap navigation arguments to cleanly rewind state before executing the DAG
    if args.nav and args.chapter and args.subject:
        handle_navigation(args.nav, args.chapter, args.subject)
        
    run_pipeline()