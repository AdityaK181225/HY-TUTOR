"""
HY-TUTOR: LEVEL 4 REFERENCE OPTIMIZER (command_3_optimizer.py)
Target Hardware: Asus TUF F15 (RTX 2050 4GB VRAM, 8GB System RAM)
Model Engines: 
  - Phase 1 (Extraction): Gemma 4 26B A4B IT (Fast, No Thinking)
  - Phase 2 (Consolidation): Gemma 4 26B A4B IT (High Thinking)
  - Phase 3 (Vectorization): Gemini Embedding 2
Optimized with large 5000-word sliding windows to maximize throughput.
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

# --- PHASE 2 SCHEMA: Structured Layout ---
class OptimizedReferenceElement(BaseModel):
    shortcut_type: str = Field(..., description="Strictly one of: 'SHORTCUT_METHOD', 'EDGE_CASE_PROOF', 'COMPETITIVE_VARIABLE_CORRELATION'")
    title: str = Field(..., description="A brief title of the competitive shortcut or rule.")
    advanced_derivation_latex: str = Field(..., description="Pristine LaTeX expression of the formula or derivation step using standard math formatting ($ or $$).")
    conceptual_bridge_insight: str = Field(..., description="A brief 1-2 sentence explanation of how this bridges or bypasses NCERT core mechanics.")
    element_embedding: Optional[List[float]] = Field(default=None, description="High-precision semantic vector from Gemini Embedding 2.")

class ReferenceMinedChunk(BaseModel):
    active_chapter_id: str
    chunk_index: int
    milestone_alignment: str
    advanced_elements: List[OptimizedReferenceElement]

# --- PHASE 1 SCHEMA: In-Depth Text Retrieval ---
class VerbatimSegmentExtraction(BaseModel):
    contains_relevant_advanced_content: bool = Field(..., description="True if this segment contains concepts extending or optimizing the active milestone.")
    verbatim_mined_markdown: str = Field(..., description="Extracted paragraphs, formula lines, derivations, and step-by-step proofs. Copy them in complete, unsummarized, verbatim depth.")

def load_ncert_chunk_milestone_and_text(active_chunk_dir: Path) -> tuple[str, str, str]:
    """Safely extracts active milestone context, subject, and the verbatim core text mined from NCERT."""
    ncert_path = active_chunk_dir / "NCERT_chunk.json"
    if not ncert_path.exists():
        print(f"[CRITICAL ERROR] Missing Upstream Dependency: NCERT chunk data not found at {ncert_path}")
        print("[HALT] Run command_2_miner.py before executing the Reference Optimizer.")
        sys.exit(1)

    try:
        with open(ncert_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            subject = data.get("subject", "mathematics").lower()
            milestone = data.get("milestone_alignment", "UNKNOWN_MILESTONE")
            
            # Reconstruct the NCERT standard baseline context for semantic mapping
            ncert_text_dump = ""
            elements = data.get("extracted_elements", [])
            for el in elements:
                if el.get("element_type") == "VERBATIM_THEORY":
                    ncert_text_dump += f"\n- {el.get('content')}"
            
            return milestone, subject, ncert_text_dump
    except Exception as e:
        print(f"[CRITICAL ERROR] Failed parsing upstream NCERT miner output: {e}")
        sys.exit(1)

def locate_and_read_reference_text(reference_dir: Path, subject: str, chapter_id: str) -> str:
    """Reads high-tier reference material (Cengage/Arihant) with domain-isolated scanning."""
    possible_targets = [
        reference_dir / subject.lower() / f"{chapter_id}.md",
        reference_dir / subject.lower() / f"{chapter_id}.txt",
        reference_dir / subject.capitalize() / f"{chapter_id}.md",
        reference_dir / subject.capitalize() / f"{chapter_id}.txt",
        reference_dir / f"{chapter_id}.md",
        reference_dir / f"{chapter_id}.txt"
    ]

    selected_path: Optional[Path] = None
    for path in possible_targets:
        if path.exists():
            selected_path = path
            break

    if not selected_path:
        print(f"[WARNING] Advanced Reference Source missing for {chapter_id} inside {reference_dir}")
        print(f"Scanned Paths checked: {[str(p) for p in possible_targets]}")
        print("[PROCESS] Proceeding with fallback mode (No advanced reference overrides detected).")
        return ""

    print(f"[SUCCESS] Located Advanced Reference material at: {selected_path}")
    with open(selected_path, "r", encoding="utf-8") as f:
        return f.read().strip()

def split_text_into_semantic_segments(text: str, max_words: int = 5000) -> List[str]:
    """Splits raw book text into larger logical segments matching paragraph limits to maximize window efficiency."""
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

def execute_command_3_pipeline(chapter_id: str, chunk_index: int, subject: Optional[str] = None):
    from utils.paths import SubjectPaths, resolve_subject

    # Resolve subject: priority = explicit arg > env/pointer > legacy.
    # As a final fallback we use the subject embedded inside the
    # NCERT chunk (written by C2), which preserves the old behaviour
    # where C3 discovered the subject from upstream.
    resolved: Optional[str] = (subject or "").strip().lower() or None
    if not resolved:
        try:
            resolved = resolve_subject()
        except ValueError:
            resolved = None  # fall through to NCERT chunk lookup

    print(f"\n[INITIALIZING] Command 3 Reference Optimizer for {chapter_id} | Chunk: {chunk_index}")

    REFERENCE_DIR = Path("data_library/raw_sources/reference_manuals")

    # We need to know the per-subject chunk dir. If the subject isn't
    # resolved yet, we'll read the NCERT chunk from any subject dir
    # we can find, then lock onto that subject. This keeps C3 usable
    # in legacy mode (no --subject, no pointer set).
    paths = None
    if resolved:
        paths = SubjectPaths.for_subject(resolved)
        paths.chunk_dir.mkdir(parents=True, exist_ok=True)
        active_chunk_dir = paths.chunk_dir
    else:
        # Fall back to the legacy flat dir just to discover the subject.
        from utils.paths import DATA_LIBRARY
        active_chunk_dir = DATA_LIBRARY / "active_workspace" / "active_chunk"

    # 1. Load Upstream NCERT Verification Anchors
    active_milestone, subject, ncert_baseline = load_ncert_chunk_milestone_and_text(active_chunk_dir)
    print(f"[UPSTREAM SYNC] Subject: '{subject}' | Concept Milestone: '{active_milestone}'")

    # Lock onto the discovered subject (which may differ from the
    # caller's arg). This is the same behaviour as before for legacy
    # invocations, and the right behaviour for the wired-up pipeline.
    subject_norm = subject.strip().lower()
    if paths is None or paths.subject != subject_norm:
        paths = SubjectPaths.for_subject(subject_norm)
        paths.chunk_dir.mkdir(parents=True, exist_ok=True)
        active_chunk_dir = paths.chunk_dir
    print(f"[PINNED] Per-subject workspace: {paths.root}")

    # 2. Extract Raw Reference Book Data
    raw_ref_text = locate_and_read_reference_text(REFERENCE_DIR, subject, chapter_id)

    # Early escape if no high-level reference manual is found
    if not raw_ref_text:
        print("[PROCESS] Initializing empty reference container schema.")
        fallback_payload = ReferenceMinedChunk(
            active_chapter_id=chapter_id,
            chunk_index=chunk_index,
            milestone_alignment=active_milestone,
            advanced_elements=[]
        )
        output_path = paths.chunk_paths()["reference"]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(fallback_payload.model_dump(), f, indent=4)
        print(f"[SUCCESS] Reference Optimizer completed (Fallback Mode). Saved to: {output_path}")
        return

    # 3. Partition Raw Reference Manual into large 5000-word logical blocks to reduce loop iterations
    ref_segments = split_text_into_semantic_segments(raw_ref_text, max_words=5000)
    print(f"[TEXT CHUNKER] Document divided into {len(ref_segments)} high-capacity segments to minimize API calls.")

    # 4. Load environment and model configuration
    load_dotenv(dotenv_path=Path("config/.env"))
    if not os.getenv("GEMINI_API_KEY"):
        print("[FATAL ERROR] GEMINI_API_KEY not found in config/.env")
        sys.exit(1)
    
    # Model Configurations (Split Processing Sequence)
    PHASE1_MODEL_NAME = os.getenv("COMMAND_3_MODEL", "gemma-4-26b-a4b-it") # SWAPPED to Gemma for Phase 1
    PHASE2_CONSOLIDATION_MODEL = os.getenv("COMMAND_3_CONSOLIDATION_MODEL", "gemma-4-26b-a4b-it")
    EMBEDDING_MODEL = "gemini-embedding-2"

    print(f"[ENGINES LINKED] Phase 1 Engine: {PHASE1_MODEL_NAME} | Phase 2 Engine: {PHASE2_CONSOLIDATION_MODEL}")

    # =========================================================================
    # PHASE 1: SLIDING-WINDOW VERBATIM EXTRACTION LOOP (Accumulate Raw Text)
    # =========================================================================
    accumulated_advanced_markdown = ""

    for idx, segment in enumerate(ref_segments):
        print(f"[PIPELINE LOOP] Mining Reference Segment {idx + 1}/{len(ref_segments)}...")
        
        prompt_phase1 = f"""
        You are the Reference Optimizer (Phase 1) for the HY-TUTOR local system.
        Your task is to review this segment of an advanced reference book and extract any advanced competitive exam shortcuts, math optimization rules, unique properties, or alternate derivations.

        === CONCEPTUAL ALIGNMENT ANCHOR (NCERT CORE LEVEL) ===
        Target Milestone: {active_milestone}
        Verbatim Baseline Content:
        {ncert_baseline}

        === CURRENT REFERENCE BOOK PORTION ===
        {segment}

        STRICT EXTRACTION LAWS:
        1. CROSS-REFERENCE SYNC: Evaluate the Reference Book segment against the NCERT Core Anchor. Identify if this portion is a direct extension, a specialized competitive case, or an optimization of the NCERT concept (even if terminology or titles differ).
        2. EXHAUSTIVE VERBATIM EXTRACTION (CRITICAL): Do NOT summarize, paraphrase, or compress. Extract the complete explanations, step-by-step mathematical proofs, derivation steps, and formulas exactly as they are written, word-for-word. We need 100% of the mathematical depth.
        3. STRICT MILITARY RELEVANCE: If a formula, shortcut, or topic in this segment does NOT directly relate to or extend the active milestone ('{active_milestone}'), set contains_relevant_advanced_content to false and leave verbatim_mined_markdown blank.
        4. PERFECT LATEX format: Every equation, variable, or proof sequence must be wrapped in strict LaTeX format ($ for inline, $$ for display).
        """

        # Optimized Phase 1: Fast scan using Gemma 4 26B (Disabled High Thinking)
        # Inference via Gateway - automatic logging + retries
        try:
            raw_text, _model_used = call_gemini(
                "command_3_optimizer",
                PHASE1_MODEL_NAME,
                prompt_phase1,
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=VerbatimSegmentExtraction,
                max_retries=5,
            )
        except RuntimeError as e:
            print(f"[FATAL ERROR] Command 3 Phase 1 failed on segment {idx + 1} after retries: {e}")
            sys.exit(1)

        # Clean markdown if present
        raw_text = (raw_text or "").strip()
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            if lines[0].startswith("```json") or lines[0].startswith("```"):
                raw_text = "\n".join(lines[1:-1])

        try:
            segment_data = json.loads(raw_text.strip())
            if segment_data.get("contains_relevant_advanced_content") and segment_data.get("verbatim_mined_markdown"):
                mined_md = segment_data.get("verbatim_mined_markdown").strip()
                accumulated_advanced_markdown += f"\n\n<!-- Segment {idx + 1} Mined -->\n" + mined_md
                print(f"[PHASE 1 SUCCESS] Mined {len(mined_md.split())} words of in-depth advanced material.")
            else:
                print(f"[PHASE 1 SKIP] Segment {idx + 1} contained no directly relevant extensions.")
        except json.JSONDecodeError as parse_err:
            print(f"[WARNING] Failed to parse Phase 1 output from segment {idx + 1}, skipping chunk: {parse_err}")

    # =========================================================================
    # PHASE 2: MASTER CONSOLIDATION PASS (Compile Raw Pool into Structured JSON)
    # =========================================================================
    print(f"\n[PHASE 2] Initiating Master Consolidation Pass...")
    total_accumulated_words = len(accumulated_advanced_markdown.split())
    print(f"[VOLUME REPORT] Consolidated Raw Competitive Pool contains {total_accumulated_words} words.")

    if total_accumulated_words == 0:
        print("[PROCESS] Consolidated raw pool is empty. Writing empty reference JSON schema.")
        empty_payload = ReferenceMinedChunk(
            active_chapter_id=chapter_id,
            chunk_index=chunk_index,
            milestone_alignment=active_milestone,
            advanced_elements=[]
        )
        output_path = paths.chunk_paths()["reference"]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(empty_payload.model_dump(), f, indent=4)
        print(f"[SUCCESS] Reference Optimizer completed (Fallback Mode). Saved to: {output_path}")
        return

    prompt_phase2 = f"""
    You are the Lead Master Compiler (Phase 2 Consolidation) for the HY-TUTOR local system.
    Your task is to take the entire raw compiled pool of mined competitive textbook material and structure it cleanly into the final ReferenceMinedChunk Pydantic schema.

    === CONCEPTUAL ALIGNMENT ANCHOR ===
    Active Milestone: {active_milestone}

    === CONSOLIDATED RAW ADVANCED MATERIAL POOL ===
    {accumulated_advanced_markdown}

    STRICT CONSOLIDATION LAWS:
    1. ZERO-LOSS COMPILATION: Do not be lazy. You must extract and preserve EVERY single competitive trick, shortcut, theorem, and formula derivation from the consolidated pool.
    2. STEP-BY-STEP LATEX RETENTION: Keep the full mathematical derivation step sequences in the advanced_derivation_latex attribute. Do not shorten or skip intermediate equation lines. Use proper LaTeX math environments ($...$ or $$...$$).
    3. DETAILED COGNITIVE BRIDGES: For every element, write a deep, 1-2 sentence explanation of how the shortcut optimizes or bridges standard NCERT base axioms.
    4. NO REDUNDANT BULLETS: If there are duplicates across mined segments, unify them into single comprehensive entries containing all mapped proofs.
    """

    # Phase 2: Run with High Thinking Reasoning using specialized gemma-4-26b-a4b-it
    # Inference via Gateway - automatic logging + retries
    try:
        raw_text, _model_used = call_gemini(
            "command_3_optimizer",
            PHASE2_CONSOLIDATION_MODEL,
            prompt_phase2,
            temperature=0.1,
            response_mime_type="application/json",
            response_schema=ReferenceMinedChunk,
            max_retries=5,
        )
    except RuntimeError as e:
        print(f"[FATAL ERROR] Command 3 Phase 2 Consolidation failed after retries: {e}")
        sys.exit(1)

    # Clean markdown if present
    raw_text = (raw_text or "").strip()
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        if lines[0].startswith("```json") or lines[0].startswith("```"):
            raw_text = "\n".join(lines[1:-1])

    try:
        optimized_json = json.loads(raw_text.strip())
        
        # Enforce exact chapter metadata injection
        optimized_json["active_chapter_id"] = chapter_id
        optimized_json["chunk_index"] = chunk_index
        optimized_json["milestone_alignment"] = active_milestone

        elements = optimized_json.get("advanced_elements", [])
        print(f"[CONSOLIDATION REPORT] Successfully parsed consolidated raw pool into {len(elements)} rich elements.")

        # =========================================================================
        # PHASE 3: VECTORIZATION (Generate Semantic Embeddings) - kept as direct call
        # Wrapped with manual record_inference() to ensure embedding usage is also logged.
        # =========================================================================
        if elements:
            print(f"[PROCESS] Vectorizing structured advanced elements using {EMBEDDING_MODEL}...")
            element_texts = [f"{el['title']} - {el['conceptual_bridge_insight']}" for el in elements]
            try:
                from google import genai
                from google.genai import types
                _embed_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
                _start = time.time()
                embed_response = _embed_client.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=element_texts,
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_DOCUMENT",
                        output_dimensionality=3072
                    )
                )
                record_inference(
                    command="command_3_optimizer",
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
                    optimized_json["advanced_elements"][i]["element_embedding"] = embedding.values
            except Exception as embed_err:
                print(f"[WARNING] Advanced element embedding generation failed. Proceeding without vectors: {embed_err}")

        # =========================================================================
        # PHASE 4: WRITE DATA TO WORKSPACE CACHE
        # =========================================================================
        OUTPUT_REF_PATH = paths.chunk_paths()["reference"]
        with open(OUTPUT_REF_PATH, "w", encoding="utf-8") as f:
            json.dump(optimized_json, f, indent=4)

        print(f"[SUCCESS] Command 3 executed successfully.")
        print(f"Staged finalized structured data payload to: -> {OUTPUT_REF_PATH}")
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed parsing consolidated JSON: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Failed writing payload state: {e}")
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HY-TUTOR Command 3 Reference Optimizer")
    parser.add_argument("chapter_id", nargs="?", help="Target Chapter ID")
    parser.add_argument("chunk_index", nargs="?", help="Chunk index (integer)")
    parser.add_argument("--subject", type=str, default=None,
                        help="Active subject (e.g., mathematics). If omitted, "
                             "resolved from the environment / pointer.")
    args = parser.parse_args()
    if not args.chapter_id or args.chunk_index is None:
        print("Usage: python command_3_optimizer.py <Chapter_ID> <Chunk_Index>")
        sys.exit(1)
    execute_command_3_pipeline(args.chapter_id, int(args.chunk_index), subject=args.subject)
