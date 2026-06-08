"""
HY-TUTOR: LEVEL 4 QUESTION EVALUATOR & EXEMPLAR INJECTOR (command_5_5_injector.py)
Target Hardware: Asus TUF F15 (RTX 2050 4GB VRAM, 8GB System RAM)
Model Engine: Gemini 3.1 Flash-Lite (High Thinking for Consolidation Only) & Gemini Embedding 2
Iteratively processes raw exemplar documents in large 5000-word semantic slices to extract,
validate, and generate high-yield math variants mapped strictly to NCERT milestones without latency.
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
from utils.usage_tracker import record_inference
from utils.genai_client import get_default_model

# --- SCHEMAS ---
class PracticeProblem(BaseModel):
    problem_id: str = Field(..., description="Unique ID: e.g., 'EXEMPLAR_01' or 'VARIANT_01'")
    problem_type: str = Field(..., description="Strictly one of: 'EXEMPLAR_SEED' or 'AI_STRUCTURAL_VARIANT'")
    question_text_latex: str = Field(..., description="The problem statement formatted in clean, professional LaTeX.")
    solution_step_latex: str = Field(..., description="The step-by-step mathematical derivation formatted in LaTeX.")
    difficulty_tier: str = Field(..., description="Strictly one of: 'TIER_1', 'TIER_2', 'TIER_3'")
    problem_embedding: Optional[List[float]] = Field(default=None, description="Semantic vector for mistake profiling.")

class SegmentProblemMining(BaseModel):
    contains_matching_problems: bool = Field(..., description="True if this exemplar segment contains problems aligned to the active milestone.")
    mined_raw_problems_markdown: str = Field(..., description="Verbatim markdown copy of any questions and solutions aligned to the NCERT anchor.")

class ActiveChunkProblems(BaseModel):
    active_chapter_id: str
    chunk_index: int
    problem_selection_reasoning: str = Field(..., description="Brief log outlining why specific problems were approved and why out-of-scope concepts were dropped.")
    problems: List[PracticeProblem]

def load_ncert_reference_anchor(active_chunk_dir: Path) -> tuple[str, str, str]:
    """Safely extracts active milestone context, subject, and standard theory elements from NCERT_chunk.json."""
    ncert_path = active_chunk_dir / "NCERT_chunk.json"
    if not ncert_path.exists():
        print(f"[CRITICAL ERROR] Missing Upstream Dependency: NCERT core chunk not found at {ncert_path}")
        print("[HALT] Run command_2_miner.py before executing the Exemplar Injector.")
        sys.exit(1)

    try:
        with open(ncert_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            subject = data.get("subject", "mathematics").lower()
            milestone = data.get("milestone_alignment", "UNKNOWN_MILESTONE")
            
            # Reconstruct the NCERT standard baseline definitions to ground problem extraction
            ncert_theorems_dump = ""
            elements = data.get("extracted_elements", [])
            for el in elements:
                if el.get("element_type") in ["VERBATIM_THEORY", "LATEX_FORMULA"]:
                    ncert_theorems_dump += f"\n- {el.get('content')}"
            
            return milestone, subject, ncert_theorems_dump
    except Exception as e:
        print(f"[CRITICAL ERROR] Failed parsing upstream NCERT miner output: {e}")
        sys.exit(1)

def locate_and_read_exemplar_text(exemplar_dir: Path, subject: str, chapter_id: str) -> str:
    """Scans and reads NCERT exemplar files with domain-isolated path verification."""
    possible_targets = [
        exemplar_dir / subject.lower() / f"{chapter_id}.md",
        exemplar_dir / subject.lower() / f"{chapter_id}.txt",
        exemplar_dir / subject.capitalize() / f"{chapter_id}.md",
        exemplar_dir / subject.capitalize() / f"{chapter_id}.txt",
        exemplar_dir / f"{chapter_id}.md",
        exemplar_dir / f"{chapter_id}.txt"
    ]

    selected_path: Optional[Path] = None
    for path in possible_targets:
        if path.exists():
            selected_path = path
            break

    if not selected_path:
        print(f"[WARNING] Raw Exemplar textbook target missing for {chapter_id} inside {exemplar_dir}")
        print(f"Scanned Paths checked: {[str(p) for p in possible_targets]}")
        print("[PROCESS] Proceeding with empty problems container.")
        return ""

    print(f"[SUCCESS] Located Exemplar manual at: {selected_path}")
    with open(selected_path, "r", encoding="utf-8") as f:
        return f.read().strip()

def split_text_into_semantic_segments(text: str, max_words: int = 5000) -> List[str]:
    """Divides raw book text into larger logical segments matching paragraph limits to maximize efficiency."""
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = []
    current_word_count = 0

    for para in paragraphs:
        word_count = len(para.split())
        if current_word_count + word_count > max_words and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [para]
            current_word_count = word_count
        else:
            current_chunk.append(para)
            current_word_count += word_count

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
    
    return chunks

def get_future_milestones(active_workspace: Path, current_chunk_index: int) -> list[str]:
    """Gathers downstream milestones from the per-subject active workspace
    file to build the Preemption Protection Shield.
    """
    if not active_workspace.exists():
        return []
    try:
        with open(active_workspace, "r", encoding="utf-8") as f:
            data = json.load(f)
        chunks = data.get("chunks", [])
        return [c.get("milestone_alignment") for c in chunks if c.get("chunk_index") > current_chunk_index]
    except Exception:
        return []

def execute_command_5_5_pipeline(chapter_id: str, chunk_index: int, subject: Optional[str] = None):
    from utils.paths import SubjectPaths, resolve_subject, NCERT_EXEMPLARS_DIR

    try:
        resolved = resolve_subject(subject)
    except ValueError as e:
        print(f"[FATAL ERROR] {e} (set --subject or HY_TUTOR_SUBJECT)")
        sys.exit(1)

    print(f"\n[INITIALIZING] Command 5.5 Exemplar Injector for {chapter_id} | Chunk: {chunk_index} | Subject: {resolved}")

    paths = SubjectPaths.for_subject(resolved)
    paths.chunk_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load Grounding Reference Data
    current_milestone, subject, ncert_baseline = load_ncert_reference_anchor(paths.chunk_dir)
    raw_exemplar_text = locate_and_read_exemplar_text(NCERT_EXEMPLARS_DIR, subject, chapter_id)
    future_milestones = get_future_milestones(paths.active_workspace, chunk_index)
    print(f"[PINNED] Per-subject workspace: {paths.root}")

    # Early escape if no raw exemplar textbook is present
    if not raw_exemplar_text:
        fallback_payload = ActiveChunkProblems(
            active_chapter_id=chapter_id,
            chunk_index=chunk_index,
            problem_selection_reasoning="No raw exemplar reference text staged on disk. Skipping injection.",
            problems=[]
        )
        output_path = paths.chunk_paths()["problems"]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(fallback_payload.model_dump(), f, indent=4)
        print(f"[SUCCESS] Exemplar Injector completed (Fallback Mode). Saved to: {output_path}")
        return

    # 2. Slice Raw Exemplar Textbook into logical blocks of 5000 words to minimize execution count
    exemplar_slices = split_text_into_semantic_segments(raw_exemplar_text, max_words=5000)
    print(f"[TEXT CHUNKER] Exemplar manual divided into {len(exemplar_slices)} high-capacity segments.")

    # 3. Model Configuration
    MODEL_NAME = get_default_model("command_5_5_injector")
    EMBEDDING_MODEL = "gemini-embedding-2"

    # =========================================================================
    # PHASE 1: SLIDING-WINDOW EXEMPLAR EXTRACTION LOOP (Accumulate Raw Text)
    # =========================================================================
    accumulated_raw_problems = ""
    future_milestones_str = "\n".join([f"- {m}" for m in future_milestones]) if future_milestones else "None"

    for idx, segment in enumerate(exemplar_slices):
        print(f"[PIPELINE LOOP] Mining Exemplar Segment {idx + 1}/{len(exemplar_slices)}...")
        
        prompt_phase1 = f"""
        You are the Question Evaluator (Phase 1) for the HY-TUTOR local system.
        Your task is to analyze this segment of the NCERT Exemplar manual and extract questions that align with the studied NCERT concept milestone.

        === CONCEPTUAL ALIGNMENT ANCHOR (STUDIED TOPICS) ===
        Target Milestone: {current_milestone}
        Core Theoretical Baseline:
        {ncert_baseline}

        === COGNITIVE PREREQUISITE PROTECTION SHIELD (FORBIDDEN OUT-OF-BOUNDS TOPICS) ===
        Do NOT extract any problems requiring theorems or mechanics from these future milestones:
        {future_milestones_str}

        === CURRENT EXEMPLAR TEXT PORTION ===
        {segment}

        EXTRACTION DIRECTIONS:
        1. THE COMPATIBILITY MATCH: Check if the segment contains problems directly testing the definitions, properties, or concepts of the studied NCERT milestone ('{current_milestone}').
        2. EXHAUSTIVE VERBATIM RETRIEVAL: If a question matches, extract the problem statement and the step-by-step mathematical derivation exactly as-is, unsummarized, in full depth.
        3. SHIELD ENFORCEMENT: If a problem requires concepts from the Protection Shield (downstream unstudied milestones), drop it immediately.
        4. LaTeX NOTATION: All formulas, matrices, and equations must be wrapped in strict LaTeX layout ($ or $$).
        """

        # Optimized Phase 1: Fast parsing with high VRAM throughput (Thinking Disabled)
        # Inference via Gateway - automatic logging + retries
        try:
            raw_text, _model_used = call_gemini(
                "command_5_5_injector",
                MODEL_NAME,
                prompt_phase1,
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=SegmentProblemMining,
                max_retries=5,
            )
        except RuntimeError as e:
            print(f"[FATAL ERROR] Command 5.5 Phase 1 failed on segment {idx + 1} after retries: {e}")
            sys.exit(1)

        # Clean markdown if present
        raw_text = (raw_text or "").strip()
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            if lines[0].startswith("```json") or lines[0].startswith("```"):
                raw_text = "\n".join(lines[1:-1])

        try:
            segment_data = json.loads(raw_text.strip())
            if segment_data.get("contains_matching_problems") and segment_data.get("mined_raw_problems_markdown"):
                mined_text = segment_data.get("mined_raw_problems_markdown").strip()
                accumulated_raw_problems += f"\n\n<!-- Segment {idx + 1} Mined -->\n" + mined_text
                print(f"[PHASE 1 SUCCESS] Mined matching practice problems from Segment {idx + 1}.")
            else:
                print(f"[PHASE 1 SKIP] Segment {idx + 1} contained no matching standard numericals.")
        except json.JSONDecodeError as parse_err:
            print(f"[WARNING] Failed parsing Phase 1 output from segment {idx + 1}: {parse_err}")

    # =========================================================================
    # PHASE 2: MASTER CONSOLIDATION & VARIANT SYNTHESIS (Compile & Diversify)
    # =========================================================================
    print(f"\n[PHASE 2] Initiating Master Consolidation & Variant Synthesis Pass...")
    total_accumulated_words = len(accumulated_raw_problems.split())
    print(f"[VOLUME REPORT] Mined Raw Problems Pool contains {total_accumulated_words} words.")

    if total_accumulated_words == 0:
        print("[PROCESS] Mined pool is empty. Writing empty problems container payload.")
        empty_payload = ActiveChunkProblems(
            active_chapter_id=chapter_id,
            chunk_index=chunk_index,
            problem_selection_reasoning="No compatible exemplar exercises found for this milestone segment.",
            problems=[]
        )
        output_path = paths.chunk_paths()["problems"]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(empty_payload.model_dump(), f, indent=4)
        print(f"[SUCCESS] Finished Exemplar Injector (Consolidation Fallback). Saved to: {output_path}")
        return

    prompt_phase2 = f"""
    You are the Lead Master Compiler and Variant Synthesizer (Phase 2) for the HY-TUTOR system.
    Your task is to take the entire raw compiled pool of mined exemplar questions and compile them into a balanced study set under the Pydantic ActiveChunkProblems schema.

    === CONCEPTUAL ALIGNMENT ANCHOR ===
    Active Milestone: {current_milestone}
    Core Theoretical Baseline:
    {ncert_baseline}

    === CONSOLIDATED RAW PRACTICE EXERCISES ===
    {accumulated_raw_problems}

    STRICT COMPILATION LAWS:
    1. EXCLUSIVITY CHECK: Filter out duplicate problems. Group approved extracted exemplar questions cleanly as 'EXEMPLAR_SEED' elements.
    2. STRUCTURAL VARIANT SYNTHESIS: Generate 1 to 2 'AI_STRUCTURAL_VARIANT' companion questions. A variant must:
       - Mirror the exact logical structure of a parsed exemplar seed.
       - Alter numerical parameters, variables, matrix dimensions, or scenario conditions.
       - Keep the math challenging but direct, providing a complete step-by-step solution in solution_step_latex.
    3. PACING TARGET: Return exactly 3 to 4 total problems in the final list, assigning them to 'TIER_1', 'TIER_2', or 'TIER_3' based on mathematical complexity.
    4. LaTeX INTEGRITY: Every problem statement, equation, variable, and step-by-step solution must use proper standard LaTeX wrapping ($...$ or $$...$$).
    """

    # Active reasoning remains exclusively during Phase 2 Consolidation & Variant synthesis
    # Inference via Gateway - automatic logging + retries
    try:
        raw_text, _model_used = call_gemini(
            "command_5_5_injector",
            MODEL_NAME,
            prompt_phase2,
            temperature=0.2,
            response_mime_type="application/json",
            response_schema=ActiveChunkProblems,
            max_retries=5,
        )
    except RuntimeError as e:
        print(f"[FATAL ERROR] Command 5.5 Phase 2 Consolidation failed after retries: {e}")
        sys.exit(1)

    # Clean markdown if present
    raw_text = (raw_text or "").strip()
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        if lines[0].startswith("```json") or lines[0].startswith("```"):
            raw_text = "\n".join(lines[1:-1])

    try:
        problems_json = json.loads(raw_text.strip())
        problems_json["chunk_index"] = chunk_index
        problems_json["active_chapter_id"] = chapter_id

        problems = problems_json.get("problems", [])
        print(f"[CONSOLIDATION REPORT] Successfully compiled {len(problems)} practice problems (Seeds + Variants).")

        # =========================================================================
        # PHASE 3: VECTORIZATION (Generate Semantic Embeddings) - kept as direct call
        # Wrapped with manual record_inference() to ensure embedding usage is also logged.
        # =========================================================================
        if problems:
            print(f"[PROCESS] Vectorizing consolidated exercises using {EMBEDDING_MODEL} for mistake profiling...")
            problem_texts = [f"{p['difficulty_tier']} - {p['question_text_latex']}" for p in problems]
            try:
                from google import genai
                from google.genai import types
                _embed_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
                _start = time.time()
                embed_response = _embed_client.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=problem_texts,
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_DOCUMENT",
                        output_dimensionality=3072
                    )
                )
                record_inference(
                    command="command_5_5_injector",
                    model=EMBEDDING_MODEL,
                    provider="google_genai",
                    status="success",
                    duration_ms=int((time.time() - _start) * 1000),
                    prompt="",
                    response_text="",
                    response=embed_response,
                    api_key=os.getenv("GEMINI_API_KEY"),
                )
                for i, embedding in enumerate(embed_response.embeddings):
                    problems_json["problems"][i]["problem_embedding"] = embedding.values
            except Exception as embed_err:
                print(f"[WARNING] Question embedding generation skipped. Error: {embed_err}")

        # =========================================================================
        # PHASE 4: WRITE DATA TO WORKSPACE CACHE
        # =========================================================================
        OUTPUT_PROBLEMS_PATH = paths.chunk_paths()["problems"]
        with open(OUTPUT_PROBLEMS_PATH, "w", encoding="utf-8") as f:
            json.dump(problems_json, f, indent=4)

        print(f"[SUCCESS] Command 5.5 executed successfully.")
        print(f"Staged finalized practice pool payload to: -> {OUTPUT_PROBLEMS_PATH}")

        # Phase 2.1: Index to per-subject vector DB (best-effort).
        try:
            from utils.vector_db import index_active_chunk as _iac
            _stats = _iac(paths, chapter_id, resolved, chunk_index)
            print(f"[VECTOR_DB] Index result for {chapter_id} chunk {chunk_index}: {_stats}")
        except Exception as _e:
            print(f"[VECTOR_DB] Indexing skipped (non-fatal): {_e}")
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed parsing consolidated JSON: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Failed writing payload state: {e}")
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HY-TUTOR Command 5.5 Exemplar Injector")
    parser.add_argument("chapter_id", nargs="?", help="Target Chapter ID")
    parser.add_argument("chunk_index", nargs="?", help="Chunk index (integer)")
    parser.add_argument("--subject", type=str, default=None,
                        help="Active subject (e.g., mathematics). If omitted, "
                             "resolved from the environment / pointer.")
    args = parser.parse_args()
    if not args.chapter_id or args.chunk_index is None:
        print("Usage: python command_5_5_injector.py <Chapter_ID> <Chunk_Index>")
        sys.exit(1)
    execute_command_5_5_pipeline(args.chapter_id, int(args.chunk_index), subject=args.subject)
