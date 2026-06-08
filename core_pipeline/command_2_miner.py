"""
HY-TUTOR: LEVEL 4 CORE ASSET MINER (command_2_miner.py)
Target Hardware: Asus TUF F15 (RTX 2050 4GB VRAM, 8GB System RAM)
Optimized with Gemini 3.1 Flash-Lite (High Thinking) & Resilient Exponential Retry.
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
    log_init, log_process, log_success, log_warning, log_error, log_debug
)

class MinedElement(BaseModel):
    element_type: str = Field(..., description="Strictly one of: 'VERBATIM_THEORY', 'LATEX_FORMULA', or 'VISUAL_GROUNDING_DESCRIPTION'")
    content: str = Field(..., description="The exact verbatim text, pure LaTeX equation, or descriptive text.")
    context_anchor: str = Field(..., description="A short 3-5 word label identifying the concept.")

class NCERTMinedChunk(BaseModel):
    active_chapter_id: str
    chunk_index: int
    milestone_alignment: str
    deep_thinking_extraction_log: str = Field(..., description="Step 1: Count the total number of paragraphs and formulas in the raw chunk text. Step 2: Explicitly state your plan to extract every single one verbatim without skipping any.")
    cleaned_text: str = Field(..., description="The FULL verbatim textbook text for this chunk, copied end-to-end with original paragraph breaks (\\n\\n) and section headers preserved. This is the 'blueprint-style' full context payload that downstream commands read first.")
    extracted_elements: List[MinedElement]

def load_chunk_text(blueprint_path: Path, target_chunk_index: int) -> dict:
    """Read a per-chunk blueprint file and return it.

    Phase 2 refactor: the blueprint is now stored as individual files
    under ``chapters/<chapter_id>/blueprint/chunk_NN.json``.  Each file is
    self-contained and already scoped to a single chunk, so no filtering
    is needed.

    Backward-compat: if the file still looks like a monolithic blueprint
    (has a ``"chunks"`` list), fall back to the old filter logic.
    """
    if not blueprint_path.exists():
        log_error("command_2_miner", f"Blueprint not found at {blueprint_path}")
        sys.exit(1)
    try:
        with open(blueprint_path, "r", encoding="utf-8") as f:
            blueprint_data = json.load(f)

        # Phase 2 per-chunk file: self-contained, no "chunks" wrapper
        if "chunk_index" in blueprint_data and "cleaned_text" in blueprint_data:
            return blueprint_data

        # Legacy monolithic blueprint: filter by chunk_index
        for chunk in blueprint_data.get("chunks", []):
            if chunk.get("chunk_index") == target_chunk_index:
                return chunk
    except Exception as e:
        log_error("command_2_miner", f"Failed parsing blueprint: {e}")
        sys.exit(1)
    log_error("command_2_miner", f"Chunk Index {target_chunk_index} not found")
    sys.exit(1)

def execute_command_2_pipeline(chapter_id: str, chunk_index: int, subject: Optional[str] = None):
    from utils.paths import SubjectPaths, resolve_subject

    # Resolve subject (priority: explicit arg > env > pointer > legacy)
    try:
        resolved = resolve_subject(subject)
    except ValueError as e:
        log_error("command_2_miner", f"{e} (run command_1_blueprint or set --subject)")
        sys.exit(1)

    log_init("command_2_miner", f"Execution for {chapter_id} | Chunk: {chunk_index} | Subject: {resolved}")

    paths = SubjectPaths.for_subject(resolved)
    paths.chunk_dir.mkdir(parents=True, exist_ok=True)

    # Phase 2: prefer the per-chunk blueprint file in the chapter folder
    _per_chunk_bp = paths.blueprint_chunk_path(chapter_id, chunk_index)
    _legacy_bp = paths.blueprint_path(chapter_id)
    bp_file = _per_chunk_bp if _per_chunk_bp.exists() else _legacy_bp
    chunk_data = load_chunk_text(bp_file, chunk_index)
    raw_chunk_text = chunk_data.get("cleaned_text", "")
    milestone = chunk_data.get("milestone_alignment", "UNKNOWN_MILESTONE")

    if not raw_chunk_text:
        log_error("command_2_miner", "Cleaned text payload is empty. Nothing to mine.")
        sys.exit(1)

    MODEL_NAME = get_default_model("command_2_miner")

    prompt = f"""
    You are the Core Asset Miner (Command 2) for the HY-TUTOR local system. Your task is to perform EXHAUSTIVE, 100% verbatim text mining on the provided textbook chunk.
    Target Chapter: {chapter_id}
    Active Milestone: {milestone}

    RAW CHUNK TEXT:
    {raw_chunk_text}

    MANDATORY RULES:
    0. BLUEPRINT-STYLE CLEANED TEXT (NEW — TOP-LEVEL 'cleaned_text' FIELD): Populate the top-level 'cleaned_text' field with the ENTIRE raw chunk text above, copied verbatim end-to-end. Preserve the original paragraph structure by inserting '\\n\\n' (double newlines) between paragraphs and '\\n' (single newlines) for line breaks inside the same paragraph. Preserve section headers, sub-headers, and bullet/numbered lists as they appear in the source. This field is the canonical full-context payload that downstream commands read first — it MUST be 100% of the source text, character-for-character, with no summarization, no paraphrasing, and no omissions.
    1. SINGLE CONTINUOUS VERBATIM BLOCK (PRIMARY): Output exactly ONE large VERBATIM_THEORY element whose content is the entire raw chunk text above, copied verbatim, with the same '\\n\\n' paragraph breaks as the cleaned_text field. Do NOT split the prose around formulas. Do NOT create multiple small VERBATIM_THEORY snippets. The content of this element MUST be identical to the 'cleaned_text' field.
    2. SUPPLEMENTARY FORMULA EXTRACTION (SECONDARY): Additionally extract any standalone math/equation rows that the textbook presents as discrete display lines as separate LATEX_FORMULA elements. These are SUPPLEMENTARY to the verbatim text, not replacements for chunks of it.
    3. LaTeX Normalization: Convert any standalone formulas or inline variables into strict LaTeX notation. Use $...$ for inline and $$...$$ for display equations.
    4. EXTRACTION LOG: In deep_thinking_extraction_log, state: (a) the total word count of the raw text, (b) the number of display formulas extracted separately, (c) confirmation that the single VERBATIM_THEORY element covers the full text, (d) confirmation that 'cleaned_text' and the VERBATIM_THEORY element are byte-for-byte identical.
    5. SELF-CHECK: Before returning, confirm: (i) the 'cleaned_text' field reconstructs the raw chunk text end-to-end with zero word loss, (ii) the VERBATIM_THEORY element reconstructs the raw chunk text end-to-end with zero word loss, (iii) the two are identical.
    """

    # Model Inference via Inference Gateway (automatic logging + retries)
    try:
        raw_text, _model_used = call_gemini(
            "command_2_miner",
            MODEL_NAME,
            prompt,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=NCERTMinedChunk,
            max_retries=5,
        )
    except RuntimeError as e:
        log_error("command_2_miner", f"NCERT mining failed after retries: {e}")
        sys.exit(1)

    # Clean markdown if present
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        if lines[0].startswith("```json") or lines[0].startswith("```"):
            raw_text = "\n".join(lines[1:-1])

    try:
        mined_json = json.loads(raw_text.strip())
        chunk_paths = paths.chunk_paths()
        output_path = chunk_paths["ncert"]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(mined_json, f, indent=4)
        log_success("command_2_miner", f"Extracted {len(mined_json.get('extracted_elements', []))} exhaustive elements")
        log_process("command_2_miner", f"[WRITE] NCERT_chunk.json -> {output_path}")

        # --- Phase 2: Copy to per-chapter archive folder -------------------
        import shutil
        _ncert_archive = paths.ncert_chunk_path(chapter_id, chunk_index)
        _ncert_archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output_path, _ncert_archive)
        log_process("command_2_miner", f"[ARCHIVE] NCERT -> {_ncert_archive}")
    except json.JSONDecodeError as e:
        log_error("command_2_miner", f"Failed parsing NCERT payload: {e}")
        sys.exit(1)
    except Exception as e:
        log_error("command_2_miner", f"Failed writing NCERT payload: {e}")
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HY-TUTOR Command 2 NCERT Miner")
    parser.add_argument("chapter_id", nargs="?", help="Target Chapter ID (e.g., CH_12_03)")
    parser.add_argument("chunk_index", nargs="?", help="Chunk index (integer)")
    parser.add_argument("--subject", type=str, default=None,
                        help="Active subject (e.g., mathematics). If omitted, "
                             "resolved from the environment / pointer.")
    args = parser.parse_args()
    if not args.chapter_id or args.chunk_index is None:
        # Preserve the original bare-arg behaviour: silent exit 1.
        sys.exit(1)
    execute_command_2_pipeline(args.chapter_id, int(args.chunk_index), subject=args.subject)
