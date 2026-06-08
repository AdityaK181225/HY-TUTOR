"""
HY-TUTOR: LEVEL 4 UNIFIED LESSON FORGE (command_5_forge.py)
Target Hardware: Asus TUF F15 (RTX 2050 4GB VRAM, 8GB System RAM)
Model Engine: Gemma 4 31B IT (High Thinking)
Synthesizes NCERT verbatim core data, advanced Reference book shortcuts, and Exemplar practice problems.
Bypasses JSON wrappers to safely stream massive LaTeX documents directly to Markdown.

June 2026 fixes:
  - Passes max_output_tokens=16384 to avoid mid-document truncation.
  - Adds a completion-check + continuation loop so the document
    always ends cleanly with the Practice Exercises section.
  - Renders the empty-bridge case as the user-facing italic note
    "No competitive shortcuts apply at this introductory milestone".
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from utils.inference import call_gemini
from utils.genai_client import get_default_model

# Sentinel used to detect whether the forge output actually
# completed the last required section ("## Practice Exercises").
PRACTICE_EXERCISES_HEADER = "## Practice Exercises"

# How many continuation passes to attempt when the previous output
# is truncated before the final section.
MAX_CONTINUATIONS = 2

# When there are no competitive bridges, the forge emits this
# italic note in place of the Advanced Insights section.
EMPTY_BRIDGE_NOTE = (
    "*No competitive shortcuts apply at this introductory "
    "milestone — focus on the baseline theory above.*"
)

def load_upstream_dependencies(active_chunk_dir: Path) -> tuple[dict, dict, dict, dict]:
    """Safely extracts NCERT core, Reference shortcuts, Competitive Bridge, and Practice Problems chunks."""
    ncert_path = active_chunk_dir / "NCERT_chunk.json"
    ref_path = active_chunk_dir / "Reference_chunk.json"
    bridge_path = active_chunk_dir / "Bridge_chunk.json"
    problems_path = active_chunk_dir / "Active_Chunk_Problems.json"

    if not ncert_path.exists() or not ref_path.exists() or not bridge_path.exists() or not problems_path.exists():
        print(f"[CRITICAL ERROR] Upstream Dependencies missing in {active_chunk_dir}")
        print(f"NCERT cached: {ncert_path.exists()} | Reference cached: {ref_path.exists()} | Bridge cached: {bridge_path.exists()} | Problems cached: {problems_path.exists()}")
        sys.exit(1)

    try:
        with open(ncert_path, "r", encoding="utf-8") as f:
            ncert_data = json.load(f)
        with open(ref_path, "r", encoding="utf-8") as f:
            ref_data = json.load(f)
        with open(bridge_path, "r", encoding="utf-8") as f:
            bridge_data = json.load(f)
        with open(problems_path, "r", encoding="utf-8") as f:
            problems_data = json.load(f)
        return ncert_data, ref_data, bridge_data, problems_data
    except Exception as e:
        print(f"[CRITICAL ERROR] Failed parsing upstream JSON dependency files: {e}")
        sys.exit(1)

def build_synthesis_prompt(
    chapter_id: str,
    active_milestone: str,
    ncert_data: dict,
    ref_data: dict,
    bridge_data: dict,
    problems_data: dict,
    has_bridges: bool,
) -> str:
    """Construct the unified lesson synthesis prompt.

    When the bridge has zero insights, an extra instruction tells the
    model to insert the EMPTY_BRIDGE_NOTE in the Advanced Insights
    section instead of fabricating content.
    """
    empty_bridge_instruction = ""
    if not has_bridges:
        empty_bridge_instruction = f"""
    ADVANCED INSIGHTS — SPECIAL EMPTY-BRIDGE INSTRUCTION:
    The Bridge step produced zero bridge insights for this milestone
    because the chunk is purely foundational and admits no
    competitive shortcut without later concepts.  In the Advanced
    Insights section, do NOT fabricate any shortcuts, derivations, or
    matrix operations.  Instead, render EXACTLY this single italic
    line and nothing else in that section:

    {EMPTY_BRIDGE_NOTE}
"""

    return f"""
    You are the Unified Lesson Forge (Command 5) for the HY-TUTOR system.
    Your mission is to compile standard concepts, advanced optimizations, cognitive bridge explanations, and active practice problems into a beautifully structured Markdown textbook page.

    Target Chapter: {chapter_id}
    Active Milestone: {active_milestone}

    === STREAM 1: NCERT STANDARD BASELINE DATA ===
    {json.dumps(ncert_data, indent=2)}

    === STREAM 2: ADVANCED REFERENCE SHORTCUTS ===
    {json.dumps(ref_data, indent=2)}

    === STREAM 3: COMPETITIVE BRIDGES & WARNINGS ===
    {json.dumps(bridge_data, indent=2)}

    === STREAM 4: EXEMPLARY PRACTICE PROBLEMS ===
    {json.dumps(problems_data, indent=2)}

    STRICT CONSOLIDATION & COGNITIVE INTERLEAVING INSTRUCTIONS:
    1. STRICT NO-ALTERATION RULE (CRITICAL): Do NOT change, shorten, modify, summarize, or paraphrase any of the extracted content from Stream 1 (NCERT Core theory, definitions, formulas), Stream 2 (Reference Book shortcuts, advanced derivation steps), or Stream 4 (Practice Problems). You must copy and retain their details verbatim and in their full conceptual depth.
    2. THE GLUE MANDATE: You must use the 'bridge_insights' from Stream 3 (specifically the 'bridge_explanation', 'advanced_application', and 'latex_formula_bridge') purely as the "explanation glue". Interleave these explanations dynamically *between* standard NCERT entries and their corresponding advanced shortcuts to explain how the student transitions mathematically from standard board-level concepts to rapid competitive shortcuts. Do not invent outside explanations.
    3. OUT-OF-SYLLABUS WARNING PLACEMENT: If any element or shortcut relates to the 'out_of_syllabus_warnings' array inside Stream 3, place an explicit bold banner right above it:
       `⚠️ [WARNING: Out of Syllabus - Competitive Extension Only]`
    4. EXEMPLAR PRACTICE PROBLEMS SECTION (AT THE END): Create a dedicated section at the very bottom named '## Practice Exercises'. In this section, you must list all questions from Stream 4 ('problems') exactly as they are defined, showing their ID, difficulty level, and problem text (including LaTeX). Do NOT include their step-by-step solutions or answers here, because the solutions to these are meant to be solved by the student or discussed interactively with the Socratic live tutor.
    5. PRECISE LATEX: Output all mathematical equations, variables, and proofs using clean, standard LaTeX wrapping ($ for inline, $$ for block display).
    6. ALWAYS END WITH PRACTICE EXERCISES: The document MUST end with the '## Practice Exercises' section. Do not stop early. Do not truncate mid-section. The last visible line of your output should be the last question in Stream 4.
{empty_bridge_instruction}
    THE STRUCTURE HIERARCHY TEMPLATE:
    Return your output strictly as a PURE MARKDOWN DOCUMENT matching this structure exactly (Do not wrap it in JSON):

    # {active_milestone}

    ## Baseline Theory (NCERT Baseline Alignment)
    [Full-length, untouched verbatim NCERT definitions, theorems, and core elements from Stream 1]

    ## Advanced Insights (Competitive Bridges & Shortcuts)
    [Interleaved conceptual progressions: Verbatim NCERT concept -> Bridge Explanation Glue (Stream 3) -> Verbatim Advanced Shortcut (Stream 2).  If the bridge pool is empty, render the empty-bridge italic note only.]

    ## Key Formulas (Comprehensive LaTeX Summary)
    [Consolidated LaTeX formulas from both Stream 1 and Stream 2, mapped clearly]

    ## Solved Bridge Examples (Step-by-Step with Clear Explanations)
    [1-2 practical mathematics/science problems worked out with side-by-side solutions: one showing the traditional school board method, and the other showing the rapid competitive shortcut method.  If no shortcut example is appropriate for this milestone, you may still show a worked example using the board method only.]

    ## Practice Exercises
    [List all questions from Stream 4 showing only their ID, Tier, and Question Text verbatim. Do NOT show solutions.]
    """


def _clean_markdown(text: str) -> str:
    """Strip leading/trailing markdown code-fence artifacts that LLMs sometimes emit."""
    text = (text or "").strip()
    if text.startswith("```markdown"):
        text = text[len("```markdown"):].lstrip()
    elif text.startswith("```"):
        text = text[3:].lstrip()
    if text.endswith("```"):
        text = text[:-3].rstrip()
    return text


def _looks_complete(md: str) -> bool:
    """Heuristic: did the previous forge pass finish all required sections?

    We treat the document as complete if it contains the final
    "## Practice Exercises" header.  This is good enough for our
    template: the very last section is always Practice Exercises.
    """
    if not md:
        return False
    return PRACTICE_EXERCISES_HEADER in md


def execute_command_5_pipeline(chapter_id: str, chunk_index: int, subject: Optional[str] = None):
    from utils.paths import SubjectPaths, resolve_subject

    try:
        resolved = resolve_subject(subject)
    except ValueError as e:
        print(f"[FATAL ERROR] {e} (set --subject or HY_TUTOR_SUBJECT)")
        sys.exit(1)

    print(f"\n[INITIALIZING] Command 5 Unified Lesson Forge for {chapter_id} | Chunk: {chunk_index} | Subject: {resolved}")

    paths = SubjectPaths.for_subject(resolved)
    paths.chunk_dir.mkdir(parents=True, exist_ok=True)

    # Ingest all four upstream dependency files
    ncert_data, ref_data, bridge_data, problems_data = load_upstream_dependencies(paths.chunk_dir)
    active_milestone = ncert_data.get("milestone_alignment", "UNKNOWN_MILESTONE")
    print(f"[PINNED] Per-subject workspace: {paths.root}")

    MODEL_NAME = get_default_model("command_5_forge")

    bridge_insights = (bridge_data or {}).get("bridge_insights", []) or []
    has_bridges = len(bridge_insights) > 0

    prompt = build_synthesis_prompt(
        chapter_id=chapter_id,
        active_milestone=active_milestone,
        ncert_data=ncert_data,
        ref_data=ref_data,
        bridge_data=bridge_data,
        problems_data=problems_data,
        has_bridges=has_bridges,
    )

    print(f"[PROCESS] Dispatching quadruple-stream synthesis load to {MODEL_NAME} (max_output_tokens=16384)...")

    # Model Inference via Inference Gateway (automatic logging + retries)
    # Note: Forge uses text/plain (pure Markdown) — no JSON schema, no JSON parsing.
    final_markdown = ""
    try:
        final_markdown, _model_used = call_gemini(
            "command_5_forge",
            MODEL_NAME,
            prompt,
            temperature=0.2,
            response_mime_type="text/plain",  # <-- BYPASSING JSON PARSING
            max_output_tokens=16384,
            max_retries=5,
        )
        final_markdown = _clean_markdown(final_markdown)
    except RuntimeError as e:
        print(f"[FATAL FAILURE] Unified Lesson Forge failed after retries: {e}")
        sys.exit(1)

    # ============================================================
    # COMPLETION-CHECK + CONTINUATION LOOP
    # ============================================================
    # The forge output can hit max_output_tokens mid-document,
    # especially when the lesson is long.  If the output does not
    # include the final "## Practice Exercises" header, ask the
    # model to continue from where it left off.  Repeat up to
    # MAX_CONTINUATIONS times.
    for attempt in range(1, MAX_CONTINUATIONS + 1):
        if _looks_complete(final_markdown):
            print(f"[FORGE] Document complete after {attempt} continuation pass(es).")
            break
        print(f"[FORGE] Document appears truncated (missing '{PRACTICE_EXERCISES_HEADER}'). "
              f"Asking for continuation (pass {attempt}/{MAX_CONTINUATIONS})...")
        tail = final_markdown[-400:] if final_markdown else ""
        continuation_prompt = (
            "Continue the unified lesson Markdown document from EXACTLY where you stopped. "
            "Do not repeat any content already produced. "
            "The document must end with the '## Practice Exercises' section listing every "
            "question from Stream 4 of the original prompt. "
            "Resume with the first heading or content that was missing. "
            f"\n\n--- LAST 400 CHARS OF THE EXISTING DOCUMENT ---\n{tail}\n"
            "--- CONTINUE BELOW ---\n"
        )
        try:
            cont_text, _ = call_gemini(
                "command_5_forge",
                MODEL_NAME,
                continuation_prompt,
                temperature=0.2,
                response_mime_type="text/plain",
                max_output_tokens=16384,
                max_retries=5,
            )
            cont_text = _clean_markdown(cont_text)
            # Splice: ensure exactly one blank line between the previous tail and the continuation.
            sep = "\n\n" if final_markdown and not final_markdown.endswith("\n\n") else ""
            final_markdown = (final_markdown or "") + sep + cont_text
        except RuntimeError as e:
            print(f"[FORGE] Continuation pass {attempt} failed: {e}")
            break

    if not _looks_complete(final_markdown):
        print(f"[FORGE WARNING] Document still incomplete after {MAX_CONTINUATIONS} continuations. "
              "Saving the partial document anyway.")

    # ============================================================
    # EMPTY-BRIDGE INJECTION (defensive)
    # ============================================================
    # If the bridge payload was empty, the model should already have
    # rendered the italic note.  But if the model hallucinated
    # content anyway (defensive), we can post-process: replace the
    # Advanced Insights section with the empty-bridge note.
    if not has_bridges:
        # Naively replace the entire "## Advanced Insights" section
        # up to the next "## " heading with the italic note.  This
        # is best-effort; if the heading isn't found, we just
        # leave the lesson as-is and trust the prompt instruction.
        marker = "## Advanced Insights"
        if marker in final_markdown:
            start = final_markdown.find(marker)
            # Find the next "## " heading after the marker
            tail_start = final_markdown.find("\n## ", start + len(marker))
            if tail_start == -1:
                tail_start = len(final_markdown)
            final_markdown = (
                final_markdown[:start]
                + marker + "\n\n" + EMPTY_BRIDGE_NOTE + "\n"
                + final_markdown[tail_start:]
            )
            print("[FORGE] Injected empty-bridge italic note into the lesson.")

    try:
        # Save the finalized consolidated textbook page directly to markdown
        OUTPUT_MD_PATH = paths.chunk_paths()["lesson"]
        with open(OUTPUT_MD_PATH, "w", encoding="utf-8") as f:
            f.write(final_markdown)
        print(f"[SUCCESS] Command 5 completed successfully. Synced textbook lesson to: -> {OUTPUT_MD_PATH}")

        # Phase 2.1: Index to per-subject vector DB (best-effort).
        try:
            from utils.vector_db import index_active_chunk as _iac
            _stats = _iac(paths, chapter_id, resolved, chunk_index)
            print(f"[VECTOR_DB] Index result for {chapter_id} chunk {chunk_index}: {_stats}")
        except Exception as _e:
            print(f"[VECTOR_DB] Indexing skipped (non-fatal): {_e}")
    except Exception as e:
        print(f"[ERROR] Failed saving Unified_Lesson.md: {e}")
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HY-TUTOR Command 5 Unified Lesson Forge")
    parser.add_argument("chapter_id", nargs="?", help="Target Chapter ID")
    parser.add_argument("chunk_index", nargs="?", help="Chunk index (integer)")
    parser.add_argument("--subject", type=str, default=None,
                        help="Active subject (e.g., mathematics). If omitted, "
                             "resolved from the environment / pointer.")
    args = parser.parse_args()
    if not args.chapter_id or args.chunk_index is None:
        print("Usage: python command_5_forge.py <Chapter_ID> <Chunk_Index>")
        sys.exit(1)
    execute_command_5_pipeline(args.chapter_id, int(args.chunk_index), subject=args.subject)
