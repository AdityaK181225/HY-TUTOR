"""
HY-TUTOR: LEVEL 6 LOCAL EDGE ROUTER (command_0_5_router.py)
Target Hardware: Asus TUF F15 (RTX 2050 4GB VRAM, 8GB System RAM)
Model Engine: gemma-4-31b-it (or fallback) via Modernized Google GenAI SDK
Includes a resilient 5-pass exponential backoff retry loop for Conversational Overrides.

Wired up to per-subject paths (data_library/subject_workspaces/<subject>/).
The legacy flat ``data_library/active_workspace/`` tree is no longer used by
this command; downstream commands that need to look up the active subject
fall back to the ``HY_TUTOR_SUBJECT`` env var or the
``data_library/subject_workspaces/.current_subject`` pointer file.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from utils.inference import call_gemini
from utils.genai_client import get_default_model
from utils.logging_utils import (
    log_init, log_process, log_success, log_warning, log_error, log_state,
    log_debug, log_critical
)
from utils.paths import (
    SubjectPaths,
    set_current_subject,
    get_subject_router_state,
)

# Rigid Output Schema for LLM Conversational Override
class OverrideEvaluation(BaseModel):
    is_valid_acknowledgement: bool = Field(..., description="True if the user actively confirms they understand the prerequisite concept.")
    extracted_rationale: str = Field(..., description="Brief explanation of why the user's input was accepted or rejected.")

# Rigid Output Schema for Downstream Orchestrator
class RouterDirective(BaseModel):
    active_state: str = Field(..., description="Strictly 'STATE_A', 'STATE_B', or 'STATE_C'")
    target_chapter_id: str
    subject: str = Field(..., description="Lower-cased active subject (e.g., 'mathematics'). Embedded so downstream commands can resolve per-subject paths.")
    blocking_prerequisite: Optional[dict] = Field(None, description="Details of the missing prerequisite if in STATE_B")
    active_weak_area: Optional[dict] = Field(None, description="Details of the weak area if in STATE_C")
    execution_path: List[str] = Field(..., description="List of pipeline commands to execute next.")

def load_system_ledgers(subject: str) -> tuple[dict, dict]:
    """Safely extracts both the Syllabus Map and the Global Progress Tracker."""
    from utils.paths import MASTER_SYLLABUS_PATH, GLOBAL_TRACKER_PATH

    if not MASTER_SYLLABUS_PATH.exists():
        log_critical("command_0_5_router", f"Master Syllabus missing at {MASTER_SYLLABUS_PATH}")
        sys.exit(1)

    try:
        with open(MASTER_SYLLABUS_PATH, "r", encoding="utf-8") as f:
            full_syllabus = json.load(f)

        # Apply Clean Domain Isolation mapping (Level 3 Fix)
        subject_map = full_syllabus.get(subject.lower(), {})

        if not subject_map:
            log_critical("command_0_5_router", f"Subject '{subject}' not found in Master Syllabus")
            sys.exit(1)

        tracker_data = {}
        if GLOBAL_TRACKER_PATH.exists():
            with open(GLOBAL_TRACKER_PATH, "r", encoding="utf-8") as f:
                tracker_data = json.load(f)

        return subject_map, tracker_data
    except Exception as e:
        log_critical("command_0_5_router", f"Ledger parsing failed: {e}")
        sys.exit(1)

def set_active_chunk_pointer(paths: SubjectPaths, chapter_id: str, chunk_index: int, active_state: str):
    """Safely updates the per-subject volatile workspace so the orchestrator
    targets the exact chunk needed for the current subject.
    """
    paths.active_workspace.parent.mkdir(parents=True, exist_ok=True)

    data = {}
    if paths.active_workspace.exists():
        try:
            with open(paths.active_workspace, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            log_debug("command_0_5_router", f"Failed to read existing workspace: {e}")
            pass

    data["active_chapter_id"] = chapter_id
    data["current_active_chunk_index"] = chunk_index
    data["active_state"] = active_state

    with open(paths.active_workspace, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    log_debug("command_0_5_router", f"Active chunk pointer set: chapter={chapter_id}, chunk={chunk_index}, state={active_state}")

def is_cache_valid(paths: SubjectPaths, target_chapter_id: str, target_chunk_index: int) -> bool:
    """Prevents cross-chapter cache poisoning by validating ALL physical
    assets in the per-subject active chunk directory via metadata.
    """
    chunk_dir = paths.chunk_dir

    # All files required for complete pipeline execution
    required_files = {
        "NCERT_chunk.json": True,           # Command 2 output
        "Reference_chunk.json": True,       # Command 3 output
        "Bridge_chunk.json": True,          # Command 4 output
        "Active_Chunk_Problems.json": True,  # Command 5.5 output
        "Unified_Lesson.md": True           # Command 5 output
    }

    # Check if directory exists
    if not chunk_dir.exists():
        return False

    # Check all required files exist and validate their metadata
    for filename, is_required in required_files.items():
        file_path = chunk_dir / filename
        if not file_path.exists():
            log_debug("command_0_5_router", f"Cache validation: Missing required file: {filename}")
            return False

        # Validate JSON files contain correct chapter/chunk metadata
        if filename.endswith('.json'):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Validate chapter and chunk alignment
                    if data.get("active_chapter_id") != target_chapter_id:
                        log_debug("command_0_5_router", f"Cache validation: Chapter mismatch in {filename} - expected {target_chapter_id}, got {data.get('active_chapter_id')}")
                        return False
                    if data.get("chunk_index") != target_chunk_index:
                        log_debug("command_0_5_router", f"Cache validation: Chunk index mismatch in {filename} - expected {target_chunk_index}, got {data.get('chunk_index')}")
                        return False
            except (json.JSONDecodeError, Exception) as e:
                log_debug("command_0_5_router", f"Cache validation failed for {filename}: {e}")
                return False

    log_debug("command_0_5_router", f"Cache validation: ALL files present and validated for {target_chapter_id} chunk {target_chunk_index}")
    return True

def is_blueprint_valid(paths: SubjectPaths, chapter_id: str) -> bool:
    """Checks if the per-subject chapter-level structural blueprint
    already exists on disk.
    """
    blueprint_path = paths.blueprint_path(chapter_id)
    return blueprint_path.exists()

def evaluate_conversational_override(prereq_topic: str, user_input: str) -> bool:
    """Uses LLM to evaluate if user input constitutes a valid prerequisite override, featuring resilient backoff."""
    log_process("command_0_5_router", "Evaluating conversational override via LLM...")

    MODEL_NAME = get_default_model("command_0_5_router")
    log_process("command_0_5_router", f"Using model: {MODEL_NAME}")

    prompt = f"""
    You are the State B Prerequisite Gatekeeper.
    The student is currently blocked because they haven't completed the prerequisite concept: '{prereq_topic}'.
    They have provided the following conversational response to bypass the block:
    "{user_input}"
    Determine if this is a valid acknowledgement of competency (e.g., "I know this", "skip it, I studied this in class", "I understand it").
    Return True if valid, False if they are confused or asking for help.
    """

    try:
        raw_text, _model_used = call_gemini(
            "command_0_5_router",
            MODEL_NAME,
            prompt,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=OverrideEvaluation,
            max_retries=5,
        )
        eval_json = json.loads(raw_text)
        log_success("command_0_5_router", f"Override Eval: Validity={eval_json['is_valid_acknowledgement']} | Reason: {eval_json['extracted_rationale']}")
        return eval_json.get("is_valid_acknowledgement", False)
    except RuntimeError as e:
        log_error("command_0_5_router", f"Override evaluation failed after retries: {e}")
        return False
    except json.JSONDecodeError as e:
        log_error("command_0_5_router", f"Failed to parse AI response as JSON: {e}")
        return False

def force_complete_prerequisite(tracker_data: dict, prereq_chapter_id: str):
    """Mutates Global_Subject_Tracker.json directly to mark a prerequisite as completed."""
    from utils.paths import GLOBAL_TRACKER_PATH

    log_process("command_0_5_router", f"Force-completing prerequisite: {prereq_chapter_id}")

    if "chapters_ledger" not in tracker_data:
        tracker_data["chapters_ledger"] = {}

    tracker_data["chapters_ledger"][prereq_chapter_id] = {
        "status": "COMPLETED",
        "overridden_via_chat": True,
        "weak_areas_flagged": []
    }

    with open(GLOBAL_TRACKER_PATH, "w", encoding="utf-8") as f:
        json.dump(tracker_data, f, indent=4)
    log_success("command_0_5_router", f"Ledger update: Concept '{prereq_chapter_id}' marked as COMPLETED via conversational override")

def execute_command_0_5_pipeline(subject: str, chapter_id: str, chat_override: str = None, _recursion_depth: int = 0):
    # Prevent infinite recursion from circular prerequisite chains
    MAX_RECURSION_DEPTH = 3
    if _recursion_depth > MAX_RECURSION_DEPTH:
        log_critical("command_0_5_router", f"Circular prerequisite dependency detected for {chapter_id}. Max depth {MAX_RECURSION_DEPTH} exceeded.")
        sys.exit(1)

    subject_norm = (subject or "").strip().lower()
    if not subject_norm:
        log_critical("command_0_5_router", "Empty subject supplied to execute_command_0_5_pipeline")
        sys.exit(1)

    log_init("command_0_5_router", f"Edge Router initialized for {subject_norm} | {chapter_id} (Recursion Depth: {_recursion_depth})")
    log_process("command_0_5_router", "Step 1: Loading domain ledgers...")

    # 0. Resolve per-subject paths ONCE and pin the ambient pointer so
    #    downstream subprocesses that aren't passed --subject can still
    #    discover the right workspace.
    paths = SubjectPaths.for_subject(subject_norm)
    set_current_subject(subject_norm)
    log_process("command_0_5_router", f"Per-subject workspace pinned: {paths.root}")

    # 1. Load Isolated Domain Ledgers
    subject_map, tracker_data = load_system_ledgers(subject_norm)
    chapter_metadata = subject_map.get("chapters", {}).get(chapter_id)

    if not chapter_metadata:
        log_critical("command_0_5_router", f"Chapter '{chapter_id}' not found in '{subject_norm}' syllabus.")
        sys.exit(1)

    log_success("command_0_5_router", f"Loaded syllabus for {subject_norm}: {len(subject_map.get('chapters', {}))} chapters")

    # 2. Check State C (Adaptive Revision Loop - Weak Areas)
    # Highest priority: If they failed a chunk in this chapter previously, force revision.
    log_process("command_0_5_router", "Step 2: Checking for weak areas (STATE C)...")
    chapter_ledger = tracker_data.get("chapters_ledger", {}).get(chapter_id, {})
    active_weak_areas = [w for w in chapter_ledger.get("weak_areas_flagged", []) if w.get("is_weak_area") is True]

    if active_weak_areas:
        weak_target = active_weak_areas[0]
        weak_chunk_idx = weak_target.get('chunk_index', 0)
        weak_topic = weak_target.get('topic', 'Unknown')
        log_state("command_0_5_router", f"STATE C: Weak area detected - Topic: '{weak_topic}' at Chunk {weak_chunk_idx}")

        # Inject exact pointer into volatile workspace
        log_process("command_0_5_router", f"Setting active chunk pointer: chapter={chapter_id}, chunk={weak_chunk_idx}, state=STATE_C")
        set_active_chunk_pointer(paths, chapter_id, weak_chunk_idx, "STATE_C")

        # Verify physical cache alignment
        log_process("command_0_5_router", "Verifying cache alignment...")
        if is_cache_valid(paths, chapter_id, weak_chunk_idx):
            log_success("command_0_5_router", "Cache HIT: All required files present and validated")
            exec_path = ["command_5_5_injector.py", "command_6_tutor.py"]
        else:
            log_warning("command_0_5_router", "Cache MISS: Required files missing or mismatched")
            if is_blueprint_valid(paths, chapter_id):
                log_success("command_0_5_router", "Blueprint HIT: Using existing chapter blueprint")
                exec_path = [
                    "command_2_miner.py",
                    "command_3_optimizer.py",
                    "command_4_bridge.py",
                    "command_5_5_injector.py", # SWAPPED: Runs before Forge (C5)
                    "command_5_forge.py",
                    "command_6_tutor.py"
                ]
            else:
                log_warning("command_0_5_router", "Blueprint MISS: Initiating complete chapter parsing")
                exec_path = [
                    "command_1_blueprint.py",
                    "command_2_miner.py",
                    "command_3_optimizer.py",
                    "command_4_bridge.py",
                    "command_5_5_injector.py", # SWAPPED: Runs before Forge (C5)
                    "command_5_forge.py",
                    "command_6_tutor.py"
                ]

        log_process("command_0_5_router", f"Execution path: {' → '.join(exec_path)}")
        directive = RouterDirective(
            active_state="STATE_C",
            target_chapter_id=chapter_id,
            subject=subject_norm,
            active_weak_area=weak_target,
            execution_path=exec_path
        )
        save_and_exit(paths, directive)

    # 3. Check State B (Prerequisite Blockade)
    log_process("command_0_5_router", "Step 3: Checking prerequisites (STATE B)...")
    prereqs = chapter_metadata.get("cross_grade_prerequisites", [])

    # Collect ALL blocking prerequisites, not just the first one
    all_blocked = []
    for req in prereqs:
        req_id = req.get("chapter_id")
        req_status = tracker_data.get("chapters_ledger", {}).get(req_id, {}).get("status", "PENDING")
        log_debug("command_0_5_router", f"Prerequisite {req_id}: status={req_status}")
        if req_status != "COMPLETED":
            all_blocked.append(req)

    if all_blocked:
        # Use first blocked for UI display
        blocked_by = all_blocked[0]
        blocked_topic = blocked_by.get("topic", blocked_by.get("chapter_id", "Unknown"))
        log_state("command_0_5_router", f"STATE B: {len(all_blocked)} prerequisite(s) blocking - '{blocked_topic}'")

        # Check if user provided a chat override attempt
        if chat_override:
            log_process("command_0_5_router", "User provided chat override - evaluating...")
            # Evaluate override for the first blocking prerequisite
            is_valid = evaluate_conversational_override(blocked_topic, chat_override)
            if is_valid:
                # Mark ALL blocking prerequisites as complete (not just the first)
                for blocked_req in all_blocked:
                    force_complete_prerequisite(tracker_data, blocked_req["chapter_id"])
                log_process("command_0_5_router", f"All {len(all_blocked)} prerequisite(s) cleared via chat override. Re-evaluating state...")

                # Reload tracker data to get updated state and re-check
                # Use iterative approach: reload ledgers and continue (no recursion)
                subject_map, tracker_data = load_system_ledgers(subject_norm)
                # Re-check prerequisites with updated tracker
                prereqs = chapter_metadata.get("cross_grade_prerequisites", [])
                still_blocked = []
                for req in prereqs:
                    req_id = req.get("chapter_id")
                    req_status = tracker_data.get("chapters_ledger", {}).get(req_id, {}).get("status", "PENDING")
                    if req_status != "COMPLETED":
                        still_blocked.append(req)

                if still_blocked:
                    # If there are still blocked prerequisites after override, stay in STATE B
                    # This can happen if there are more prerequisites than the user overridden
                    new_blocked_by = still_blocked[0]
                    log_warning("command_0_5_router", f"Additional prerequisite(s) still blocking: {new_blocked_by.get('chapter_id')}")
                    directive = RouterDirective(
                        active_state="STATE_B",
                        target_chapter_id=chapter_id,
                        subject=subject_norm,
                        blocking_prerequisite=new_blocked_by,
                        execution_path=[]
                    )
                    save_and_exit(paths, directive)

                # If no more blocking prerequisites, continue to next checks
                # Fall through to State A check below
            else:
                log_warning("command_0_5_router", "Chat override REJECTED. Maintaining STATE B lock.")

                # If no valid override, stay in State B
                log_process("command_0_5_router", "No valid override - execution halted at STATE B")
                directive = RouterDirective(
                    active_state="STATE_B",
                    target_chapter_id=chapter_id,
                    subject=subject_norm,
                    blocking_prerequisite=blocked_by,
                    execution_path=[]
                )
                save_and_exit(paths, directive)
        else:
            # No chat override provided, stay in State B
            log_process("command_0_5_router", "No chat override provided - execution halted at STATE B")
            directive = RouterDirective(
                active_state="STATE_B",
                target_chapter_id=chapter_id,
                subject=subject_norm,
                blocking_prerequisite=blocked_by,
                execution_path=[]
            )
            save_and_exit(paths, directive)

    # 4. State A (Standard Adaptive Path)
    log_process("command_0_5_router", "Step 4: Checking standard path (STATE A)...")
    log_state("command_0_5_router", "STATE A: Path clear - standard adaptive routing")

    # Get ongoing sequential chunk index or start at 0
    log_process("command_0_5_router", "Retrieving current chunk index from workspace...")
    current_idx = 0
    if paths.active_workspace.exists():
        try:
            with open(paths.active_workspace, "r", encoding="utf-8") as f:
                w_data = json.load(f)
                if w_data.get("active_chapter_id") == chapter_id:
                    current_idx = w_data.get("current_active_chunk_index", 0)
                    log_success("command_0_5_router", f"Retrieved chunk index: {current_idx}")
                else:
                    log_debug("command_0_5_router", "Different chapter in workspace - starting at 0")
        except Exception as e:
            log_warning("command_0_5_router", f"Failed to read workspace: {e}")
    else:
        log_debug("command_0_5_router", "No workspace file found - starting at chunk 0")

    log_process("command_0_5_router", f"Setting active chunk pointer: chapter={chapter_id}, chunk={current_idx}, state=STATE_A")
    set_active_chunk_pointer(paths, chapter_id, current_idx, "STATE_A")

    log_process("command_0_5_router", "Verifying cache alignment...")
    if is_cache_valid(paths, chapter_id, current_idx):
        log_success("command_0_5_router", "Cache HIT: All required files present - pruning Commands 1-5")
        exec_path = ["command_6_tutor.py"]
    else:
        log_warning("command_0_5_router", "Cache MISS: Context requires generation")
        if is_blueprint_valid(paths, chapter_id):
            log_success("command_0_5_router", "Blueprint HIT: Using existing chapter blueprint")
            exec_path = [
                "command_2_miner.py",
                "command_3_optimizer.py",
                "command_4_bridge.py",
                "command_5_5_injector.py", # SWAPPED: Runs before Forge (C5)
                "command_5_forge.py",
                "command_6_tutor.py"
            ]
        else:
            log_warning("command_0_5_router", "Blueprint MISS: Initiating complete chapter parsing")
            exec_path = [
                "command_1_blueprint.py",
                "command_2_miner.py",
                "command_3_optimizer.py",
                "command_4_bridge.py",
                "command_5_5_injector.py", # SWAPPED: Runs before Forge (C5)
                "command_5_forge.py",
                "command_6_tutor.py"
            ]

    log_process("command_0_5_router", f"Execution path: {' → '.join(exec_path)}")
    directive = RouterDirective(
        active_state="STATE_A",
        target_chapter_id=chapter_id,
        subject=subject_norm,
        execution_path=exec_path
    )
    save_and_exit(paths, directive)

def save_and_exit(paths: SubjectPaths, directive: RouterDirective):
    """Writes the per-subject router directive to disk and exits."""
    paths.router_state.parent.mkdir(parents=True, exist_ok=True)

    with open(paths.router_state, "w", encoding="utf-8") as f:
        json.dump(directive.model_dump(), f, indent=4)

    log_success("command_0_5_router", f"Router Directive Published to {paths.router_state}")
    log_state("command_0_5_router", f"Final State: {directive.active_state}")
    sys.exit(0)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HY-TUTOR Command 0.5 Edge Router")
    parser.add_argument("subject", type=str, help="Subject Domain (e.g., Physics)")
    parser.add_argument("chapter_id", type=str, help="Target Chapter ID (e.g., CH_12_01)")
    parser.add_argument("--chat", type=str, help="Optional conversational override text for State B", default=None)

    args = parser.parse_args()
    execute_command_0_5_pipeline(args.subject, args.chapter_id, args.chat)
