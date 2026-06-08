"""
HY-TUTOR: File Utilities with Thread-Safe Operations
Provides atomic file operations and locking mechanisms to prevent race conditions.
"""

import os
import sys
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional
from contextlib import contextmanager


class FileLock:
    """
    Simple file-based locking mechanism for cross-process synchronization.
    Uses .lock files to prevent concurrent access.
    """
    
    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
    
    def acquire(self, timeout: float = 10.0) -> bool:
        """Acquire the lock, wait up to timeout seconds."""
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Create lock file exclusively
                self.lock_path.parent.mkdir(parents=True, exist_ok=True)
                fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                return True
            except FileExistsError:
                # Lock already exists, wait and retry
                time.sleep(0.1)
        
        return False
    
    def release(self) -> None:
        """Release the lock."""
        try:
            if self.lock_path.exists():
                self.lock_path.unlink()
        except Exception as e:
            print(f"[WARNING] Failed to release lock {self.lock_path}: {e}")
    
    @contextmanager
    def lock(self, timeout: float = 10.0):
        """Context manager for lock acquisition and release."""
        acquired = self.acquire(timeout)
        if not acquired:
            raise TimeoutError(f"Could not acquire lock {self.lock_path} within {timeout}s")
        try:
            yield
        finally:
            self.release()


def get_lock_path(file_path: Path) -> Path:
    """Get the lock file path for a given file."""
    return file_path.with_suffix(file_path.suffix + '.lock')


def safe_write_json(
    file_path: Path,
    data: Any,
    indent: int = 4,
    timeout: float = 10.0,
    backup: bool = True
) -> None:
    """
    Thread-safe JSON write with atomic file operations.
    
    Args:
        file_path: Destination file path
        data: Python object to serialize to JSON
        indent: JSON indentation level
        timeout: Maximum time to wait for lock (seconds)
        backup: Whether to create backup before overwrite
    
    Raises:
        TimeoutError: If lock cannot be acquired within timeout
        Exception: For other file operation errors
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = get_lock_path(file_path)
    lock = FileLock(lock_path)
    
    with lock.lock(timeout):
        # Create backup if requested and file exists
        if backup and file_path.exists():
            try:
                backup_path = file_path.with_suffix(file_path.suffix + '.bak')
                shutil.copy2(file_path, backup_path)
            except Exception as e:
                print(f"[WARNING] Failed to create backup of {file_path}: {e}")
        
        # Write to temporary file first, then rename for atomicity
        temp_fd, temp_path = tempfile.mkstemp(
            dir=str(file_path.parent),
            suffix='.tmp',
            prefix=f'.{file_path.stem}'
        )
        
        try:
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            
            # Atomic rename (works on POSIX, may need fallback on Windows)
            os.replace(temp_path, str(file_path))
            
        except Exception as e:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except Exception:
                pass
            raise Exception(f"Failed to write {file_path}: {e}")


def safe_read_json(
    file_path: Path,
    timeout: float = 10.0
) -> Optional[Any]:
    """
    Thread-safe JSON read with locking.
    
    Args:
        file_path: File path to read
        timeout: Maximum time to wait for lock (seconds)
    
    Returns:
        Parsed JSON data or None if file doesn't exist or is invalid
    
    Raises:
        TimeoutError: If lock cannot be acquired within timeout
    """
    if not file_path.exists():
        return None
    
    lock_path = get_lock_path(file_path)
    lock = FileLock(lock_path)
    
    with lock.lock(timeout):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            print(f"[WARNING] Failed to read {file_path}: {e}")
            return None


def safe_delete(file_path: Path, timeout: float = 10.0) -> bool:
    """
    Thread-safe file deletion with locking.
    
    Args:
        file_path: File path to delete
        timeout: Maximum time to wait for lock (seconds)
    
    Returns:
        True if deletion succeeded, False otherwise
    
    Raises:
        TimeoutError: If lock cannot be acquired within timeout
    """
    if not file_path.exists():
        return True
    
    lock_path = get_lock_path(file_path)
    lock = FileLock(lock_path)
    
    with lock.lock(timeout):
        try:
            if file_path.is_file():
                file_path.unlink()
            elif file_path.is_dir():
                shutil.rmtree(file_path)
            return True
        except Exception as e:
            print(f"[WARNING] Failed to delete {file_path}: {e}")
            return False


def clear_directory(directory_path: Path, timeout: float = 10.0) -> bool:
    """
    Thread-safe directory clearing with locking.
    
    Args:
        directory_path: Directory to clear
        timeout: Maximum time to wait for lock (seconds)
    
    Returns:
        True if clearing succeeded, False otherwise
    
    Raises:
        TimeoutError: If lock cannot be acquired within timeout
    """
    if not directory_path.exists():
        return True
    
    lock_path = directory_path / '.directory.lock'
    lock = FileLock(lock_path)
    
    with lock.lock(timeout):
        try:
            for item in directory_path.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            return True
        except Exception as e:
            print(f"[WARNING] Failed to clear directory {directory_path}: {e}")
            return False


def safe_write_text(
    file_path: Path,
    content: str,
    encoding: str = "utf-8",
    timeout: float = 10.0,
    backup: bool = True,
) -> None:
    """
    Thread-safe text/markdown write with atomic file operations.

    Args:
        file_path: Destination file path
        content: Text content to write
        encoding: File encoding
        timeout: Maximum time to wait for lock (seconds)
        backup: Whether to create backup before overwrite

    Raises:
        TimeoutError: If lock cannot be acquired within timeout
        Exception: For other file operation errors
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = get_lock_path(file_path)
    lock = FileLock(lock_path)

    with lock.lock(timeout):
        if backup and file_path.exists():
            try:
                backup_path = file_path.with_suffix(file_path.suffix + ".bak")
                shutil.copy2(file_path, backup_path)
            except Exception as e:
                print(f"[WARNING] Failed to create backup of {file_path}: {e}")

        temp_fd, temp_path = tempfile.mkstemp(
            dir=str(file_path.parent),
            suffix=".tmp",
            prefix=f".{file_path.stem}",
        )

        try:
            with os.fdopen(temp_fd, "w", encoding=encoding) as f:
                f.write(content)
            os.replace(temp_path, str(file_path))
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise


def atomic_directory_clear(directory_path: Path, timeout: float = 10.0) -> bool:
    """
    Atomically clear a directory's contents under a lock.
    Removes all files and subdirectories but preserves the directory itself.

    Args:
        directory_path: Directory to clear
        timeout: Maximum time to wait for lock (seconds)

    Returns:
        True if clearing succeeded, False otherwise

    Raises:
        TimeoutError: If lock cannot be acquired within timeout
    """
    if not directory_path.exists():
        return True

    directory_path.mkdir(parents=True, exist_ok=True)
    lock_path = directory_path / ".directory.lock"
    lock = FileLock(lock_path)

    with lock.lock(timeout):
        try:
            for item in directory_path.iterdir():
                if item.name == ".directory.lock":
                    continue  # Don't delete the lock file itself
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            return True
        except Exception as e:
            print(f"[WARNING] Failed to atomically clear directory {directory_path}: {e}")
            return False


# Convenience exports
__all__ = [
    'FileLock',
    'get_lock_path',
    'safe_write_json',
    'safe_read_json',
    'safe_delete',
    'clear_directory',
    'safe_write_text',
    'atomic_directory_clear',
]
