"""
HY-TUTOR: LEVEL 4 SEMANTIC CHUNKING & BLUEPRINT ENGINE (command_1_blueprint.py)
Target Hardware: Asus TUF F15 (RTX 2050 4GB VRAM, 8GB System RAM)
Optimized with Gemini 3.1 Flash-Lite (High Thinking) & Gemini Embedding 2.
"""

import os
import sys
import json
import time
import re
import tempfile
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from utils.inference import call_gemini
from utils.genai_client import get_default_model
from utils.usage_tracker import record_inference


# ============================================================================
# ATOMIC JSON WRITE HELPER
# ============================================================================
# Prevents the classic "half-written file" failure mode: a crash, OOM kill,
# SIGKILL, or subprocess timeout while a 100+ KB JSON file is being flushed
# to disk can otherwise leave a corrupt or empty ``chapter_blueprint_*.json``
# in place, which downstream C2/C3/C4/C5 cannot parse. The temp+replace
# pattern means the destination file is only ever swapped in atomically, so
# either the previous good copy is intact or the new one is fully written.
def _atomic_write_json(target_path: Path, payload: dict) -> None:
    """Write ``payload`` as JSON to ``target_path`` atomically.

    The file is first written to a sibling temp file in the same directory
    (so the rename is a single inode swap, never a cross-filesystem copy),
    then ``os.replace()`` swaps it into place. If the write fails for any
    reason, the partial temp file is cleaned up and the original file
    (if any) is left untouched.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(target_path.parent),
        prefix=f".{target_path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_f:
            json.dump(payload, tmp_f, indent=4)
            tmp_f.flush()
            os.fsync(tmp_f.fileno())
        os.replace(tmp_path, str(target_path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ============================================================================
# SELF-HEAL: re-derive backup blueprint from the active workspace
# ============================================================================
def _active_workspace_has_valid_blueprint(active_path: Path, chapter_id: str) -> bool:
    """Return True iff ``active_path`` exists, parses as JSON, and
    contains a blueprint matching ``chapter_id`` with at least one
    chunk that has a non-empty ``cleaned_text`` field.
    """
    if not active_path.exists():
        return False
    try:
        with open(active_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False
    if data.get("active_chapter_id") != chapter_id:
        return False
    chunks = data.get("chunks") or []
    if not chunks:
        return False
    if not any((c.get("cleaned_text") or "").strip() for c in chunks):
        return False
    return True


def _self_heal_backup(paths, chapter_id: str) -> bool:
    """Three-stage idempotent guard for the blueprint command.

    Stage 1 — both files already valid:
        If the active workspace AND the backup both exist and the
        active workspace has valid blueprint content for this chapter,
        we have nothing to do. Returns the special sentinel
        ``"no_op"`` (a truthy string) so the caller logs the
        "already complete" path and skips the LLM entirely.

    Stage 2 — backup missing, workspace valid:
        If the active workspace is valid but the backup file is
        missing, re-derive the backup from the active workspace
        (atomic write). Returns True.

    Stage 3 — needs full pipeline:
        Otherwise return False so the caller falls through to the
        full LLM-driven path.
    """
    active_path = paths.active_workspace
    backup_path = paths.blueprint_path(chapter_id)
    workspace_valid = _active_workspace_has_valid_blueprint(active_path, chapter_id)
    if workspace_valid and backup_path.exists():
        return "no_op"
    if workspace_valid:
        try:
            with open(active_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            _atomic_write_json(backup_path, data)
        except Exception as e:
            print(f"[WARN] Self-heal backup write failed: {e}")
            return False
        return True
    return False

class ChapterChunk(BaseModel):
    chunk_index: int = Field(..., description="Sequential zero-indexed identifier for the operational chunk.")
    milestone_alignment: str = Field(..., description="The specific conceptual syllabus milestone this chunk covers.")
    cleaned_text: str = Field(..., description="CRITICAL: The ENTIRE verbatim pedagogical textbook text. DO NOT SUMMARIZE. Copy the full source text belonging to this chunk.")
    iat_priority: str = Field(..., description="Syllabus trend priority matrix weighting: 'HIGH', 'MEDIUM', or 'LOW'.")
    guardrail_status: str = Field(..., description="Set strictly to 'VALID' or '[WARNING: Out of Syllabus]'.")
    chunk_embedding: Optional[List[float]] = Field(default=None, description="High-precision semantic vector from Gemini Embedding 2.")

class ChapterBlueprint(BaseModel):
    active_chapter_id: str
    subject_name: str
    total_chunks_in_chapter: int
    deep_thinking_chunking_plan: str = Field(..., description="Analyze the raw source text block-by-block. Explain how you will divide it among the milestones without losing or summarizing a single sentence of the original text.")
    chunks: List[ChapterChunk]

def load_master_syllabus(syllabus_path: Path) -> dict:
    if not syllabus_path.exists():
        print(f"[CRITICAL ERROR] Dependency Missing: Master Syllabus not found at {syllabus_path}")
        sys.exit(1)
    try:
        with open(syllabus_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[CRITICAL ERROR] Corruption Detected in {syllabus_path}: {e}")
        sys.exit(1)

def locate_and_read_textbook(textbook_dir: Path, chapter_id: str) -> str:
    textbook_dir.mkdir(parents=True, exist_ok=True)
    md_target = textbook_dir / f"{chapter_id}.md"
    txt_target = textbook_dir / f"{chapter_id}.txt"
    selected_path = md_target if md_target.exists() else txt_target if txt_target.exists() else None
    
    if not selected_path:
        print(f"[CRITICAL ERROR] Ingestion Source Missing for {chapter_id} in {textbook_dir}")
        sys.exit(1)
        
    print(f"[PROCESS] Autonomous I/O Layer reading text file: {selected_path}")
    with open(selected_path, "r", encoding="utf-8") as f:
        return f.read().strip()

def sanitize_input_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'[\ud800-\udfff]', '', text)
    return text.replace('\u0000', '').strip()

def execute_command_1_pipeline(chapter_id: str, subject: Optional[str] = None):
    """Run the blueprint engine for ``chapter_id``.

    Subject resolution priority:
      1. Explicit ``subject`` arg
      2. ``utils.paths.resolve_subject()`` (env var / pointer / legacy)
      3. Auto-discovery by scanning the Master Syllabus for the
         chapter's owning subject (preserves the original behaviour
         when the command is invoked without --subject).
    """
    print(f"\n[INITIALIZING] Command 1 Engine Execution for Target Cache: {chapter_id}")

    from utils.paths import (
        MASTER_SYLLABUS_PATH,
        NCERT_TEXTBOOKS_DIR,
        SubjectPaths,
        resolve_subject,
    )
    TEXTBOOK_DIR = NCERT_TEXTBOOKS_DIR

    # --- Resolve the active subject --------------------------------
    target_subject: Optional[str] = None
    explicit_subject = (subject or "").strip().lower() or None
    if explicit_subject:
        target_subject = explicit_subject
        print(f"[INPUT] Explicit subject passed: '{target_subject}'")
    else:
        try:
            target_subject = resolve_subject()
            print(f"[INPUT] Subject resolved from environment/pointer: '{target_subject}'")
        except ValueError:
            target_subject = None  # fall through to auto-discovery

    # Auto-discovery fallback: scan the Master Syllabus for the
    # chapter's owning subject. This preserves the original command
    # behaviour for callers that don't pass --subject and don't have
    # the ambient pointer set.
    master_syllabus = load_master_syllabus(MASTER_SYLLABUS_PATH)
    chapter_metadata = None
    if target_subject:
        candidate = master_syllabus.get(target_subject, {})
        if candidate.get("chapters", {}).get(chapter_id):
            chapter_metadata = candidate["chapters"][chapter_id]
        else:
            print(f"[WARN] Subject '{target_subject}' does not own {chapter_id}; auto-discovering owner.")
            target_subject = None

    if not chapter_metadata:
        for candidate_subject, content in master_syllabus.items():
            if "chapters" in content and chapter_id in content["chapters"]:
                target_subject = candidate_subject
                chapter_metadata = content["chapters"][chapter_id]
                break

    if not chapter_metadata:
        print(f"[CRITICAL ERROR] {chapter_id} is completely absent from Master Syllabus mapping.")
        sys.exit(1)

    target_subject_norm = target_subject.strip().lower()

    # --- Per-subject workspace -------------------------------------
    paths = SubjectPaths.for_subject(target_subject_norm)
    paths.active_workspace.parent.mkdir(parents=True, exist_ok=True)

    milestones_list = []
    atomic_chunks = chapter_metadata.get("atomic_chunks", [])
    for chunk in atomic_chunks:
        core_milestones = chunk.get("core_milestones", [])
        for ms in core_milestones:
            if ms not in milestones_list:
                milestones_list.append(ms)

    if not milestones_list:
        milestones_list = chapter_metadata.get("milestones", [])

    print(f"[VERIFIED] Upstream Map Match: Found {chapter_id} under Subject Key: '{target_subject_norm}'")
    print(f"[PINNED] Per-subject workspace: {paths.root}")

    # --- IDEMPOTENT FAST PATH --------------------------------------
    # The C1 command writes 100+ KB of structured data derived from an
    # LLM call that costs real time and API quota. If a previous run
    # already produced a valid blueprint for this chapter and the
    # files are still on disk, re-running C1 is wasted work and — as
    # the original failure showed — risks a JSON parse error from the
    # model returning a slightly different response shape on retry.
    # So we short-circuit:
    #
    #   - If both the active workspace AND the backup file are valid,
    #     log a "no-op" line and exit 0 immediately.
    #   - If only the active workspace is valid, re-derive the backup
    #     from it (atomic write) and exit 0.
    #   - Otherwise, fall through to the full LLM pipeline.
    try:
        heal_result = _self_heal_backup(paths, chapter_id)
        if heal_result == "no_op":
            backup_path = paths.blueprint_path(chapter_id)
            print(f"[NO-OP] Blueprint already complete and valid; skipping LLM call.")
            print(f"[OK]    chapter_blueprint_{chapter_id}.json -> {backup_path}")
            print(f"[SUCCESS] Blueprint verified; no LLM call required.")
            return
        if heal_result:
            backup_path = paths.blueprint_path(chapter_id)
            print(f"[SELF-HEAL] Backup blueprint re-derived from active workspace.")
            print(f"[WRITE]  chapter_blueprint_{chapter_id}.json -> {backup_path}")
            print(f"[SUCCESS] Blueprint verified via self-heal; no LLM call required.")
            return
    except Exception as e:
        print(f"[WARN] Self-heal path raised (continuing with full pipeline): {e}")

    isolated_textbook_dir = TEXTBOOK_DIR / target_subject_norm
    raw_textbook_content = locate_and_read_textbook(isolated_textbook_dir, chapter_id)
    clean_textbook_content = sanitize_input_text(raw_textbook_content)

    print("[PROCESS] Dispatching extraction sequence to GenAI...")
    try:
        # Switched to Gemini 3.1 Flash-Lite
        MODEL_NAME = get_default_model("command_1_blueprint")
        EMBEDDING_MODEL = "gemini-embedding-2"

        prompt = f"""
        You are the structural data engineering layer of the HY-TUTOR local system.
        Target Chapter: {chapter_id}
        Valid Learning Milestones: {json.dumps(milestones_list)}
        
        RAW SOURCE TEXT:
        {clean_textbook_content}
        
        PROCESSING INSTRUCTIONS:
        1. Conceptual Milestone Chunking: Split the text into sub-topics aligned with the milestones.
        2. ZERO SUMMARIZATION RULE (FATAL PENALTY): When placing text into the 'cleaned_text' field for each chunk, you MUST copy the entire verbatim source text related to that milestone. Do not compress, do not paraphrase, do not summarize. We need 100% of the raw textbook data distributed across the chunks.
        """

        # PHASE 1: Logical Chunking via Inference Gateway (automatic logging + retries)
        try:
            raw_text, _model_used = call_gemini(
                "command_1_blueprint",
                MODEL_NAME,
                prompt,
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=ChapterBlueprint,
                max_retries=5,
            )
        except RuntimeError as e:
            print(f"[LLM EXECUTION FAULT] Blueprint chunking failed after retries: {e}")
            sys.exit(1)

        # Clean markdown if present
        raw_text = raw_text.strip()
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            if lines[0].startswith("```json") or lines[0].startswith("```"):
                raw_text = "\n".join(lines[1:-1])

        try:
            blueprint_json = json.loads(raw_text.strip())
        except json.JSONDecodeError as e:
            print(f"[LLM EXECUTION FAULT] Failed to parse AI response as JSON: {e}")
            sys.exit(1)
        
        # PHASE 2: Semantic Vectorization (Gemini Embedding 2) — direct embed_content call
        # Kept outside the gateway because the gateway wraps generate_content only.
        print(f"[PROCESS] Generating high-precision embeddings for {len(blueprint_json['chunks'])} chunks...")
        chunk_texts = [chunk["cleaned_text"] for chunk in blueprint_json["chunks"]]
        
        if chunk_texts:
            try:
                # Lazy import here so embedding SDK is only needed if this phase runs
                from google import genai
                from google.genai import types
                _embed_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
                _embed_start = time.time()
                # Batch processing the chunks into the embedding space
                embed_response = _embed_client.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=chunk_texts,
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_DOCUMENT",
                        output_dimensionality=3072 # Preserving maximum granularity
                    )
                )
                
                # Zip the vectors back into the JSON blueprint
                for i, embedding in enumerate(embed_response.embeddings):
                    blueprint_json["chunks"][i]["chunk_embedding"] = embedding.values

                record_inference(
                    command="command_1_blueprint",
                    model=EMBEDDING_MODEL,
                    provider="google_genai",
                    status="success",
                    duration_ms=int((time.time() - _embed_start) * 1000),
                    prompt=f"{len(chunk_texts)} chunks",
                    response_text="",
                    response=embed_response,
                    api_key=os.getenv("GEMINI_API_KEY", ""),
                )
                    
            except Exception as e:
                record_inference(
                    command="command_1_blueprint",
                    model=EMBEDDING_MODEL,
                    provider="google_genai",
                    status="failure",
                    duration_ms=int((time.time() - _embed_start) * 1000) if '_embed_start' in dir() else 0,
                    error=str(e)[:500],
                )
                print(f"[WARNING] Embedding API fault. Proceeding without vectors. Error: {e}")

        # PHASE 3: Cache Writing (per-subject)
        OUTPUT_CACHE_PATH = paths.active_workspace
        BACKUP_CACHE_PATH = paths.blueprint_path(chapter_id)

        if OUTPUT_CACHE_PATH.exists():
            try:
                with open(OUTPUT_CACHE_PATH, "r", encoding="utf-8") as f:
                    existing_state = json.load(f)
                    blueprint_json["current_active_chunk_index"] = existing_state.get("current_active_chunk_index", 0)
                    blueprint_json["active_state"] = existing_state.get("active_state", "STATE_A")
            except Exception:
                pass

        if "current_active_chunk_index" not in blueprint_json:
             blueprint_json["current_active_chunk_index"] = 0

        # All four writes below use atomic temp+replace so that a crash,
        # OOM kill, or subprocess timeout mid-write can never leave a
        # half-written JSON file in place — the previous good copy is
        # preserved until the new one is fully flushed and fsynced.
        _atomic_write_json(OUTPUT_CACHE_PATH, blueprint_json)
        _atomic_write_json(BACKUP_CACHE_PATH, blueprint_json)

        # --- PHASE 3b: Per-Chapter Folder Writing (PHASE 2) -----------------
        chapter_dir = paths.chapter_dir(chapter_id)
        blueprint_dir = chapter_dir / "blueprint"
        blueprint_dir.mkdir(parents=True, exist_ok=True)

        for chunk in blueprint_json.get("chunks", []):
            chunk_file = blueprint_dir / f"chunk_{chunk.get('chunk_index', 0):02d}.json"
            chunk_payload = {
                "active_chapter_id": chapter_id,
                "subject_name": blueprint_json.get("subject_name", target_subject_norm),
                "chunk_index": chunk.get("chunk_index"),
                "milestone_alignment": chunk.get("milestone_alignment"),
                "cleaned_text": chunk.get("cleaned_text"),
                "iat_priority": chunk.get("iat_priority"),
                "guardrail_status": chunk.get("guardrail_status"),
                "chunk_embedding": chunk.get("chunk_embedding"),
            }
            _atomic_write_json(chunk_file, chunk_payload)

        import time as _time
        metadata_payload = {
            "active_chapter_id": chapter_id,
            "subject_name": blueprint_json.get("subject_name", target_subject_norm),
            "total_chunks_in_chapter": blueprint_json.get("total_chunks_in_chapter", 0),
            "deep_thinking_chunking_plan": blueprint_json.get("deep_thinking_chunking_plan", ""),
            "created_at": _time.strftime("%Y-%m-%dT%H:%M:%S"),
            "last_modified": _time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        _atomic_write_json(paths.metadata_path(chapter_id), metadata_payload)

        print(f"[WRITE]  chapters/{chapter_id}/blueprint/ (per-chunk files)")
        print(f"[WRITE]  chapters/{chapter_id}/metadata.json")

        print(f"[SUCCESS] Blueprint compiled and vectorized with {blueprint_json['total_chunks_in_chapter']} operational chunks.")
        print(f"[WRITE]  active_chapter_workspace.json -> {OUTPUT_CACHE_PATH}")
        print(f"[WRITE]  chapter_blueprint_{chapter_id}.json -> {BACKUP_CACHE_PATH}")

    except Exception as e:
        print(f"[LLM EXECUTION FAULT] Generation API pass aborted: {e}")
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HY-TUTOR Command 1 Blueprint Engine")
    parser.add_argument("chapter_id", nargs="?", help="Target Chapter ID (e.g., CH_12_03)")
    parser.add_argument("--subject", type=str, default=None,
                        help="Active subject (e.g., mathematics). If omitted, "
                             "resolved from the environment / pointer / Master Syllabus.")
    args = parser.parse_args()
    if not args.chapter_id:
        # Preserve the original bare-arg behaviour: with no chapter_id we
        # exit 1 silently (matches the pre-refactor contract that
        # tests/test_subprocess.py relies on for a "no-args" check).
        sys.exit(1)
    execute_command_1_pipeline(args.chapter_id, subject=args.subject)
