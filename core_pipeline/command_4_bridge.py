"""
HY-TUTOR: LEVEL 4 COMPETITIVE BRIDGE (command_4_bridge.py)
Target Hardware: Asus TUF F15 (RTX 2050 4GB VRAM, 8GB System RAM)
Model Engine: Gemini 3.1 Flash-Lite (High Thinking)
Configured with exponential backoff and absolute math logic preservation.

June 2026 refactor (topic-coherence enforcement):
  The bridge is now GROUNDED in the active NCERT chunk.  The model
  itself curates 0..N bridge insights that flow directly from the
  NCERT chunk's own concepts.  The reference book is reduced to a
  secondary "inspiration pool" that the model may draw from only if
  the shortcut's prerequisites are already introduced in the NCERT
  chunk.  Every bridge insight must declare its prerequisite_check
  and prerequisite_satisfied_in_ncert.  After generation, the
  pipeline post-processes the output: any insight where
  prerequisite_satisfied_in_ncert is false is moved to
  out_of_syllabus_warnings.
"""

import os
import sys
import json
import time
import re
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from utils.inference import call_gemini
from utils.genai_client import get_default_model

class BridgeInsight(BaseModel):
    concept_anchor: str = Field(..., description="The NCERT concept from the active chunk that this bridge extends.")
    bridge_explanation: str = Field(..., description="The cognitive touchpoint explaining HOW the NCERT concept naturally extends into a competitive shortcut or insight.")
    advanced_application: str = Field(..., description="An alternative problem setup or accelerated calculation methodology.")
    latex_formula_bridge: str = Field(..., description="Pristine LaTeX showing the mathematical transition from the NCERT formula to the shortcut ($...$ or $$...$$).")
    prerequisite_check: str = Field(..., description="One-sentence list of prerequisite concepts the shortcut requires (e.g. 'requires matrix multiplication and identity matrix').")
    prerequisite_satisfied_in_ncert: bool = Field(..., description="True ONLY if every prerequisite listed above is introduced in the active NCERT chunk. False otherwise.")

class BridgedChunkPayload(BaseModel):
    active_chapter_id: str
    chunk_index: int
    milestone_alignment: str
    cognitive_analysis_log: str = Field(..., description="Analyze the active NCERT chunk. Explain step-by-step what competitive or cognitive insight (if any) flows NATURALLY from the NCERT content alone. If the NCERT chunk is purely foundational (definitions, notation, elementary examples) and admits no genuine competitive shortcut without later concepts, say so explicitly.")
    bridge_insights: List[BridgeInsight]
    out_of_syllabus_warnings: List[str] = Field(..., description="List of advanced concepts dropped because their prerequisites are not in the active NCERT chunk.")

def load_upstream_dependencies(active_chunk_dir: Path) -> tuple[dict, dict]:
    ncert_path = active_chunk_dir / "NCERT_chunk.json"
    ref_path = active_chunk_dir / "Reference_chunk.json"
    if not ncert_path.exists() or not ref_path.exists():
        print(f"[CRITICAL ERROR] Missing Upstream Dependencies. NCERT: {ncert_path.exists()} | Reference: {ref_path.exists()}")
        sys.exit(1)
    with open(ncert_path, "r", encoding="utf-8") as f:
        ncert_data = json.load(f)
    with open(ref_path, "r", encoding="utf-8") as f:
        ref_data = json.load(f)
    return ncert_data, ref_data

def sanitize_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'[\ud800-\udfff]', '', text)
    return text.replace('\u0000', '').strip()

def execute_command_4_pipeline(chapter_id: str, chunk_index: int, subject: Optional[str] = None):
    from utils.paths import SubjectPaths, resolve_subject

    try:
        resolved = resolve_subject(subject)
    except ValueError as e:
        print(f"[FATAL ERROR] {e} (set --subject or HY_TUTOR_SUBJECT)")
        sys.exit(1)

    print(f"\n[INITIALIZING] Command 4 Competitive Bridge for {chapter_id} | Chunk: {chunk_index} | Subject: {resolved}")

    paths = SubjectPaths.for_subject(resolved)
    paths.chunk_dir.mkdir(parents=True, exist_ok=True)

    ncert_data, ref_data = load_upstream_dependencies(paths.chunk_dir)
    active_milestone = ncert_data.get("milestone_alignment", "UNKNOWN_MILESTONE")
    print(f"[PINNED] Per-subject workspace: {paths.root}")

    advanced_elements = ref_data.get("advanced_elements", [])
    ncert_has_content = bool(ncert_data.get("cleaned_text") or ncert_data.get("extracted_elements"))
    if not ncert_has_content:
        print("[CRITICAL ERROR] NCERT chunk has no content. Aborting bridge generation.")
        sys.exit(1)

    MODEL_NAME = get_default_model("command_4_bridge")

    # Use the FULL NCERT chunk (cleaned_text + extracted elements) as the
    # primary grounding context.  This is what the bridge is curated against.
    sanitized_ncert_full = sanitize_text(
        json.dumps(
            {
                "milestone_alignment": active_milestone,
                "cleaned_text": ncert_data.get("cleaned_text", ""),
                "extracted_elements": ncert_data.get("extracted_elements", []),
            },
            indent=2,
        )
    )
    sanitized_ref = sanitize_text(json.dumps(advanced_elements, indent=2))

    prompt = f"""
    You are the Competitive Bridge (Command 4) for the HY-TUTOR system.

    ============================================================
    CORE DIRECTIVE (READ FIRST)
    ============================================================
    The bridge you generate MUST be GROUNDED in the active NCERT
    chunk below.  You are NOT a free-form competitive-trick
    generator.  You are a curator: you may only emit bridge insights
    whose prerequisite concepts are introduced in the active NCERT
    chunk.

    If the active NCERT chunk is purely foundational (a definition,
    basic notation, or an elementary example) and admits no genuine
    competitive shortcut without later concepts, you SHOULD emit
    zero bridge_insights and explain that in the
    cognitive_analysis_log.  This is the CORRECT, expected output
    for many introductory milestones.  Do not invent shortcuts
    that depend on concepts the student has not yet seen.

    ============================================================
    Target Chapter: {chapter_id}
    Active Milestone: {active_milestone}
    ============================================================

    === STREAM 1: ACTIVE NCERT CHUNK (PRIMARY GROUNDING) ===
    {sanitized_ncert_full}

    === STREAM 2: ADVANCED REFERENCE SHORTCUTS (SECONDARY INSPIRATION ONLY) ===
    {sanitized_ref}

    Note: The reference shortcuts in Stream 2 are mined from across
    the entire chapter.  They may be from milestones the student
    has not reached yet.  Treat them as a brainstorming pool, not
    as a requirement.  For each candidate shortcut, you must check
    whether the prerequisite concepts are already introduced in
    Stream 1.  If they are not, the shortcut is OUT OF SCOPE for
    this chunk and must be moved to out_of_syllabus_warnings.

    ============================================================
    MANDATORY RULES
    ============================================================
    1. TOPIC-COHERENCE GATE: For every bridge insight you consider,
       first list the prerequisite concepts the shortcut uses
       (prerequisite_check).  Then verify each prerequisite is
       introduced in Stream 1.  If ANY prerequisite is missing from
       Stream 1, set prerequisite_satisfied_in_ncert = false and
       move the shortcut to out_of_syllabus_warnings.

    2. NCERT-GROUNDED: Every bridge insight must flow directly
       from a concept in Stream 1.  Do not link Stream 1 to a
       Stream 2 shortcut by superficial word overlap (e.g. both
       mention the word "matrix").  The cognitive link must be
       about the actual math, not shared vocabulary.

    3. NO HALLUCINATED CONCEPTS: If Stream 1 introduces only the
       definition of a matrix and basic notation, the only honest
       bridges are things like: "notice how the data layout in the
       table generalises to m rows and n columns", or "observe
       that the elements of a matrix are addressable by (i, j)
       which is a useful indexing convention for later
       operations".  Do not pretend the student already knows
       matrix multiplication, determinants, or inverses.

    4. SMALL BRIDGES ARE FINE: 0..2 bridges per chunk is normal.
       Emit 0 bridges when the chunk is purely foundational.

    5. PERFECT LaTeX: All equations must use $...$ (inline) or
       $$...$$ (display).  Use \\begin{{bmatrix}}...\\end{{bmatrix}}
       for matrices.

    ============================================================
    OUTPUT
    ============================================================
    Return strictly a JSON object matching the
    BridgedChunkPayload schema.  The schema is already enforced
    by the SDK; just make sure each bridge_insight has
    prerequisite_check and prerequisite_satisfied_in_ncert filled
    in correctly.  Empty bridge_insights is a valid result.
    """

    # Model Inference via Inference Gateway (automatic logging + retries)
    try:
        raw_text, _model_used = call_gemini(
            "command_4_bridge",
            MODEL_NAME,
            prompt,
            temperature=0.2,
            response_mime_type="application/json",
            response_schema=BridgedChunkPayload,
            max_retries=5,
        )
    except RuntimeError as e:
        print(f"[FATAL FAILURE] Bridge compilation failed after retries: {e}")
        sys.exit(1)

    # Clean markdown if present
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        if lines[0].startswith("```json") or lines[0].startswith("```"):
            raw_text = "\n".join(lines[1:-1])

    try:
        bridged_json = json.loads(raw_text.strip())

        # ============================================================
        # POST-PROCESSING: enforce prerequisite-satisfaction gate
        # ============================================================
        insights = bridged_json.get("bridge_insights", []) or []
        warnings = list(bridged_json.get("out_of_syllabus_warnings", []) or [])

        kept_insights = []
        demoted_count = 0
        for ins in insights:
            satisfied = bool(ins.get("prerequisite_satisfied_in_ncert", False))
            if satisfied:
                kept_insights.append(ins)
            else:
                demoted_count += 1
                title = (ins.get("concept_anchor") or "Unknown concept").strip()
                reason = (ins.get("prerequisite_check") or "prerequisites not in NCERT chunk").strip()
                warnings.append(
                    f"Demoted (prereq not in NCERT): '{title}' — {reason}"
                )
                print(f"[BRIDGE GATE] Demoted insight '{title}': {reason}")

        bridged_json["bridge_insights"] = kept_insights
        bridged_json["out_of_syllabus_warnings"] = warnings

        if demoted_count:
            print(f"[BRIDGE GATE] {demoted_count} insight(s) moved to out_of_syllabus_warnings.")

        OUTPUT_BRIDGE_PATH = paths.chunk_paths()["bridge"]
        with open(OUTPUT_BRIDGE_PATH, "w", encoding="utf-8") as f:
            json.dump(bridged_json, f, indent=4)
        print(f"[SUCCESS] Command 4 executed. Kept {len(kept_insights)} valid insight(s); {len(warnings)} warning(s).")
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed parsing bridged JSON schema: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Failed writing bridge cache payload: {e}")
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HY-TUTOR Command 4 Competitive Bridge")
    parser.add_argument("chapter_id", nargs="?", help="Target Chapter ID")
    parser.add_argument("chunk_index", nargs="?", help="Chunk index (integer)")
    parser.add_argument("--subject", type=str, default=None,
                        help="Active subject (e.g., mathematics). If omitted, "
                             "resolved from the environment / pointer.")
    args = parser.parse_args()
    if not args.chapter_id or args.chunk_index is None:
        print("Usage: python command_4_bridge.py <Chapter_ID> <Chunk_Index>")
        sys.exit(1)
    execute_command_4_pipeline(args.chapter_id, int(args.chunk_index), subject=args.subject)
