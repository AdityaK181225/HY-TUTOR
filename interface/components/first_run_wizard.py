"""
HY-TUTOR: First-Run Wizard
===========================
Renders a small Streamlit panel if the app is launched without a configured
GEMINI_API_KEY. The wizard writes the key to ``config/.env`` and then
redirects straight to the main dashboard.  It is shown **only once** —
on the very first launch.

Called from the top of ``interface/app.py``:
    from components.first_run_wizard import maybe_render_first_run_wizard
    if maybe_render_first_run_wizard():
        st.stop()  # don't render the rest of the app until key is saved
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Tuple

import streamlit as st

# We import the custom icon helper lazily so the wizard works even if the
# rest of the interface layer is still warming up.
try:
    from components.icons import icon
except Exception:  # pragma: no cover — best-effort import
    def icon(name: str, **kwargs):  # type: ignore
        return ""


# Gemini keys from aistudio.google.com start with "AIza" and are ~39 chars.
_GEMINI_KEY_RE = re.compile(r"^AIza[A-Za-z0-9_\-]{30,50}$")

# Link where users can obtain a free Gemini API key.
_GEMINI_KEY_URL = (
    "https://aistudio.google.com/apikey?authuser=1"
    "&_gl=1*ms56u1*_ga*MTk5Njg3MjQzMC4xNzgwNjU5MjUw*"
    "_ga_P1DBVKWT6V*czE3ODA5NzM2MjEkbzIkZzEkdDE3ODA5NzM5MTAkajYwJGwwJGg2"
    "MjA5NDg1Ng.."
)


def _repo_root() -> Path:
    """Resolve the repo root regardless of where streamlit is launched from."""
    return Path(__file__).resolve().parent.parent.parent


def _env_path() -> Path:
    return _repo_root() / "config" / ".env"


def _read_existing_key() -> str:
    """Return the current GEMINI_API_KEY (empty string if missing/blank)."""
    env_file = _env_path()
    if not env_file.exists():
        return ""
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.strip() == "GEMINI_API_KEY":
                return v.strip().strip('"').strip("'")
    except Exception:
        return ""
    return ""


def _save_key(api_key: str) -> Tuple[bool, str]:
    """Atomically write GEMINI_API_KEY to config/.env. Returns (ok, message)."""
    env_file = _env_path()
    env_file.parent.mkdir(parents=True, exist_ok=True)

    # If .env doesn't exist, seed it from .env.example.
    if not env_file.exists():
        example = env_file.parent / ".env.example"
        if example.exists():
            env_file.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            env_file.write_text("# HY-TUTOR environment\n", encoding="utf-8")

    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
        out: list[str] = []
        replaced = False
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith("GEMINI_API_KEY=") or stripped.startswith("# GEMINI_API_KEY="):
                out.append(f"GEMINI_API_KEY={api_key}")
                replaced = True
            else:
                out.append(line)
        if not replaced:
            if out and out[-1].strip() != "":
                out.append("")
            out.append(f"GEMINI_API_KEY={api_key}")

        tmp = env_file.with_suffix(".env.tmp")
        tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
        os.replace(tmp, env_file)
        try:
            os.chmod(env_file, 0o600)
        except Exception:
            pass
        return True, f"Key saved to {env_file}"
    except Exception as exc:  # pragma: no cover — IO error
        return False, f"Failed to write {env_file}: {exc}"


def maybe_render_first_run_wizard() -> bool:
    """Render the wizard **only** when no GEMINI_API_KEY has been configured.

    Returns:
        True if the wizard was shown (caller should ``st.stop()``),
        False if the key exists and the app should render normally.
    """
    if _read_existing_key():
        # Key already set — never show the wizard again.
        return False

    # --- Wizard UI -----------------------------------------------------------
    st.set_page_config(
        page_title="HY-TUTOR — First Run Setup",
        layout="centered",
    )
    _css = """
    <style>
        .hytutor-wizard-wrap {
            max-width: 640px;
            margin: 4rem auto 2rem auto;
            padding: 2rem 2.5rem;
            border-radius: 18px;
            background: #FFF8E7;
            border: 1px solid #E6D9B8;
            box-shadow: 0 8px 32px rgba(120, 90, 30, 0.08);
        }
        .hytutor-wizard-wrap h1 { margin-top: 0; }
        .hytutor-api-link {
            display: inline-block;
            padding: 6px 14px;
            margin: 4px 0 12px 0;
            border-radius: 8px;
            background: #E8F0FE;
            border: 1px solid #4285F4;
            color: #1A73E8;
            font-weight: 600;
            text-decoration: none;
        }
        .hytutor-api-link:hover { background: #D2E3FC; }
    </style>
    """
    st.markdown(_css, unsafe_allow_html=True)
    st.markdown('<div class="hytutor-wizard-wrap">', unsafe_allow_html=True)

    st.markdown(
        f'<h1 style="display:flex;align-items:center;gap:8px;">'
        f'{icon("rocket_launch", size=28)} Welcome to HY-TUTOR</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        "Let's get you set up. You only need to do this **once** — your "
        "API key will be saved locally and the wizard will never appear again."
    )

    # --- API key form --------------------------------------------------------
    st.markdown("### Add your Gemini API key")
    st.markdown(
        "HY-TUTOR uses Google's Gemini API to compile lessons and tutor you."
    )
    st.markdown(
        f'<a class="hytutor-api-link" href="{_GEMINI_KEY_URL}" '
        f'target="_blank" rel="noopener">🔑 &nbsp;Get a free Gemini API key here</a>',
        unsafe_allow_html=True,
    )
    st.markdown("Then paste it below:")

    with st.form("hytutor_first_run_key_form", clear_on_submit=False):
        api_key = st.text_input(
            "GEMINI_API_KEY",
            type="password",
            placeholder="AIza...",
            help=(
                "The key looks like AIzaSy... (about 39 characters). "
                "It is stored locally in config/.env with mode 600."
            ),
        )
        submitted = st.form_submit_button(
            "Save and continue", type="primary", use_container_width=True,
        )

        if submitted:
            if not _GEMINI_KEY_RE.match(api_key.strip()):
                st.error(
                    "That doesn't look like a valid Gemini key. "
                    "It should start with `AIza` and be about 39 characters long. "
                    "Double-check the value you copied."
                )
            else:
                ok, msg = _save_key(api_key.strip())
                if ok:
                    st.success(f"✅ {msg}")
                    st.session_state["_wizard_key_saved"] = True
                else:
                    st.error(msg)

    # --- After key is saved: redirect straight to the dashboard ---------------
    if st.session_state.get("_wizard_key_saved"):
        st.info("Key saved! Redirecting to HY-TUTOR…")
        if st.button("🚀 Go to Dashboard", type="primary"):
            st.session_state.pop("_wizard_key_saved", None)
            st.cache_data.clear()
            st.rerun()
        st.stop()

    st.markdown(
        "<sub>Need help? See the project README or open an issue on GitHub.</sub>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    return True