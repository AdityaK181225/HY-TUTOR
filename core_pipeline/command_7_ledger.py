"""
HY-TUTOR: LEVEL 5 SESSION CLOSER & LEDGER (command_7_ledger.py)
Target Hardware: Asus TUF F15 (RTX 2050 4GB VRAM, 8GB System RAM)
Model Engine: gemma-4-31b-it (High Thinking) via Modernized Google GenAI SDK
"""

import os
import sys
import json
import time
import shutil
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from utils.inference import call_gemini
from utils.genai_client import get_default_model
from utils.paths import SubjectPaths, resolve_subject

class SessionDiagnostics(BaseModel):
    proficiency_score: int = Field(..., description="Integer from 0 to 100 representing the student's mastery based on errors vs. hints.")
    master_notes: str = Field(..., description="Summary of key insights, formulas, and resolved doubts extracted from the chat.")
    problems_verified: str = Field(..., description="Summary of the mathematical practice problems successfully solved.")
    diagnostic_summary: str = Field(..., description="A 2-3 sentence analysis of the student's cognitive performance, pinpointing specific strengths or weaknesses.")

def load_session_history(history_path: Path) -> dict:
    if not history_path.exists():
        print(f"[CRITICAL ERROR] Upstream Dependency Missing: Session history not found at {history_path}")
        print("[HALT] Cannot close session without valid interaction logs.")
        sys.exit(1)
    try:
        with open(history_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[CRITICAL ERROR] Failed parsing active session history: {e}")
        sys.exit(1)

def get_active_topic(active_chunk_dir: Path) -> str:
    ncert_path = active_chunk_dir / "NCERT_chunk.json"
    if ncert_path.exists():
        try:
            with open(ncert_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("milestone_alignment", "Unknown Concept")
        except Exception:
            pass
    return "Unknown Concept"

def update_global_tracker(chapter_id: str, chunk_index: int, topic_name: str, proficiency_score: int):
    from utils.paths import GLOBAL_TRACKER_PATH
    if not GLOBAL_TRACKER_PATH.exists():
        print("[WARNING] Global_Subject_Tracker.json not found. Skipping long-term ledger mutation.")
        return

    try:
        with open(GLOBAL_TRACKER_PATH, "r", encoding="utf-8") as f:
            tracker_data = json.load(f)

        is_weak = proficiency_score < 70
        action_logged = False

        if "chapters_ledger" in tracker_data and chapter_id in tracker_data["chapters_ledger"]:
            chapter_node = tracker_data["chapters_ledger"][chapter_id]
            weak_areas = chapter_node.get("weak_areas_flagged", [])
            existing_flag = next((item for item in weak_areas if item.get("chunk_index") == chunk_index), None)

            if is_weak:
                if existing_flag:
                    existing_flag["is_weak_area"] = True
                else:
                    weak_areas.append({"topic": topic_name, "chunk_index": chunk_index, "is_weak_area": True})
                print(f"[LEDGER UPDATE] Proficiency ({proficiency_score}%) < 70%. Concept '{topic_name}' flagged as WEAK AREA.")
                action_logged = True
            else:
                if existing_flag and existing_flag.get("is_weak_area"):
                    existing_flag["is_weak_area"] = False
                    print(f"[LEDGER UPDATE] Proficiency ({proficiency_score}%) >= 70%. Concept '{topic_name}' cleared from WEAK AREAS.")
                    action_logged = True
                else:
                    print(f"[LEDGER UPDATE] Proficiency ({proficiency_score}%) >= 70%. Mastery confirmed.")

            if action_logged:
                chapter_node["weak_areas_flagged"] = weak_areas
                tracker_data["chapters_ledger"][chapter_id] = chapter_node
                with open(GLOBAL_TRACKER_PATH, "w", encoding="utf-8") as f:
                    json.dump(tracker_data, f, indent=4)
                    
    except Exception as e:
        print(f"[ERROR] Failed to update Global Subject Tracker: {e}")

def advance_active_chunk_and_clear_cache(
    chapter_id: str,
    active_workspace: Path,
    active_chunk_dir: Path,
):
    """Increments the active chunk index and safely wipes the physical
    payload cache. Operates on per-subject paths.
    """
    if active_workspace.exists():
        try:
            with open(active_workspace, "r", encoding="utf-8") as f:
                data = json.load(f)

            if data.get("active_chapter_id") == chapter_id:
                current_idx = data.get("current_active_chunk_index", 0)
                total_chunks = data.get("total_chunks_in_chapter", 1)

                new_idx = current_idx + 1
                data["current_active_chunk_index"] = new_idx

                with open(active_workspace, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                print(f"[STATE ADVANCEMENT] Chapter '{chapter_id}' advanced to Chunk {new_idx}.")

                if new_idx >= total_chunks:
                    print(f"[STATE ADVANCEMENT] You have reached the end of Chapter '{chapter_id}'!")
        except Exception as e:
            print(f"[ERROR] Failed to update volatile workspace: {e}")

    if active_chunk_dir.exists():
        try:
            for item in active_chunk_dir.iterdir():
                if item.is_file():
                    item.unlink()
            print("[STATE ADVANCEMENT] Cleared physical chunk cache. Ready for next pipeline generation.")
        except Exception as e:
            print(f"[ERROR] Failed to clear active chunk directory: {e}")

def execute_command_7_pipeline(
    chapter_id: str,
    chunk_index: int,
    history_file_path: Path,
    subject: Optional[str] = None,
):
    print(f"\n[INITIALIZING] Command 7 Session Closer & Ledger for {chapter_id} | Chunk: {chunk_index}")

    try:
        resolved = resolve_subject(subject)
    except ValueError as e:
        print(f"[FATAL ERROR] {e}")
        sys.exit(1)

    paths = SubjectPaths.for_subject(resolved)
    print(f"[PINNED] Per-subject workspace: {paths.root}")

    history_data = load_session_history(history_file_path)
    topic_name = get_active_topic(paths.chunk_dir)
    dialogue_log = history_data.get("history", [])

    if not dialogue_log:
        print("[PROCESS] No dialogue history found. Exiting ledger.")
        return

    MODEL_NAME = get_default_model("command_7_ledger")
    print(f"[PROCESS] Dispatching session history to {MODEL_NAME} for diagnostic parsing...")

    prompt = f"""
    You are the Session Closer & Ledger (Command 7) for the HY-TUTOR system.
    Your task is to analyze the following student-tutor dialogue history and extract performance metrics.

    Target Chapter: {chapter_id}
    Active Topic: {topic_name}

    === DIALOGUE HISTORY ===
    {json.dumps(dialogue_log, indent=2)}

    MANDATORY RULES:
    1.  Calculate a 'proficiency_score' (integer 0-100). Subtract points for repeated errors, conceptual misunderstandings, or needing excessive hints.
    2.  Compile 'master_notes' containing any core formulas or axioms the tutor had to reinforce.
    3.  Summarize 'problems_verified' to list what mathematical hurdles the student cleared.
    4.  Provide a 'diagnostic_summary' pinpointing exactly where their analytical mechanics are strong or weak.
    """

    # Model Inference via Inference Gateway (automatic logging + retries)
    try:
        raw_text, _model_used = call_gemini(
            "command_7_ledger",
            MODEL_NAME,
            prompt,
            temperature=0.1,
            response_mime_type="application/json",
            response_schema=SessionDiagnostics,
            max_retries=5,
        )
    except RuntimeError as e:
        print(f"[FATAL FAILURE] Ledger failed after retries: {e}")
        sys.exit(1)

    # Clean markdown if present
    raw_text = (raw_text or "").strip()
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        if lines[0].startswith("```json") or lines[0].startswith("```"):
            raw_text = "\n".join(lines[1:-1])

    try:
        diagnostics = json.loads(raw_text.strip())
        score = diagnostics.get("proficiency_score", 100)

        update_global_tracker(chapter_id, chunk_index, topic_name, score)

        if score >= 70:
            advance_active_chunk_and_clear_cache(
                chapter_id, paths.active_workspace, paths.chunk_dir
            )

        print("\n=== MASTER_NOTES ===")
        print(diagnostics.get("master_notes", ""))
        print("\n=== PROBLEMS ===")
        print(diagnostics.get("problems_verified", ""))
        print("\n=== DIAGNOSTICS ===")
        print(diagnostics.get("diagnostic_summary", ""))
        print(f"\n[SYSTEM_FINAL] Proficiency Score Logged: {score}%")

    except json.JSONDecodeError as e:
        print(f"[LLM EXECUTION FAULT] Ledger JSON parsing failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[LLM EXECUTION FAULT] Ledger execution pass aborted: {e}")
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HY-TUTOR Command 7 Session Closer & Ledger")
    parser.add_argument("chapter_id", nargs="?", help="Target Chapter ID")
    parser.add_argument("chunk_index", nargs="?", help="Active chunk index (integer)")
    parser.add_argument("history_file", nargs="?", help="Path to the chat history JSON")
    parser.add_argument("--subject", type=str, default=None,
                        help="Active subject (e.g., mathematics). If omitted, "
                             "resolved from the environment / pointer.")
    args = parser.parse_args()
    if not all([args.chapter_id, args.chunk_index is not None, args.history_file]):
        print("Usage: python command_7_ledger.py <Chapter_ID> <Chunk_Index> <History_JSON_Path>")
        sys.exit(1)
    execute_command_7_pipeline(
        args.chapter_id,
        int(args.chunk_index),
        Path(args.history_file),
        subject=args.subject,
    )
