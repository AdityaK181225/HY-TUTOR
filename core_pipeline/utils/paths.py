"""
HY-TUTOR: Centralized Path Management
Provides consistent path definitions and validation across the entire pipeline.

June 2026 refactor:
  The legacy flat data_library/active_workspace/ and project-root
  chapter_cache/ directories have been fully replaced by per-subject
  trees under data_library/subject_workspaces/<subject>/.
  All call sites now resolve the correct paths via the SubjectPaths
  class or the resolve_subject() + get_subject_*() helpers.
"""

import os
import json as _json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent

# ============================================================================
# DIRECTORY STRUCTURE
# ============================================================================

CONFIG_DIR = PROJECT_ROOT / "config"
DATA_LIBRARY = PROJECT_ROOT / "data_library"
METADATA_DIR = DATA_LIBRARY / "metadata"
RAW_SOURCES_DIR = DATA_LIBRARY / "raw_sources"

CBSE_GUIDELINES_DIR = RAW_SOURCES_DIR / "cbse_guidelines"
NCERT_TEXTBOOKS_DIR = RAW_SOURCES_DIR / "ncert_textbooks"
REFERENCE_MANUALS_DIR = RAW_SOURCES_DIR / "reference_manuals"
NCERT_EXEMPLARS_DIR = RAW_SOURCES_DIR / "ncert_exemplars"

SUBJECT_WORKSPACES_DIR = DATA_LIBRARY / "subject_workspaces"

INTERFACE_DIR = PROJECT_ROOT / "interface"
INTERFACE_ASSETS_DIR = INTERFACE_DIR / "assets"
CORE_PIPELINE_DIR = PROJECT_ROOT / "core_pipeline"

# ============================================================================
# GLOBAL FILE PATHS
# ============================================================================

MASTER_SYLLABUS_PATH = METADATA_DIR / "Master_Subject_Syllabus.json"
GLOBAL_TRACKER_PATH = DATA_LIBRARY / "Global_Subject_Tracker.json"
ENV_PATH = CONFIG_DIR / ".env"
ENV_SETUP_PATH = CONFIG_DIR / "env_setup.sh"

# ============================================================================
# PATH VALIDATION
# ============================================================================

def validate_project_root() -> bool:
    for expected in ["core_pipeline", "data_library", "interface", "config"]:
        if not (PROJECT_ROOT / expected).exists():
            return False
    return True


# ============================================================================
# RAW-SOURCE HELPERS (global, not per-subject)
# ============================================================================

def get_subject_dir(subject: str) -> Path:
    return RAW_SOURCES_DIR / subject.lower()


def get_chapter_path(subject: str, chapter_id: str, source_type: str = "ncert") -> Path:
    source_dirs = {
        "ncert": NCERT_TEXTBOOKS_DIR,
        "reference": REFERENCE_MANUALS_DIR,
        "exemplar": NCERT_EXEMPLARS_DIR,
        "cbse": CBSE_GUIDELINES_DIR,
    }
    base_dir = source_dirs.get(source_type, NCERT_TEXTBOOKS_DIR) / subject.lower()
    return base_dir / f"{chapter_id}.md"


# ============================================================================
# PER-SUBJECT WORKSPACE HELPERS
# ============================================================================

def get_subject_workspace(subject: str) -> Path:
    return SUBJECT_WORKSPACES_DIR / subject.lower()

def get_subject_router_state(subject: str) -> Path:
    return get_subject_workspace(subject) / "router_state.json"

def get_subject_tracker(subject: str) -> Path:
    return get_subject_workspace(subject) / "subject_tracker.json"

def get_subject_active_workspace(subject: str) -> Path:
    return get_subject_workspace(subject) / "active_chapter_workspace.json"

def get_subject_ui_session(subject: str) -> Path:
    return get_subject_workspace(subject) / "ui_session.json"

def get_subject_chunk_dir(subject: str) -> Path:
    return get_subject_workspace(subject) / "active_chunk"

def get_subject_vector_db(subject: str) -> Path:
    """Per-subject ChromaDB persistent store."""
    return get_subject_workspace(subject) / "vector_db"

def ensure_subject_workspace(subject: str) -> Path:
    ws = get_subject_workspace(subject)
    for subdir in ["active_chunk", "chapters", "vector_db"]:
        (ws / subdir).mkdir(parents=True, exist_ok=True)
    return ws

def get_subject_blueprint_path(subject: str, chapter_id: str) -> Path:
    return get_subject_workspace(subject) / f"chapter_blueprint_{chapter_id}.json"


# ============================================================================
# PATH SANITIZATION
# ============================================================================

def sanitize_path(path_str: str) -> Path:
    path = Path(path_str)
    try:
        resolved = path.resolve()
    except Exception as e:
        raise ValueError(f"Invalid path: {path_str} - {e}")
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        raise ValueError(f"Path escapes project root: {path_str}")
    return resolved


# ============================================================================
# PER-SUBJECT RESOLVER
# ============================================================================

CURRENT_SUBJECT_POINTER = SUBJECT_WORKSPACES_DIR / ".current_subject"


def set_current_subject(subject: str) -> None:
    if subject is None:
        return
    cleaned = str(subject).strip().lower()
    if not cleaned:
        return
    try:
        SUBJECT_WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
        CURRENT_SUBJECT_POINTER.write_text(cleaned, encoding="utf-8")
    except Exception:
        pass


def get_current_subject() -> Optional[str]:
    try:
        if CURRENT_SUBJECT_POINTER.exists():
            value = CURRENT_SUBJECT_POINTER.read_text(encoding="utf-8").strip()
            if value:
                return value.lower()
    except Exception:
        pass
    return None


def resolve_subject(subject: Optional[str] = None) -> str:
    if subject and str(subject).strip():
        return str(subject).strip().lower()
    env_subj = os.getenv("HY_TUTOR_SUBJECT", "").strip().lower()
    if env_subj:
        return env_subj
    ptr = get_current_subject()
    if ptr:
        return ptr
    raise ValueError(
        "No active subject resolved. Pass --subject <name>, "
        "set HY_TUTOR_SUBJECT, or call set_current_subject() first."
    )


@dataclass(frozen=True)
class SubjectPaths:
    subject: str
    root: Path
    chunk_dir: Path
    router_state: Path
    active_workspace: Path
    ui_session: Path
    chapter_cache: Path
    recovery: Path
    blueprint_dir: Path
    chapters_dir: Path
    vector_db_dir: Path

    @staticmethod
    def for_subject(subject: str) -> "SubjectPaths":
        cleaned = (subject or "").strip().lower()
        if not cleaned:
            raise ValueError("Subject cannot be empty")
        ensure_subject_workspace(cleaned)
        root = get_subject_workspace(cleaned)
        _chapters_dir = root / "chapters"
        return SubjectPaths(
            subject=cleaned,
            root=root,
            chunk_dir=root / "active_chunk",
            router_state=root / "router_state.json",
            active_workspace=root / "active_chapter_workspace.json",
            ui_session=root / "ui_session.json",
            chapter_cache=root / "chapter_cache",
            recovery=root / "recovery" / "recovery_state.json",
            blueprint_dir=root,
            chapters_dir=_chapters_dir,
            vector_db_dir=root / "vector_db",
        )

    def blueprint_path(self, chapter_id: str) -> Path:
        return self.blueprint_dir / f"chapter_blueprint_{chapter_id}.json"

    def session_history(self) -> Path:
        return self.chapter_cache / "active_session_history.json"

    def chunk_paths(self) -> dict:
        return {
            "ncert":     self.chunk_dir / "NCERT_chunk.json",
            "reference": self.chunk_dir / "Reference_chunk.json",
            "bridge":    self.chunk_dir / "Bridge_chunk.json",
            "problems":  self.chunk_dir / "Active_Chunk_Problems.json",
            "lesson":    self.chunk_dir / "Unified_Lesson.md",
        }

    # ----------------------------------------------------------------
    # Per-Chapter Archive Folder Helpers (PHASE 2 — CHANGES_PHASE_2.md)
    # ----------------------------------------------------------------

    def chapter_dir(self, chapter_id: str) -> Path:
        """Returns ``chapters/<subject>/<chapter_id>/`` — the archive root."""
        return self.chapters_dir / chapter_id

    def blueprint_chunk_path(self, chapter_id: str, chunk_index: int) -> Path:
        """Per-chunk blueprint file produced by C1."""
        return self.chapter_dir(chapter_id) / "blueprint" / f"chunk_{chunk_index:02d}.json"

    def ncert_chunk_path(self, chapter_id: str, chunk_index: int) -> Path:
        """Archived NCERT mined chunk produced by C2."""
        return self.chapter_dir(chapter_id) / "ncert" / f"chunk_{chunk_index:02d}.json"

    def reference_chunk_path(self, chapter_id: str, chunk_index: int) -> Path:
        """Archived reference mined chunk produced by C3."""
        return self.chapter_dir(chapter_id) / "reference" / f"chunk_{chunk_index:02d}.json"

    def bridge_chunk_path(self, chapter_id: str, chunk_index: int) -> Path:
        """Archived bridge chunk produced by C4."""
        return self.chapter_dir(chapter_id) / "bridge" / f"chunk_{chunk_index:02d}.json"

    def problems_chunk_path(self, chapter_id: str, chunk_index: int) -> Path:
        """Archived problems chunk produced by C5.5."""
        return self.chapter_dir(chapter_id) / "problems" / f"chunk_{chunk_index:02d}.json"

    def lesson_chunk_path(self, chapter_id: str, chunk_index: int) -> Path:
        """Archived unified lesson produced by C5."""
        return self.chapter_dir(chapter_id) / "lesson" / f"chunk_{chunk_index:02d}.md"


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'PROJECT_ROOT', 'CONFIG_DIR', 'DATA_LIBRARY', 'METADATA_DIR',
    'RAW_SOURCES_DIR', 'CBSE_GUIDELINES_DIR', 'NCERT_TEXTBOOKS_DIR',
    'REFERENCE_MANUALS_DIR', 'NCERT_EXEMPLARS_DIR', 'SUBJECT_WORKSPACES_DIR',
    'INTERFACE_DIR', 'INTERFACE_ASSETS_DIR', 'CORE_PIPELINE_DIR',
    'MASTER_SYLLABUS_PATH', 'GLOBAL_TRACKER_PATH', 'ENV_PATH', 'ENV_SETUP_PATH',
    'validate_project_root', 'get_subject_dir', 'get_chapter_path',
    'get_subject_workspace', 'get_subject_router_state', 'get_subject_tracker',
    'get_subject_active_workspace', 'get_subject_ui_session', 'get_subject_chunk_dir',
    'get_subject_vector_db', 'ensure_subject_workspace', 'get_subject_blueprint_path', 'sanitize_path',
    'CURRENT_SUBJECT_POINTER', 'set_current_subject', 'get_current_subject',
    'resolve_subject', 'SubjectPaths',
]