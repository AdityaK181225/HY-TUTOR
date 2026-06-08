"""
HY-TUTOR: First-Run Wizard
===========================
Renders a small Streamlit panel if the app is launched without a configured
GEMINI_API_KEY. The wizard writes the key to ``config/.env`` and tells the
user to refresh the page.

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


def _has_raw_sources() -> bool:
    """True if the user has uploaded at least one source file in any subject."""
    raw = _repo_root() / "data_library" / "raw_sources"
    if not raw.exists():
        return False
    for subject_dir in raw.iterdir():
        if not subject_dir.is_dir():
            continue
        if any(subject_dir.rglob("*")):
            return True
    return False


def maybe_render_first_run_wizard() -> bool:
    """Render the wizard if needed.

    Returns:
        True if the wizard was shown (caller should ``st.stop()``),
        False if everything is configured and the app should render normally.
    """
    existing_key = _read_existing_key()
    has_sources = _has_raw_sources()
    needs_key = not existing_key

    if not needs_key and has_sources:
        # Everything is set up — let the app render normally.
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
        .hytutor-wizard-step {
            padding: 0.8rem 1rem;
            margin: 0.6rem 0;
            border-radius: 10px;
            background: #FFFCF1;
            border-left: 4px solid #C8A24A;
        }
    </style>
    """
    st.markdown(_css, unsafe_allow_html=True)
    st.markdown('<div class="hytutor-wizard-wrap">', unsafe_allow_html=True)

    st.markdown("# " + icon("rocket_launch", size=28) + "  Welcome to HY-TUTOR", unsafe_allow_html=False)
    st.markdown(
        "Let's get you set up. You only need to do this once — your settings "
        "will be saved to `config/.env`."
    )

    # --- Step 1: API key ----------------------------------------------------
    if needs_key:
        st.markdown("### Step 1 — Add your Gemini API key")
        st.markdown(
            "HY-TUTOR uses Google's Gemini API to compile lessons and tutor you. "
            "Grab a free key from "
            "[Google AI Studio](https://aistudio.google.com/app/apikey) and "
            "paste it below."
        )
        with st.form("hytutor_first_run_key_form", clear_on_submit=False):
            api_key = st.text_input(
                "GEMINI_API_KEY",
                type="password",
                placeholder="AIza...",
                help="The key looks like AIzaSy... (39 characters). It's stored locally in config/.env with mode 600.",
            )
            submitted = st.form_submit_button("Save and continue", type="primary", use_container_width=True)

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
                        st.success(f"✅ {msg}. Refreshing the page…")
                        # Tell the user (and the caller) to reload.
                        st.info(
                            "The key is saved. **Click the button below to "
                            "restart HY-TUTOR with the new settings.**"
                        )
                        if st.button("🔄 Restart HY-TUTOR"):
                            st.cache_data.clear()
                            st.rerun()
                        st.stop()
                    else:
                        st.error(msg)
    else:
        st.markdown("### Step 1 — ✅ Gemini API key configured")
        with st.expander("Change the API key"):
            with st.form("hytutor_change_key_form"):
                new_key = st.text_input("New GEMINI_API_KEY", type="password", placeholder="AIza...")
                if st.form_submit_button("Update key"):
                    if not _GEMINI_KEY_RE.match(new_key.strip()):
                        st.error("That doesn't look like a valid Gemini key.")
                    else:
                        ok, msg = _save_key(new_key.strip())
                        if ok:
                            st.success(f"✅ {msg}. Restart HY-TUTOR to apply.")
                            if st.button("🔄 Restart HY-TUTOR"):
                                st.rerun()
                        else:
                            st.error(msg)

    # --- Step 2: Source materials hint --------------------------------------
    st.markdown("### Step 2 — Upload syllabus materials (next)")
    if has_sources:
        st.markdown("✅ Source materials detected in `data_library/raw_sources/`.")
    else:
        st.markdown(
            '<div class="hytutor-wizard-step">'
            "After this setup screen, HY-TUTOR will ask you to upload your "
            "syllabus files (CBSE guidelines, NCERT TOC, reference book TOC, "
            "and exemplar question bank) for each subject you want to study. "
            "You can use `.md` or `.txt` exports."
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        "<sub>Need help? See the project README or open an issue on GitHub.</sub>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    # If the key is set but the user hasn't yet, we still render the wizard
    # so they can see the source-uploads hint. Caller should st.stop() so the
    # main app doesn't run with a half-configured state.
    return True
