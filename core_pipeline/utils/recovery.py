"""
HY-TUTOR: Recovery Manager
Thread-safe pipeline recovery with JSON persistence, 24h TTL cleanup,
5-attempt cap, and retry/skip/restart/clear actions.
"""

import json
import os
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# TTL and attempt constants
RECOVERY_TTL_HOURS = 24
MAX_ATTEMPTS = 5

# Thread lock for thread-safe operations
_recovery_lock = threading.RLock()


class RecoveryManager:
    """
    Manages pipeline recovery state for failed or interrupted chapters.
    
    Features:
    - Thread-safe JSON persistence
    - 24-hour TTL auto-cleanup
    - 5-attempt cap per chapter
    - Retry/Skip/Restart/Clear actions
    """

    def __init__(self, recovery_dir: Optional[Path] = None):
        """
        Args:
            recovery_dir: Directory for recovery state files.
                         Defaults to data_library/recovery/
        """
        if recovery_dir is None:
            from utils.paths import DATA_LIBRARY
            recovery_dir = DATA_LIBRARY / "recovery"
        self.recovery_dir = recovery_dir
        self.recovery_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self.recovery_dir / "recovery_state.json"

    def _load_state(self) -> Dict[str, Any]:
        """Load recovery state from disk (thread-safe)."""
        with _recovery_lock:
            if not self._state_file.exists():
                return {"chapters": {}}
            try:
                with open(self._state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {"chapters": {}}

    def _save_state(self, state: Dict[str, Any]) -> None:
        """Persist recovery state to disk (thread-safe)."""
        with _recovery_lock:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            temp_fd, temp_path = tempfile.mkstemp(
                dir=str(self._state_file.parent),
                suffix=".tmp",
                prefix=".recovery_",
            )
            try:
                with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2, ensure_ascii=False)
                os.replace(temp_path, str(self._state_file))
            except Exception:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
                raise

    def _cleanup_expired(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Remove entries older than TTL."""
        cutoff = datetime.utcnow() - timedelta(hours=RECOVERY_TTL_HOURS)
        cleaned = {}
        for chap_id, entry in state.get("chapters", {}).items():
            last_ts = entry.get("last_failure_ts")
            if last_ts:
                try:
                    last_dt = datetime.fromisoformat(last_ts)
                    if last_dt > cutoff:
                        cleaned[chap_id] = entry
                except (ValueError, TypeError):
                    # Keep entry if timestamp is malformed
                    cleaned[chap_id] = entry
            else:
                cleaned[chap_id] = entry
        state["chapters"] = cleaned
        return state

    def record_failure(
        self,
        chapter_id: str,
        subject: str,
        failed_command: str,
        error_message: str = "",
        failed_chunk_index: int = 0,
    ) -> None:
        """
        Record a pipeline failure for a chapter.
        Increments attempt count and updates timestamp.
        """
        with _recovery_lock:
            state = self._load_state()
            state = self._cleanup_expired(state)
            chapters = state.setdefault("chapters", {})

            if chapter_id in chapters:
                entry = chapters[chapter_id]
                entry["attempts"] = entry.get("attempts", 0) + 1
                entry["last_failure_ts"] = datetime.utcnow().isoformat()
                entry["failed_command"] = failed_command
                entry["error_message"] = error_message
                entry["failed_chunk_index"] = failed_chunk_index
                entry["subject"] = subject
            else:
                chapters[chapter_id] = {
                    "subject": subject,
                    "failed_command": failed_command,
                    "error_message": error_message,
                    "failed_chunk_index": failed_chunk_index,
                    "attempts": 1,
                    "last_failure_ts": datetime.utcnow().isoformat(),
                    "status": "failed",  # failed | skipped | cleared
                }

            self._save_state(state)

    def can_retry(self, chapter_id: str) -> bool:
        """Check if the chapter has retry attempts remaining."""
        state = self._load_state()
        entry = state.get("chapters", {}).get(chapter_id, {})
        return entry.get("attempts", 0) < MAX_ATTEMPTS

    def get_next_command_index(
        self,
        chapter_id: str,
        execution_path: List[str],
        action: str = "retry",
    ) -> int:
        """
        Determine the next command index to resume from.
        
        Args:
            chapter_id: The chapter to recover
            execution_path: Ordered list of command scripts
            action: "retry" = re-run failed command, "skip" = advance past it,
                    "restart" = start from beginning
            
        Returns:
            Index into execution_path to resume from
        """
        state = self._load_state()
        entry = state.get("chapters", {}).get(chapter_id, {})
        failed_command = entry.get("failed_command", "")

        if action == "restart":
            return 0

        if action == "skip":
            # Find the failed command and advance past it
            for i, cmd in enumerate(execution_path):
                if cmd == failed_command:
                    return min(i + 1, len(execution_path) - 1)
            return 0

        # action == "retry" — re-run the failed command
        for i, cmd in enumerate(execution_path):
            if cmd == failed_command:
                return i
        return 0

    def skip_chapter(self, chapter_id: str) -> None:
        """Mark a chapter as skipped."""
        with _recovery_lock:
            state = self._load_state()
            entry = state.get("chapters", {}).get(chapter_id)
            if entry:
                entry["status"] = "skipped"
                self._save_state(state)

    def clear_chapter(self, chapter_id: str) -> None:
        """Remove a chapter from recovery state entirely."""
        with _recovery_lock:
            state = self._load_state()
            state.get("chapters", {}).pop(chapter_id, None)
            self._save_state(state)

    def clear_all(self) -> None:
        """Clear all recovery state."""
        with _recovery_lock:
            self._save_state({"chapters": {}})

    def get_recoverable_chapters(self) -> List[Dict[str, Any]]:
        """
        List all chapters that can be recovered (not expired, under attempt cap).
        Returns a list of dicts with chapter_id and metadata.
        """
        state = self._load_state()
        state = self._cleanup_expired(state)
        self._save_state(state)  # Persist cleanup

        result = []
        for chap_id, entry in state.get("chapters", {}).items():
            if entry.get("status") == "cleared":
                continue
            result.append({
                "chapter_id": chap_id,
                "subject": entry.get("subject", "unknown"),
                "failed_command": entry.get("failed_command", "unknown"),
                "error_message": entry.get("error_message", ""),
                "attempts": entry.get("attempts", 0),
                "max_attempts": MAX_ATTEMPTS,
                "can_retry": entry.get("attempts", 0) < MAX_ATTEMPTS,
                "status": entry.get("status", "failed"),
                "failed_chunk_index": entry.get("failed_chunk_index", 0),
                "last_failure": entry.get("last_failure_ts", ""),
            })
        return result

    def get_entry(self, chapter_id: str) -> Optional[Dict[str, Any]]:
        """Get the recovery entry for a specific chapter."""
        state = self._load_state()
        return state.get("chapters", {}).get(chapter_id)


__all__ = [
    "RecoveryManager",
    "RECOVERY_TTL_HOURS",
    "MAX_ATTEMPTS",
]