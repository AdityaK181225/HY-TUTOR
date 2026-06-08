"""
HY-TUTOR: Update Checker
Reads the local git state and compares against the configured remote.
Results are cached to disk for 6 hours so we don't hit the network on
every Streamlit rerun. The whole module is fail-soft \u2014 if git isn't
installed, the network is down, or this isn't a git repo, we return
sane defaults and never raise.
"""

import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ============================================================================
# PATHS
# ============================================================================

def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


CACHE_PATH = _project_root() / "data_library" / "active_workspace" / "update_cache.json"
CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)


CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 hours
GIT_TIMEOUT = 10  # seconds per subprocess call


# ============================================================================
# GIT HELPERS
# ============================================================================

def _git_available() -> bool:
    return shutil.which("git") is not None


def _run_git(args: List[str], cwd: Optional[Path] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Run a git command and return (stdout, stderr) both stripped, or (None, err)
    on any failure (timeout, non-zero exit, missing binary).
    """
    if not _git_available():
        return None, "git binary not found"
    cmd = ["git"] + args
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd or _project_root()),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
        if result.returncode == 0:
            return result.stdout.strip(), None
        return None, (result.stderr or "").strip()[:500]
    except subprocess.TimeoutExpired:
        return None, "git timed out"
    except Exception as e:  # noqa: BLE001
        return None, str(e)[:500]


def _is_git_repo() -> bool:
    out, _ = _run_git(["rev-parse", "--is-inside-work-tree"])
    return out == "true"


def _current_branch() -> Optional[str]:
    out, _ = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    return out


def _current_head() -> Optional[str]:
    out, _ = _run_git(["rev-parse", "HEAD"])
    return out


def _describe() -> Optional[str]:
    """Best-effort git describe \u2014 falls back to None when no tags exist."""
    out, _ = _run_git(["describe", "--tags", "--always", "--dirty"])
    return out


def _remote_default_branch() -> Optional[str]:
    """
    Resolve the primary branch of `origin` (the branch the local repo
    would track by default). Falls back to 'main', then 'master'.
    """
    sym, _ = _run_git(["symbolic-ref", "refs/remotes/origin/HEAD"])
    if sym:
        return sym.split("/")[-1]
    out, _ = _run_git(["remote", "show", "origin"])
    if out:
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("HEAD branch:"):
                return line.split(":", 1)[1].strip()
    for candidate in ("main", "master"):
        probe, _ = _run_git(["rev-parse", "--verify", f"origin/{candidate}"])
        if probe:
            return candidate
    return None


def _remote_head(branch: str) -> Optional[str]:
    out, _ = _run_git(["rev-parse", f"origin/{branch}"])
    return out


def _is_working_tree_clean() -> bool:
    out, _ = _run_git(["status", "--porcelain"])
    return out == "" or out is None


def _commits_behind(local: str, remote: str, n: int = 20) -> List[Dict[str, str]]:
    """
    List the first `n` commits on `remote` that are not on `local`,
    in reverse-chronological order.
    """
    fmt = "%h%x09%an%x09%s%x09%ad"
    out, _ = _run_git(["log", f"{local}..{remote}", f"--max-count={n}", f"--format={fmt}", "--date=short"])
    if not out:
        return []
    commits: List[Dict[str, str]] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 4:
            commits.append({
                "hash": parts[0],
                "author": parts[1],
                "subject": parts[2],
                "date": parts[3],
            })
    return commits


def _fetch(remote: str = "origin") -> Tuple[bool, str]:
    """git fetch <remote> \u2014 non-destructive refresh of remote refs."""
    out, err = _run_git(["fetch", remote, "--quiet"])
    if out is None and err is None:
        return False, "git fetch failed silently"
    if err:
        return False, err
    return True, ""


def _pull_ff_only(remote: str, branch: str) -> Tuple[bool, str]:
    """
    git pull --ff-only <remote> <branch>. Refuses anything but fast-forward.
    """
    out, err = _run_git(["pull", "--ff-only", remote, branch])
    if out is None and err is None:
        return False, "git pull failed silently"
    if err:
        return False, err
    return True, (out or "").strip()


# ============================================================================
# CACHE
# ============================================================================

def _read_cache() -> Optional[Dict[str, Any]]:
    if not CACHE_PATH.exists():
        return None
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_cache(payload: Dict[str, Any]) -> None:
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _is_cache_fresh(cache: Optional[Dict[str, Any]]) -> bool:
    if not cache:
        return False
    ts = cache.get("checked_at_unix")
    if not isinstance(ts, (int, float)):
        return False
    return (time.time() - float(ts)) < CACHE_TTL_SECONDS


# ============================================================================
# PUBLIC API
# ============================================================================

def get_status(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Return a status dict describing how the local repo compares to remote.

    Shape:
        {
            "is_git_repo": bool,
            "git_available": bool,
            "current_branch": Optional[str],
            "current_head_short": Optional[str],
            "current_describe": Optional[str],
            "remote_branch": Optional[str],
            "remote_head_short": Optional[str],
            "is_clean": bool,
            "status": "up_to_date" | "behind" | "ahead" | "diverged" |
                      "local_changes" | "no_remote" | "not_git" | "no_git" | "offline",
            "commits_behind_count": int,
            "commits_behind": [{hash, author, subject, date}, ...],
            "last_check_iso": str,
            "error": Optional[str],
        }
    """
    if not _git_available():
        return _status("no_git", error="git binary not found on PATH")

    if not _is_git_repo():
        return _status("not_git", error="Project directory is not a git repository")

    if not force_refresh:
        cached = _read_cache()
        if _is_cache_fresh(cached):
            return cached["status"]

    return check_now()


def check_now() -> Dict[str, Any]:
    """Force a fresh check, updating the cache. Network is required only for fetch."""
    if not _git_available():
        return _status("no_git", error="git binary not found on PATH")
    if not _is_git_repo():
        return _status("not_git", error="Project directory is not a git repository")

    branch = _current_branch()
    head = _current_head()
    describe = _describe()
    is_clean = _is_working_tree_clean()

    remote_branch = _remote_default_branch()
    if not remote_branch:
        payload = _status(
            "no_remote",
            current_branch=branch,
            current_head_short=(head or "")[:7] if head else None,
            current_describe=describe,
            is_clean=is_clean,
            error="No 'origin' remote configured",
        )
        _write_cache(payload)
        return payload

    # Try to fetch (network required). Fail-soft if it fails.
    ok, fetch_err = _fetch("origin")
    if not ok:
        # Offline path \u2014 still return whatever we know locally.
        offline = _status(
            "offline",
            current_branch=branch,
            current_head_short=(head or "")[:7] if head else None,
            current_describe=describe,
            is_clean=is_clean,
            remote_branch=remote_branch,
            error=f"git fetch failed: {fetch_err}",
        )
        _write_cache(offline)
        return offline

    remote_head = _remote_head(remote_branch)

    if not head or not remote_head:
        payload = _status(
            "no_remote",
            current_branch=branch,
            current_head_short=(head or "")[:7] if head else None,
            current_describe=describe,
            is_clean=is_clean,
            remote_branch=remote_branch,
            error="Could not resolve local or remote HEAD",
        )
        _write_cache(payload)
        return payload

    if not is_clean:
        # Surface the dirty state but still compute the version delta.
        behind = _commits_behind(head, remote_head)
        payload = _status(
            "local_changes",
            current_branch=branch,
            current_head_short=head[:7],
            current_describe=describe,
            is_clean=False,
            remote_branch=remote_branch,
            remote_head_short=remote_head[:7],
            commits_behind_count=len(behind),
            commits_behind=behind,
            error="Working tree has uncommitted changes \u2014 pull may conflict",
        )
        _write_cache(payload)
        return payload

    behind = _commits_behind(head, remote_head)
    if not behind:
        payload = _status(
            "up_to_date",
            current_branch=branch,
            current_head_short=head[:7],
            current_describe=describe,
            is_clean=True,
            remote_branch=remote_branch,
            remote_head_short=remote_head[:7],
            commits_behind_count=0,
            commits_behind=[],
        )
        _write_cache(payload)
        return payload

    payload = _status(
        "behind",
        current_branch=branch,
        current_head_short=head[:7],
        current_describe=describe,
        is_clean=True,
        remote_branch=remote_branch,
        remote_head_short=remote_head[:7],
        commits_behind_count=len(behind),
        commits_behind=behind,
    )
    _write_cache(payload)
    return payload


def do_pull() -> Tuple[bool, str]:
    """
    Run `git pull --ff-only` against the resolved remote/branch.
    Returns (success, message).
    """
    if not _git_available():
        return False, "git binary not found"
    if not _is_git_repo():
        return False, "Not a git repository"
    if not _is_working_tree_clean():
        return False, "Working tree has uncommitted changes. Commit or stash them before pulling."
    remote_branch = _remote_default_branch()
    if not remote_branch:
        return False, "No origin remote configured"
    ok, msg = _pull_ff_only("origin", remote_branch)
    if ok:
        # Invalidate cache so the next status call is fresh.
        try:
            if CACHE_PATH.exists():
                CACHE_PATH.unlink()
        except Exception:
            pass
    return ok, msg


# ============================================================================
# HELPERS
# ============================================================================

def _status(
    state: str,
    *,
    current_branch: Optional[str] = None,
    current_head_short: Optional[str] = None,
    current_describe: Optional[str] = None,
    is_clean: Optional[bool] = None,
    remote_branch: Optional[str] = None,
    remote_head_short: Optional[str] = None,
    commits_behind_count: int = 0,
    commits_behind: Optional[List[Dict[str, str]]] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "is_git_repo": state not in ("not_git",),
        "git_available": state != "no_git",
        "current_branch": current_branch,
        "current_head_short": current_head_short,
        "current_describe": current_describe,
        "is_clean": is_clean,
        "remote_branch": remote_branch,
        "remote_head_short": remote_head_short,
        "status": state,
        "commits_behind_count": commits_behind_count,
        "commits_behind": commits_behind or [],
        "last_check_iso": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "checked_at_unix": time.time(),
        "error": error,
    }


def format_state_badge(state: str) -> Tuple[str, str]:
    """Return (emoji, label) for a state value."""
    mapping = {
        "up_to_date": ("\U0001F7E2", "Up to date"),
        "behind": ("\U0001F7E1", "Updates available"),
        "ahead": ("\U0001F7E1", "Local commits ahead"),
        "diverged": ("\U0001F7E0", "Diverged from remote"),
        "local_changes": ("\U0001F534", "Uncommitted local changes"),
        "no_remote": ("\u26A0\ufe0f", "No remote configured"),
        "not_git": ("\u26A0\ufe0f", "Not a git repository"),
        "no_git": ("\u26A0\ufe0f", "git not installed"),
        "offline": ("\u26A0\ufe0f", "Offline \u2014 showing last cached state"),
    }
    return mapping.get(state, ("\u2753", state))


# ============================================================================
# PACKAGE INSTALLATION (combined update flow)
# ============================================================================

PIP_TIMEOUT = 600  # seconds — chromadb et al. can be slow to build wheels


def _parse_pip_output(full_output: str) -> List[Tuple[str, Optional[str], str]]:
    """
    Parse pip's ``Successfully installed X-Y Z-A ...`` line into a list of
    ``(package_name, old_version_or_None, new_version)`` tuples.

    pip's "Successfully installed" line format::

        Successfully installed packageA-1.2.3 packageB-4.5.6

    Older pip versions sometimes only emit a single package, so we tokenise
    defensively.  Hyphenated package names (e.g. ``pdfminer-six``) are safe
    because pip's format is unambiguously ``name-version`` and we split on
    the *last* hyphen.
    """
    out: List[Tuple[str, Optional[str], str]] = []
    for line in full_output.splitlines():
        line = line.strip()
        if not line.startswith("Successfully installed"):
            continue
        tokens = line.split()[2:]  # drop the first two words
        for spec in tokens:
            if "-" not in spec:
                continue
            idx = spec.rfind("-")
            name, version = spec[:idx], spec[idx + 1:]
            if name and version:
                out.append((name, None, version))
    return out


def _run_pip_install(requirements_file: Optional[Path] = None) -> Dict[str, Any]:
    """
    Run ``python -m pip install -r requirements.txt`` and parse the output.

    Returns a dict with::

        ok (bool), exit_code (int), message (str — tail of pip output),
        installed (list of (name, old, new) tuples), error (str | None)

    The helper is fail-soft: any exception (timeout, missing pip, IO error)
    returns ``ok=False`` and a string in ``error`` rather than raising.
    """
    import sys  # local import — this module is imported during Streamlit boot

    req_path = requirements_file or (_project_root() / "requirements.txt")
    if not req_path.exists():
        return {
            "ok": False,
            "exit_code": -1,
            "message": "",
            "installed": [],
            "error": f"requirements file not found: {req_path}",
        }

    cmd = [sys.executable, "-m", "pip", "install", "-r", str(req_path)]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(_project_root()),
            capture_output=True,
            text=True,
            timeout=PIP_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "exit_code": -1,
            "message": "",
            "installed": [],
            "error": f"pip install timed out after {PIP_TIMEOUT}s",
        }
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "exit_code": -1,
            "message": "",
            "installed": [],
            "error": str(e)[:500],
        }

    full_output = (result.stdout or "") + "\n" + (result.stderr or "")
    if result.returncode != 0:
        return {
            "ok": False,
            "exit_code": result.returncode,
            "message": full_output[-4000:],
            "installed": [],
            "error": f"pip exited with code {result.returncode}",
        }

    return {
        "ok": True,
        "exit_code": 0,
        "message": full_output[-4000:],
        "installed": _parse_pip_output(full_output),
        "error": None,
    }


def do_pull_and_install() -> Dict[str, Any]:
    """
    Pull the latest code from ``origin`` and install any new requirements.

    This is the "Update & restart" one-shot. Steps:

        1. Capture local HEAD so we can detect changes to ``requirements.txt``
        2. Run :func:`do_pull` (fast-forward only, refuses on dirty tree)
        3. Detect whether ``requirements.txt`` was modified in the just-
           pulled commits (informational; the pip install always runs)
        4. Run :func:`_run_pip_install` (fast no-op when nothing changed)
        5. Flag ``needs_restart=True`` so the UI can prompt for it

    Return shape::

        {
            "ok":                   bool,   # pull AND pip install both OK
            "pulled":               bool,   # git pull succeeded
            "pull_message":         str,    # git pull output
            "requirements_changed": bool,   # requirements.txt was touched
            "pip_ok":               bool,   # pip install succeeded
            "pip_message":          str,    # pip output (tail)
            "upgraded_packages":    [str],  # human-readable ("name old→new")
            "pip_error":            str | None,
            "needs_restart":        bool,   # always True after a successful pull
        }
    """
    result: Dict[str, Any] = {
        "ok": False,
        "pulled": False,
        "pull_message": "",
        "requirements_changed": False,
        "pip_ok": True,
        "pip_message": "",
        "upgraded_packages": [],
        "pip_error": None,
        "needs_restart": False,
    }

    # 1. Capture the local HEAD before the pull, so we can diff requirements.txt
    pre_head = _current_head()

    # 2. Pull (refuses on dirty tree / no remote / not a repo)
    pull_ok, pull_msg = do_pull()
    result["pulled"] = pull_ok
    result["pull_message"] = pull_msg
    if not pull_ok:
        return result

    # 3. Did requirements.txt change in the just-pulled commits?
    post_head = _current_head()
    if pre_head and post_head and pre_head != post_head:
        diff_out, _ = _run_git(
            ["diff", f"{pre_head}..{post_head}", "--name-only", "--", "requirements.txt"]
        )
        if diff_out and "requirements.txt" in diff_out:
            result["requirements_changed"] = True
    # If pre_head == post_head the pull was a no-op (already up to date)
    # and requirements_changed stays False. pip install will still run as a
    # safety net, but will be a fast no-op.

    # 4. Always run pip install \u2014 fast no-op when nothing changed, real
    #    upgrade when it did. Failures here don't roll back the pull; we
    #    just report them so the user can fix the env from a terminal.
    pip_result = _run_pip_install()
    result["pip_ok"] = pip_result["ok"]
    result["pip_message"] = pip_result["message"]
    result["pip_error"] = pip_result["error"]
    result["upgraded_packages"] = [
        f"{name} {old}\u2192{new}" if old else f"{name} (new: {new})"
        for (name, old, new) in pip_result["installed"]
    ]

    # 5. Always flag a restart after a successful pull \u2014 the running process
    #    has the old code in memory, and may have old packages imported.
    result["needs_restart"] = pull_ok

    result["ok"] = pull_ok and pip_result["ok"]
    return result


__all__ = [
    "get_status",
    "check_now",
    "do_pull",
    "do_pull_and_install",
    "format_state_badge",
    "CACHE_PATH",
    "CACHE_TTL_SECONDS",
]
