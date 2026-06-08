"""
HY-TUTOR: LEVEL 5 DYNAMIC LIVE TUTOR (command_6_tutor.py)
Target Hardware: Asus TUF F15 (RTX 2050 4GB VRAM, 8GB System RAM)
Local Pre-Classification: gemma4:e2b globally via Ollama API
Remote Deep Reasoning: gemma-4-31b-it (High Thinking) via Modernized Google GenAI SDK
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from utils.inference import call_gemini
from utils.genai_client import get_default_model
from utils.logging_utils import (
    log_init, log_process, log_success, log_warning, log_error, log_debug,
    log_critical
)
from utils.paths import SubjectPaths, resolve_subject
from typing import Optional

OLLAMA_URL = "http://localhost:11434/api/generate"
LOCAL_CLASSIFICATION_MODEL = "gemma4:e2b"


def check_ollama_health(timeout: int = 2) -> bool:
    """Check if Ollama server is running and accessible."""
    try:
        req = urllib.request.Request(
            f"{OLLAMA_URL}/tags",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                tags = json.loads(response.read().decode("utf-8"))
                models = tags.get("models", [])
                model_names = [m.get("name", "") for m in models]
                if LOCAL_CLASSIFICATION_MODEL in model_names:
                    log_success("command_6_tutor", f"Ollama health check: Server running, model '{LOCAL_CLASSIFICATION_MODEL}' available")
                    return True
                else:
                    log_warning("command_6_tutor", f"Ollama health check: Server running but model '{LOCAL_CLASSIFICATION_MODEL}' not found")
                    return False
    except Exception as e:
        log_warning("command_6_tutor", f"Ollama health check failed: {e}")
        return False
    return False

def query_local_pre_classification(student_response: str, expected_solution: str) -> str:
    """On-Device Pre-classification: Evaluates mistake tier via Local Ollama with fallback."""
    log_process("command_6_tutor", "Triggering On-Device Pre-classification via Local Ollama...")
    
    # Check if Ollama is available
    if not check_ollama_health():
        log_warning("command_6_tutor", "Ollama not available. Using fallback keyword-based classification.")
        # Simple keyword-based fallback classification
        student_lower = student_response.lower()
        confident_keywords = ["know", "understand", "studied", "i know", "i understand", 
                            "i've studied", "i learned", "i'm confident"]
        if any(keyword in student_lower for keyword in confident_keywords):
            log_debug("command_6_tutor", "Fallback classification: TIER_1 (confident keywords detected)")
            return "TIER_1"
        log_debug("command_6_tutor", "Fallback classification: TIER_2_3 (no confident keywords)")
        return "TIER_2_3"
    
    prompt = f"""
Analyze the student's answer against the expected correct step/solution.
Determine if the mistake is:
- TIER_1: A simple arithmetic mistake, typo, minor operational sign swap, or minor calculation slip.
- TIER_2_3: A severe conceptual failure, complete misapplication of mathematical rules, or complete blank state.

Expected Solution: {expected_solution}
Student's Response: {student_response}

Output ONLY the tier designation as a single word: TIER_1 or TIER_2_3. Do not explain.
"""
    
    payload = {
        "model": LOCAL_CLASSIFICATION_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0
        }
    }
    
    try:
        req = urllib.request.Request(
            OLLAMA_URL, 
            data=json.dumps(payload).encode("utf-8"), 
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            classification = res_data.get("response", "").strip().upper()
            if "TIER_1" in classification:
                log_debug("command_6_tutor", "Ollama classification: TIER_1")
                return "TIER_1"
            log_debug("command_6_tutor", "Ollama classification: TIER_2_3")
            return "TIER_2_3"
    except Exception as e:
        log_warning("command_6_tutor", f"Ollama classification failed: {e}. Using fallback.")
        # Fallback to keyword-based classification
        student_lower = student_response.lower()
        if any(keyword in student_lower for keyword in ["know", "understand", "studied"]):
            return "TIER_1"
        return "TIER_2_3"

def load_pedagogical_assets(chunk_paths: dict) -> tuple[str, dict]:
    """Loads per-subject Unified_Lesson.md and Active_Chunk_Problems.json
    assets generated in Level 4. ``chunk_paths`` is the output of
    :meth:`SubjectPaths.chunk_paths`.
    """
    lesson_path = chunk_paths["lesson"]
    problems_path = chunk_paths["problems"]

    if not lesson_path.exists() or not problems_path.exists():
        log_critical("command_6_tutor", f"Upstream dependencies missing for subject. Expected: {lesson_path} and {problems_path}")
        sys.exit(1)

    with open(lesson_path, "r", encoding="utf-8") as f:
        lesson_md = f.read()
    with open(problems_path, "r", encoding="utf-8") as f:
        problems_json = json.load(f)

    log_debug("command_6_tutor", f"Loaded pedagogical assets: lesson={len(lesson_md)} chars, problems={len(problems_json.get('problems', []))} items")
    return lesson_md, problems_json

def get_future_milestones(active_workspace: Path, current_chunk_index: int) -> list[str]:
    """Retrieves list of blacklisted future milestones from the per-subject
    active workspace to safeguard active pacing.
    """
    if not active_workspace.exists():
        log_debug("command_6_tutor", "No active workspace found for future milestones check")
        return []
    try:
        with open(active_workspace, "r", encoding="utf-8") as f:
            data = json.load(f)
        chunks = data.get("chunks", [])
        future_milestones = [c.get("milestone_alignment") for c in chunks if c.get("chunk_index") > current_chunk_index]
        log_debug("command_6_tutor", f"Found {len(future_milestones)} future milestones beyond chunk {current_chunk_index}")
        return future_milestones
    except Exception as e:
        log_warning("command_6_tutor", f"Failed to read future milestones: {e}")
        return []

def generate_remote_response(
    model_name: str,
    lesson_context: str,
    active_problems: dict,
    dialogue_history: list,
    latest_student_response: str,
    mistake_tier: str,
    consecutive_attempts: int,
    forbidden_milestones: list[str]
) -> str:
    """Escalates dialogue to remote engine with strict contextual sync and 5-pass resiliency."""
    log_process("command_6_tutor", f"Activating Remote Socratic Core ({model_name}) | Triage: {mistake_tier}")
    
    current_problem = active_problems.get("problems", [{}])[0]
    expected_solution = current_problem.get("solution_step_latex", "N/A")
    question_text = current_problem.get("question_text_latex", "N/A")

    forbidden_str = "\n".join([f"- {m}" for m in forbidden_milestones]) if forbidden_milestones else "None"

    system_instruction = f"""
You are the Socratic Dynamic Live Tutor (Command 6) for the HY-TUTOR system.
Pacing Ratios: 20% Baseline Theory, 70% Active Math Practice, 10% Visualizations.

=== 📖 ACTIVE STUDY MATERIAL (YOUR STRICT KNOWLEDGE BASE) ===
{lesson_context}

=== CURRENT WORKING PROBLEM ===
Question: {question_text}
Expected Derivation: {expected_solution}

CRITICAL KNOWLEDGE SYNC DIRECTIVE:
You are strictly bound to the "Active Study Material" provided above. You must read it deeply and base ALL of your hints, proofs, and explanations ONLY on the theorems and competitive bridges explicitly documented within it. Do not hallucinate outside formulas or teach advanced methods unless they are explicitly defined in the provided text.

=== COGNITIVE PREREQUISITE PROTECTION SHIELD ===
The student has NOT yet studied these future milestones:
{forbidden_str}

STRICT INSTRUCTION:
You are forbidden from asking the student to apply concepts belonging to the blacklisted future milestones. Focus entirely on the current milestone boundaries.

TRIAGE DIRECTIONS:
Mistake classification: {mistake_tier} (attempts: {consecutive_attempts})
- TIER_1: Provide a subtle immediate hint pointing to a calculation slip or variable adjustment.
- TIER_2_3 (attempts < 3): conceptual re-anchoring hint back to basic lesson axioms inside the Active Study Material.
- attempts >= 3: Step-by-step math derivation in beautiful LaTeX, explicitly logging progress evaluation.

Maintain character at all times. Use standard LaTeX wrapping ($...$ or $$...$$).
"""

    # Lazy import: only the tutor needs google.genai Content/Part structures
    from google.genai import types

    contents = []
    for msg in dialogue_history:
        role_map = "user" if msg["role"] == "user" else "model"
        contents.append(
            types.Content(
                role=role_map,
                parts=[types.Part.from_text(text=msg["content"])]
            )
        )
    contents.append(
        types.Content(role="user", parts=[types.Part.from_text(text=latest_student_response)])
    )

    # Inference via Gateway (multi-turn contents) - automatic logging + retries
    # The latest user turn is already appended to `contents`, so `prompt` is a no-op string.
    try:
        tutor_text, _model_used = call_gemini(
            "command_6_tutor",
            model_name,
            prompt=latest_student_response,  # placeholder; contents= overrides it
            contents=contents,
            system_prompt=system_instruction,
            temperature=0.3,
            max_retries=5,
        )
        return tutor_text
    except RuntimeError as e:
        log_error("command_6_tutor", f"Tutor core failed after retries: {e}")
        sys.exit(1)

def execute_command_6_pipeline(
    chapter_id: str,
    chunk_index: int,
    student_input: str,
    history_file_path: Path,
    subject: Optional[str] = None,
):
    """Orchestrates the live tutoring triage and preemption shield loops.
    Reads the per-subject lesson, problems, and active workspace files
    and writes the chat history to the caller-supplied
    ``history_file_path`` (which Phase 7 will move to per-subject).
    """
    try:
        resolved = resolve_subject(subject)
    except ValueError as e:
        log_error("command_6_tutor", f"{e}")
        sys.exit(1)

    paths = SubjectPaths.for_subject(resolved)
    paths.chunk_dir.mkdir(parents=True, exist_ok=True)
    log_init("command_6_tutor", f"Live Tutor initialized for {chapter_id} chunk {chunk_index} | Subject: {resolved}")
    log_debug("command_6_tutor", f"[PINNED] Per-subject workspace: {paths.root}")

    lesson_md, problems_json = load_pedagogical_assets(paths.chunk_paths())
    forbidden_milestones = get_future_milestones(paths.active_workspace, chunk_index)

    current_problem = problems_json.get("problems", [{}])[0]
    expected_solution = current_problem.get("solution_step_latex", "")

    mistake_tier = query_local_pre_classification(student_input, expected_solution)

    consecutive_attempts = 1
    dialogue_history = []
    if history_file_path.exists():
        try:
            with open(history_file_path, "r", encoding="utf-8") as f:
                history_data = json.load(f)
                dialogue_history = history_data.get("history", [])
                consecutive_attempts = history_data.get("consecutive_attempts", 0) + 1
        except Exception:
            pass

    MODEL_NAME = get_default_model("command_6_tutor")

    tutor_reply = generate_remote_response(
        model_name=MODEL_NAME,
        lesson_context=lesson_md,
        active_problems=problems_json,
        dialogue_history=dialogue_history,
        latest_student_response=student_input,
        mistake_tier=mistake_tier,
        consecutive_attempts=consecutive_attempts,
        forbidden_milestones=forbidden_milestones
    )

    dialogue_history.append({"role": "user", "content": student_input})
    dialogue_history.append({"role": "tutor", "content": tutor_reply})

    history_payload = {
        "chapter_id": chapter_id,
        "chunk_index": chunk_index,
        "consecutive_attempts": 0 if "logged for" in tutor_reply.lower() else consecutive_attempts,
        "last_mistake_tier": mistake_tier,
        "history": dialogue_history
    }

    with open(history_file_path, "w", encoding="utf-8") as f:
        json.dump(history_payload, f, indent=4)

    log_success("command_6_tutor", "Tutor response generated successfully")
    print("\n=== TUTOR RESPONSE BEGIN ===")
    print(tutor_reply)
    print("=== TUTOR RESPONSE END ===")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HY-TUTOR Command 6 Live Tutor")
    parser.add_argument("chapter_id", nargs="?", help="Target Chapter ID (e.g., CH_12_03)")
    parser.add_argument("chunk_index", nargs="?", help="Active chunk index (integer)")
    parser.add_argument("student_input", nargs="?", help="Student's latest message text")
    parser.add_argument("history_file", nargs="?", help="Path to the per-session chat history JSON")
    parser.add_argument("--subject", type=str, default=None,
                        help="Active subject (e.g., mathematics). If omitted, "
                             "resolved from the environment / pointer.")
    args = parser.parse_args()
    if not all([args.chapter_id, args.chunk_index is not None, args.student_input, args.history_file]):
        # Preserve the original bare-arg behaviour: silent exit 1
        # (this is the test_subprocess contract).
        sys.exit(1)
    execute_command_6_pipeline(
        args.chapter_id,
        int(args.chunk_index),
        args.student_input,
        Path(args.history_file),
        subject=args.subject,
    )
