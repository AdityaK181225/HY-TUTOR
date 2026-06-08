"""
HY-TUTOR: LEVEL 8 CHAPTER NOTES COMPILER (command_8_compile_notes.py)

After all chunks for a chapter are processed, compile all unified lessons
(chapters/<chapter_id>/lesson/chunk_*.md) into a single chapters/<chapter_id>/notes.md.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Optional


def execute_command_8_pipeline(chapter_id: str, subject: Optional[str] = None):
    from utils.paths import SubjectPaths, resolve_subject

    try:
        resolved = resolve_subject(subject)
    except ValueError as e:
        print(f"[ERROR] command_8_compile_notes: {e}")
        sys.exit(1)

    paths = SubjectPaths.for_subject(resolved)
    chapter_dir = paths.chapter_dir(chapter_id)
    lesson_dir = chapter_dir / "lesson"

    if not lesson_dir.exists():
        print(f"[WARNING] No lesson directory found at {lesson_dir}")
        print("[INFO] No unified lessons to compile yet.")
        return

    lesson_files = sorted(lesson_dir.glob("chunk_*.md"))
    if not lesson_files:
        print(f"[WARNING] No lesson chunk files found in {lesson_dir}")
        return

    metadata_file = paths.metadata_path(chapter_id)
    total_chunks = len(lesson_files)
    subject_name = resolved
    if metadata_file.exists():
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            total_chunks = metadata.get("total_chunks_in_chapter", len(lesson_files))
            subject_name = metadata.get("subject_name", resolved)
        except Exception:
            pass

    print(f"\n[INITIALIZING] Command 8: Compiling notes for {chapter_id} | Subject: {subject_name}")
    print(f"[PROCESS] Found {len(lesson_files)} unified lesson chunk(s)")

    notes_lines = []
    notes_lines.append(f"# {subject_name}: {chapter_id} -- Compiled Notes\n")
    notes_lines.append(f"> Auto-compiled from {len(lesson_files)} unified lesson chunks.")
    notes_lines.append(f"> Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    notes_lines.append("---\n")

    for i, lf in enumerate(lesson_files):
        chunk_idx_str = lf.stem.replace("chunk_", "")
        try:
            chunk_idx = int(chunk_idx_str)
        except ValueError:
            chunk_idx = i

        notes_lines.append(f"## Chunk {chunk_idx:02d}\n")
        try:
            content = lf.read_text(encoding="utf-8").strip()
            notes_lines.append(content)
        except Exception as e:
            notes_lines.append(f"*Error reading {lf.name}: {e}*")
        notes_lines.append("\n---\n")

    notes_path = paths.notes_path(chapter_id)
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.write_text("\n".join(notes_lines), encoding="utf-8")

    print(f"[SUCCESS] Compiled {len(lesson_files)} lesson chunks into notes.md")
    print(f"[WRITE] {notes_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HY-TUTOR Command 8: Chapter Notes Compiler")
    parser.add_argument("chapter_id", nargs="?", help="Target Chapter ID (e.g., CH_12_03)")
    parser.add_argument("--subject", type=str, default=None,
                        help="Active subject (e.g., mathematics). If omitted, "
                             "resolved from the environment / pointer.")
    args = parser.parse_args()
    if not args.chapter_id:
        sys.exit(1)
    execute_command_8_pipeline(args.chapter_id, subject=args.subject)