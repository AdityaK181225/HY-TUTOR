"""
HY-TUTOR: Settings Panel (settings_panel.py)
The gear-icon popover in the top-right of the app. Six tabs:
    1. AI & Models       (interface only, backend integration pending)
    2. Usage & Monitoring
    3. Appearance         (theme radio: dark mode marked "coming soon")
    4. Files & Storage
    5. Behavior
    6. About & Diagnostics (with Updates subsection + export/import)

Persistence: live state mirrored to
    data_library/active_workspace/user_settings.json
so the popover survives F5 refreshes. Defaults come from
    config/user_settings.defaults.json
"""

import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st


# ============================================================================
# PATHS
# ============================================================================

def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


DEFAULTS_PATH = _project_root() / "config" / "user_settings.defaults.json"
USER_SETTINGS_PATH = _project_root() / "data_library" / "active_workspace" / "user_settings.json"

# Ensure core_pipeline is importable (cached at module level)
_CORE_PIPELINE_PATH = str(_project_root() / "core_pipeline")
if _CORE_PIPELINE_PATH not in sys.path:
    sys.path.insert(0, _CORE_PIPELINE_PATH)


# ============================================================================
# PERSISTENCE
# ============================================================================

def _ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def load_settings() -> Dict[str, Any]:
    defaults = _load_defaults()
    if not USER_SETTINGS_PATH.exists():
        return defaults
    try:
        with open(USER_SETTINGS_PATH, "r", encoding="utf-8") as f:
            user = json.load(f)
    except Exception:
        return defaults
    return _deep_merge(defaults, user)


def save_settings(settings: Dict[str, Any]) -> bool:
    try:
        _ensure_dir(USER_SETTINGS_PATH)
        payload = dict(settings)
        payload["last_modified"] = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        with open(USER_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.warning(f"Could not save settings: {e}")
        return False


def _load_defaults() -> Dict[str, Any]:
    if not DEFAULTS_PATH.exists():
        return {}
    try:
        with open(DEFAULTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _deep_merge(defaults: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(defaults)
    for k, v in (overrides or {}).items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def reset_settings_to_defaults() -> bool:
    try:
        if USER_SETTINGS_PATH.exists():
            USER_SETTINGS_PATH.unlink()
        return True
    except Exception:
        return False


def export_settings_bytes() -> bytes:
    return json.dumps(load_settings(), indent=2, ensure_ascii=False).encode("utf-8")


def import_settings_bytes(raw: bytes) -> bool:
    try:
        parsed = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
    except Exception:
        return False
    if not isinstance(parsed, dict):
        return False
    merged = _deep_merge(_load_defaults(), parsed)
    return save_settings(merged)


# ============================================================================
# DYNAMIC CSS (font-scale, accent, magnification, density)
# ============================================================================

_FONT_SIZE_MAP = {
    "small": 14,
    "medium": 16,
    "large": 18,
    "extra_large": 20,
}

_DENSITY_PADDING = {
    "comfortable": "0.65rem 1rem",
    "compact": "0.35rem 0.7rem",
}


def build_dynamic_css(settings: Dict[str, Any]) -> str:
    """Produce the per-user CSS overrides. Mounted via st.markdown unsafe_html."""
    app = settings.get("appearance", {}) or {}
    font_size_px = _FONT_SIZE_MAP.get(app.get("font_size", "medium"), 16)
    font_family = app.get("font_family", "Georgia")
    code_font = app.get("code_font_family", "Fira Code")
    density = app.get("ui_density", "comfortable")
    accent = app.get("accent_color", "#2C4A7C")
    bg_color = app.get("background_color", "#FAF8F5")
    box_color = app.get("box_color", "#FFFFFF")
    box_border = app.get("box_border_color", "#C8D0DC")
    # New customisation keys (added in this revision). Each value is
    # normalised so a malformed entry (e.g. the user hand-edited the JSON)
    # silently falls back to the default rather than breaking the CSS.
    button_color = _normalize_hex(app.get("button_color", "#2C4A7C"), "#2C4A7C")
    sidebar_color = _normalize_hex(app.get("sidebar_color", "#1B2A4A"), "#1B2A4A")
    text_color = _normalize_hex(app.get("text_color", "#1A1A2E"), "#1A1A2E")
    text_color_enabled = bool(app.get("text_color_enabled", False))
    reduce_motion = bool(app.get("reduce_motion", False))
    high_contrast = bool(app.get("high_contrast_borders", False))
    mag_pct = int(app.get("magnification_pct", 100) or 100)
    mag_scale = max(0.5, min(2.0, mag_pct / 100.0))
    border_w = "2px" if high_contrast else "1px"
    motion_css = ""
    if reduce_motion:
        motion_css = "* { transition: none !important; animation: none !important; }\n"

    # Derived colours: button border is a 12% darker variant of the button
    # fill, sidebar border is 8% darker, and sidebar text auto-flips between
    # white and near-black based on the sidebar luminance so the nav stays
    # legible regardless of which preset the user picks.
    button_border = _darken_hex(button_color, 0.12) or accent
    sidebar_border = _darken_hex(sidebar_color, 0.08) or accent

    def _hex_to_luminance(hex_str: str) -> float:
        h = hex_str.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        try:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        except Exception:
            return 1.0
        def _ch(c):
            c = c / 255.0
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * _ch(r) + 0.7152 * _ch(g) + 0.0722 * _ch(b)

    # Auto-derive readable text color for the page background. If the
    # chosen background is dark (luminance < 0.5), we flip the global
    # `text-main` to white so text remains legible without the user
    # having to configure two settings. If the user has explicitly
    # enabled the manual override (`text_color_enabled = True`), their
    # picked `text_color` wins.
    is_dark_bg = _hex_to_luminance(bg_color) < 0.5
    if text_color_enabled:
        text_main_override = text_color
        # Pick a sensible secondary: slightly transparent variant via
        # luminance mirror, or just stay with the auto-derived secondary
        # if the user is overriding main text.
        text_secondary_override = "#A0AEC0" if is_dark_bg else "#4A5568"
    else:
        text_main_override = "#F0F2F5" if is_dark_bg else "#1A1A2E"
        text_secondary_override = "#A0AEC0" if is_dark_bg else "#4A5568"
    sidebar_text_color = "#F0F2F5" if _hex_to_luminance(sidebar_color) < 0.5 else "#1A1A2E"

    css = []
    css.append("<style id=\"hytutor-dynamic\">")
    # Re-declare both the dynamic override tokens AND the main design
    # tokens so that any rule in the main stylesheet that uses
    # `var(--paper-bg)` / `var(--white-surface)` / `var(--steel-muted)`
    # automatically picks up the new user-selected values.
    css.append(
        f":root {{ "
        f"--hytutor-font-size: {font_size_px}px; "
        f"--hytutor-accent: {accent}; "
        f"--hytutor-border-width: {border_w}; "
        f"--hytutor-bg: {bg_color}; "
        f"--hytutor-box-bg: {box_color}; "
        f"--hytutor-box-border: {box_border}; "
        f"--hytutor-text-main: {text_main_override}; "
        f"--hytutor-text-secondary: {text_secondary_override}; "
        f"--hytutor-button-bg: {button_color}; "
        f"--hytutor-button-border: {button_border}; "
        f"--hytutor-sidebar-bg: {sidebar_color}; "
        f"--hytutor-sidebar-border: {sidebar_border}; "
        f"--hytutor-sidebar-text: {sidebar_text_color}; "
        f"--paper-bg: {bg_color}; "
        f"--white-surface: {box_color}; "
        f"--steel-muted: {box_border}; "
        f"--text-main: {text_main_override}; "
        f"--text-secondary: {text_secondary_override}; "
        f"}}"
    )
    css.append(
        f".stApp {{ font-size: var(--hytutor-font-size) !important; "
        f"transform: scale({mag_scale}); transform-origin: top left; "
        f"width: {100.0 / mag_scale:.4f}%; "
        f"background-color: {bg_color} !important; "
        f"color: {text_main_override} !important; "
        f"}}"
    )
    css.append(
        f".stApp p, .stApp li, .stApp label, .stApp span, .stApp div "
        f"{{ font-family: '{font_family}', 'Palatino Linotype', serif !important; "
        f"color: var(--text-main) !important; }}"
    )
    css.append(
        f".stApp code, .stApp pre "
        f"{{ font-family: '{code_font}', 'Fira Code', 'Consolas', monospace !important; }}"
    )
    # Apply background to the main content area (the wide element to the
    # right of the sidebar). This is what the user actually sees as the
    # "dashboard background".
    css.append(
        f".stApp [data-testid=\"stAppViewContainer\"] > .main "
        f"{{ background-color: {bg_color} !important; }}"
    )
    css.append(
        f".stApp section.main, .stApp .block-container "
        f"{{ background-color: transparent !important; }}"
    )
    # Apply box/card color to all "card" surfaces.
    css.append(
        f"div[data-testid=\"stVerticalBlock\"] > div > div[data-testid=\"stVerticalBlockBorderWrapper\"] "
        f"{{ background-color: {box_color} !important; "
        f"border-color: {box_border} !important; }}"
    )
    css.append(
        f"div[data-testid=\"stForm\"] "
        f"{{ background-color: {box_color} !important; "
        f"border-color: {box_border} !important; }}"
    )
    css.append(
        f"div[data-testid=\"stExpander\"] "
        f"{{ background-color: {box_color} !important; "
        f"border-color: {box_border} !important; "
        f"border-left: 4px solid var(--hytutor-accent) !important; "
        f"border-width: var(--hytutor-border-width) !important; }}"
    )
    css.append(
        f"div[data-testid=\"stAlert\"] "
        f"{{ background-color: {box_color} !important; }}"
    )
    # .stButton > button accent border (use box_border instead of steel)
    css.append(
        f".stButton > button "
        f"{{ border-color: var(--hytutor-accent) !important; "
        f"padding: {_DENSITY_PADDING.get(density, '0.5rem 1rem')} !important; }}"
    )
    css.append(
        f".stApp div[data-testid=\"stAlert\"] "
        f"{{ border-left: 4px solid var(--hytutor-accent) !important; }}"
    )
    # metric-tile uses the user-selected box color + box border
    css.append(
        f".metric-tile "
        f"{{ background-color: {box_color} !important; "
        f"border: var(--hytutor-border-width) solid {box_border} !important; "
        f"border-left: 4px solid var(--hytutor-accent) !important; "
        f"border-radius: 10px; padding: 14px 16px; margin-bottom: 10px; "
        f"box-shadow: 0 1px 3px rgba(0,0,0,0.06); }}"
    )
    css.append(".metric-tile .label { font-size: 0.78rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.6px; font-weight: 600; }")
    css.append(".metric-tile .value { font-size: 1.6rem; color: var(--hytutor-text-main); font-weight: 700; margin-top: 4px; }")
    css.append(".metric-tile .sub { font-size: 0.78rem; color: var(--text-secondary); margin-top: 2px; }")
    css.append(".coming-soon-banner { background-color: #FFF9E6; border: 1px solid #F0E4B8; border-left: 4px solid #D4A843; color: #6B4F12; border-radius: 8px; padding: 10px 14px; font-size: 0.85rem; margin: 8px 0 12px 0; }")
    css.append(".coming-soon-badge { display: inline-block; background-color: #D4A843; color: #1A1A2E; font-size: 0.68rem; font-weight: 700; padding: 2px 8px; border-radius: 10px; margin-left: 8px; letter-spacing: 0.4px; text-transform: uppercase; vertical-align: middle; }")
    css.append(".muted-small { font-size: 0.78rem; color: var(--text-secondary); }")
    css.append(f".kbd {{ display: inline-block; padding: 1px 6px; background-color: {box_color}; border: 1px solid {box_border}; border-radius: 4px; font-family: monospace; font-size: 0.8rem; }}")
    css.append(".update-badge { display: inline-block; padding: 4px 12px; border-radius: 12px; font-weight: 700; font-size: 0.78rem; letter-spacing: 0.6px; text-transform: uppercase; }")
    css.append(motion_css)
    css.append("</style>")
    return "\n".join(css)



# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def render_settings_popover() -> None:
    """Render the gear-icon popover for the top bar."""
    if "hytutor_settings" not in st.session_state:
        st.session_state["hytutor_settings"] = load_settings()
    with st.popover("\u2699\ufe0f Settings", help="Open HY-TUTOR settings"):
        _render_popover_body()


def _render_popover_body() -> None:
    settings = st.session_state["hytutor_settings"]
    tabs = st.tabs([
        "\U0001F9E0 AI & Models",
        "\U0001F4CA Usage",
        "\U0001F3A8 Appearance",
        "\U0001F4C1 Files",
        "\u2699\ufe0f Behavior",
        "\u2139\ufe0f About",
    ])
    with tabs[0]:
        _render_ai_tab(settings)
    with tabs[1]:
        _render_usage_tab(settings)
    with tabs[2]:
        _render_appearance_tab(settings)
    with tabs[3]:
        _render_files_tab(settings)
    with tabs[4]:
        _render_behavior_tab(settings)
    with tabs[5]:
        _render_about_tab(settings)

    st.markdown("---")
    cols = st.columns(3)
    with cols[0]:
        if st.button("\U0001F4BE Save", key="settings_save", width='stretch'):
            if save_settings(settings):
                st.toast("Settings saved.", icon="\u2705")
            else:
                st.error("Save failed.")
    with cols[1]:
        if st.button("\U0001F504 Reload", key="settings_reload", width='stretch'):
            st.session_state["hytutor_settings"] = load_settings()
            st.rerun()
    with cols[2]:
        if st.button("\u26A0\ufe0f Reset", key="settings_reset", width='stretch'):
            if reset_settings_to_defaults():
                st.session_state["hytutor_settings"] = load_settings()
                st.toast("Settings reset to defaults.", icon="\u26A0\ufe0f")
                st.rerun()


# ============================================================================
# TAB 1: AI & MODELS (interface only \u2014 backend integration coming soon)
# ============================================================================

_MODEL_OPTIONS = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemma-4-31b-it",
    "gemma-4-26b-a4b-it",
]

_PROVIDER_OPTIONS = ["google_gemini", "openai_compatible", "ollama_local"]
_PERSONA_OPTIONS = ["socratic", "encouraging_coach", "strict_examiner", "concise_hint"]
_COMMAND_NAMES = [
    "command_0_syllabus", "command_0_1_editor", "command_0_5_router",
    "command_1_blueprint", "command_2_miner", "command_3_optimizer",
    "command_4_bridge", "command_5_forge", "command_5_5_injector",
    "command_6_tutor", "command_7_ledger",
]


def _render_ai_tab(settings: Dict[str, Any]) -> None:
    st.markdown("### AI & Models")
    st.markdown(
        '<div class="coming-soon-banner">\U0001F6A7 <b>Coming soon</b> \u2014 the controls below are '
        'wired into the UI but the backend integration is pending. They are disabled until then.</div>',
        unsafe_allow_html=True,
    )
    ai = settings.setdefault("ai_models", {})

    cur_provider = ai.get("api_provider", "google_gemini")
    if cur_provider not in _PROVIDER_OPTIONS:
        cur_provider = "google_gemini"
    st.selectbox(
        "API provider",
        options=_PROVIDER_OPTIONS,
        index=_PROVIDER_OPTIONS.index(cur_provider),
        disabled=True,
        help="Currently locked to Google Gemini. Other providers will be enabled in a future update.",
        key="ai_provider",
    )

    # --- API Key Input ---
    env_path = _project_root() / "config" / ".env"
    current_key = ""
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("GEMINI_API_KEY=") and len(line) > len("GEMINI_API_KEY="):
                    current_key = line[len("GEMINI_API_KEY="):]
                    break
        except Exception:
            pass

    api_key_col1, api_key_col2 = st.columns([3, 1])
    with api_key_col1:
        new_key = st.text_input(
            "Gemini API Key",
            value=current_key,
            type="password",
            help="Get yours at https://aistudio.google.com/app/apikey",
            key="ai_api_key_input",
            placeholder="Paste your Gemini API key here…",
        )
    with api_key_col2:
        st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
        save_key_clicked = st.button(
            "\U0001F4BE Save Key",
            key="ai_save_api_key",
            use_container_width=True,
        )

    if save_key_clicked:
        if not new_key or not new_key.strip():
            st.error("API key cannot be empty.")
        else:
            try:
                if env_path.exists():
                    lines = env_path.read_text(encoding="utf-8").splitlines()
                else:
                    env_path.parent.mkdir(parents=True, exist_ok=True)
                    lines = ["# HY-TUTOR Environment Variables"]

                updated = False
                for i, line in enumerate(lines):
                    if line.strip().startswith("GEMINI_API_KEY="):
                        lines[i] = f"GEMINI_API_KEY={new_key.strip()}"
                        updated = True
                        break
                if not updated:
                    lines.append(f"\nGEMINI_API_KEY={new_key.strip()}")

                env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                st.toast("API key saved successfully!", icon="\u2705")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to save API key: {exc}")

    # Status indicator
    if current_key:
        masked = current_key[:4] + "…" + current_key[-3:] if len(current_key) > 8 else "••••••••"
        st.success(f"\u2705 API key configured: {masked}")
    else:
        st.warning("\u26A0\ufe0f No API key configured. Paste your key above and click Save.")

    st.markdown("---")

    cur_model = ai.get("default_model", "gemini-3.5-flash")
    if cur_model not in _MODEL_OPTIONS:
        cur_model = "gemini-3.5-flash"
    st.selectbox(
        "Default model",
        options=_MODEL_OPTIONS,
        index=_MODEL_OPTIONS.index(cur_model),
        disabled=True,
        key="ai_default_model",
    )

    st.markdown("**Per-command model overrides**")
    overrides = ai.setdefault("per_command_overrides", {})
    for c in _COMMAND_NAMES:
        st.selectbox(
            f"  {c}",
            options=["(use default)"] + _MODEL_OPTIONS,
            index=0,
            disabled=True,
            key=f"ai_override_{c}",
        )

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.slider(
            "Max retries per model",
            min_value=1, max_value=5,
            value=int(ai.get("max_retries", 3)),
            disabled=True,
            key="ai_max_retries",
        )
    with col2:
        st.slider(
            "Timeout per call (sec)",
            min_value=30, max_value=300, step=10,
            value=int(ai.get("timeout_per_call", 60)),
            disabled=True,
            key="ai_timeout",
        )

    st.text_input(
        "Local Ollama model",
        value=ai.get("ollama_model", "gemma4:e2b"),
        disabled=True,
        key="ai_ollama_model",
        help="Used as a local fallback when cloud APIs are unavailable.",
    )

    cur_persona = ai.get("tutor_persona", "socratic")
    if cur_persona not in _PERSONA_OPTIONS:
        cur_persona = "socratic"
    st.selectbox(
        "Tutor persona",
        options=_PERSONA_OPTIONS,
        index=_PERSONA_OPTIONS.index(cur_persona),
        disabled=True,
        key="ai_tutor_persona",
    )

    with st.expander("\U0001F4D6 Show fallback chain", expanded=False):
        chain = {
            "command_0_syllabus":   ["gemini-3.5-flash", "gemma-4-31b-it", "gemini-3.1-flash-lite"],
            "command_6_tutor":      ["gemma-4-31b-it", "gemma-4-26b-a4b-it", "gemini-3.1-flash-lite"],
            "command_7_ledger":     ["gemma-4-31b-it", "gemma-4-26b-a4b-it", "gemini-3.1-flash-lite"],
            "command_2_miner":      ["gemini-3.1-flash-lite", "gemma-4-26b-a4b-it", "gemini-3.5-flash"],
            "command_0_5_router":   ["gemma-4-31b-it", "gemma-4-26b-a4b-it", "gemini-3.1-flash-lite"],
        }
        st.code(json.dumps(chain, indent=2), language="json")

    if st.button("\U0001F9EA Test connection", key="ai_test_conn", disabled=True, width='stretch'):
        pass


# ============================================================================
# TAB 2: USAGE & MONITORING
# ============================================================================

def _render_usage_tab(settings: Dict[str, Any]) -> None:
    st.markdown("### Usage & Monitoring")
    try:
        from utils.usage_tracker import get_summary, reset_log, USAGE_LOG_PATH
    except Exception as e:
        st.error(f"Usage tracker unavailable: {e}")
        return

    usage_settings = settings.setdefault("usage", {})
    if "reset_at" not in usage_settings:
        usage_settings["reset_at"] = None

    summary = get_summary(reset_at_iso=usage_settings.get("reset_at"))

    exact_pct = summary.get("exact_token_pct", 0.0)
    cost_label = "exact" if exact_pct == 100 else "approx."

    cols = st.columns(5)
    metrics_top = [
        ("Total API calls", f"{summary['total_calls']:,}", ""),
        ("Successful", f"{summary['success_calls']:,}", ""),
        ("Failed", f"{summary['failed_calls']:,}", ""),
        ("Est. cost (USD)", f"${summary['estimated_cost_usd']:.4f}", cost_label),
        ("Avg latency", f"{summary.get('avg_latency_ms', 0):.0f}ms", "per call"),
    ]
    for col, (label, val, sub) in zip(cols, metrics_top):
        with col:
            st.markdown(
                f'<div class="metric-tile"><div class="label">{label}</div>'
                f'<div class="value">{val}</div><div class="sub">{sub}</div></div>',
                unsafe_allow_html=True,
            )

    token_label = f"{exact_pct:.0f}% exact" if exact_pct > 0 else "estimated"

    cols2 = st.columns(3)
    metrics_mid = [
        ("Input tokens", f"{summary['total_input_tokens']:,}", token_label),
        ("Output tokens", f"{summary['total_output_tokens']:,}", token_label),
        ("Token accuracy", f"{exact_pct:.1f}%", "exact vs estimated"),
    ]
    for col, (label, val, sub) in zip(cols2, metrics_mid):
        with col:
            st.markdown(
                f'<div class="metric-tile"><div class="label">{label}</div>'
                f'<div class="value">{val}</div><div class="sub">{sub}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("#### \U0001F4C8 Calls per day (last 14 days)")
    # Only render the chart if there is *non-zero* call data. An empty or
    # all-zero series, combined with the popover being lazily rendered
    # (i.e. width 0 on first paint), causes Vega-Lite to emit three console
    # WARN lines on every render of this tab:
    #   * "WARN Infinite extent for field "count_start": [Infinity, -Infinity]"
    #   * "WARN Infinite extent for field "count_end":   [Infinity, -Infinity]"
    #   * "WARN Scale bindings are currently only supported for scales with
    #      unbinned, continuous domains."
    # These are auto-injected by Vega-Lite 6.x for the y-axis range params
    # when the chart is rendered with an empty extent. The cleanest fix is
    # to skip rendering entirely when there is nothing to plot; the user
    # will see a friendly caption instead of a zero-bar chart AND the
    # browser console stays clean.
    # Use a button-gated session flag so the chart's Python code (including
    # the `st.vega_lite_chart()` call) is NEVER executed on initial render.
    # Streamlit pre-renders all children of `st.popover` / `st.expander`
    # even when collapsed, which causes Vega-Embed to process the chart at
    # width=0 and emit "Infinite extent for field 'count_start/count_end'"
    # warnings. By keeping the chart behind a `st.button` + session_state
    # gate, the chart is only mounted to the DOM when the user explicitly
    # requests it, at which point the container already has its real width.
    _show_chart_key = "_usage_show_chart"
    if _show_chart_key not in st.session_state:
        st.session_state[_show_chart_key] = False
    has_chart_data = bool(summary["calls_per_day"]) and any(
        int(d.get("count", 0)) > 0 for d in summary["calls_per_day"]
    )
    if not st.session_state[_show_chart_key]:
        if has_chart_data:
            if st.button("\U0001F4C8 Show daily chart", key="usage_chart_btn", type="secondary"):
                st.session_state[_show_chart_key] = True
                st.rerun()
        else:
            st.caption("No call data yet \u2014 chart will appear after the first API call.")
    else:
        # Hide button so the user can collapse the chart back to its
        # button-only state (the chart is initially gated by a button to
        # avoid Vega-Embed's "Infinite extent" warnings during the popover's
        # first paint at width=0).
        hide_cols = st.columns([6, 1])
        with hide_cols[1]:
            if st.button("\u2715 Hide", key="usage_chart_hide", type="secondary", width='stretch'):
                st.session_state[_show_chart_key] = False
                st.rerun()
        try:
            import pandas as pd

            df = pd.DataFrame(summary["calls_per_day"])
            df["date"] = pd.to_datetime(df["date"])
            df["date_label"] = df["date"].dt.strftime("%b %d")
            records = df[["date_label", "count"]].to_dict(orient="records")

            # Wrap the chart in a *constrained* container so it doesn't
            # stretch across the entire popover width (which can be
            # 600+px and made the bars look "positioned wrongly" — they
            # were clustered to the left with huge gaps). We pin the chart
            # to a fixed sensible width and add a card background to make
            # it visually anchored. Vega-Lite's `width: "container"` was
            # being overridden by st.vega_lite_chart(width=True) which set
            # it to the parent block's width — a width that grew with the
            # popover. We now pass an explicit integer width.
            st.markdown(
                '<div style="width:100%;max-width:560px;margin:6px auto 10px auto;'
                'background-color:#FFFFFF;border:1px solid #C8D0DC;'
                'border-radius:10px;padding:8px 10px 4px 10px;'
                'box-sizing:border-box;">',
                unsafe_allow_html=True,
            )
            # Use three equal columns and put the chart in the centre one
            # so the chart is horizontally centred within the popover and
            # never hugs the left edge. Vega-Lite 6.x is finicky about
            # width: "container" inside a popover, so we pass an explicit
            # integer width that fits well in the centre column.
            chart_cols = st.columns([1, 6, 1])
            with chart_cols[1]:
                spec = {
                    "params": [],
                    "width": 520,
                    "height": 180,
                    "background": "white",
                    "padding": {"top": 8, "right": 10, "bottom": 8, "left": 10},
                    "data": {"values": records},
                    "mark": {
                        "type": "bar",
                        "color": "#6366f1",
                        "cornerRadiusTopLeft": 3,
                        "cornerRadiusTopRight": 3,
                    },
                    "encoding": {
                        "x": {
                            "field": "date_label",
                            "type": "ordinal",
                            "title": None,
                            "axis": {
                                "labelAngle": -45,
                                "grid": False,
                                "tickColor": "#4a4a5a",
                            },
                        },
                        "y": {
                            "field": "count",
                            "type": "quantitative",
                            "title": "Calls",
                            "scale": {"zero": True, "nice": True},
                            "axis": {"tickMinStep": 1, "gridColor": "#2a2a3a"},
                        },
                    },
                    "config": {"view": {"strokeWidth": 0}},
                }
                # Note: do NOT pass `use_container_width=True` to
                # st.vega_lite_chart \u2014 the explicit `"width": 520` in the
                # spec is authoritative. `use_container_width=True` would
                # override the spec width and expand the chart to fill the
                # column, re-introducing the "positioned wrongly"
                # wide-chart bug. (Streamlit \u22651.36 deprecated the old
                # `width=` kwarg in favour of `use_container_width=`.)
                st.vega_lite_chart(spec, use_container_width=False)
            st.markdown("</div>", unsafe_allow_html=True)
        except Exception:
            st.caption("Chart unavailable.")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown("#### \U0001F3AF Model breakdown")
        if summary["model_breakdown"]:
            for row in summary["model_breakdown"][:8]:
                st.progress(min(1.0, row["count"] / max(1, summary["total_calls"])),
                            text=f"{row['model']}: {row['count']}")
        else:
            st.caption("No model data yet.")

    with col_b:
        st.markdown("#### \U0001F4CB Command breakdown")
        if summary["command_breakdown"]:
            for row in summary["command_breakdown"][:8]:
                st.progress(min(1.0, row["count"] / max(1, summary["total_calls"])),
                            text=f"{row['command']}: {row['count']}")
        else:
            st.caption("No command data yet.")

    with col_c:
        st.markdown("#### \U0001F310 Provider breakdown")
        if summary.get("provider_breakdown"):
            for row in summary["provider_breakdown"][:8]:
                st.progress(min(1.0, row["count"] / max(1, summary["total_calls"])),
                            text=f"{row['provider']}: {row['count']}")
        else:
            st.caption("No provider data yet.")

    # --- Token source breakdown (exact vs estimated) ---
    ts_data = {row["source"]: row["count"] for row in summary.get("token_source_breakdown", [])}
    if ts_data:
        st.markdown("#### \U0001F4CA Token source breakdown")
        ts_cols = st.columns(2)
        with ts_cols[0]:
            exact_n = ts_data.get("exact", 0)
            est_n = ts_data.get("estimated", 0)
            total_calls = max(exact_n + est_n, 1)
            st.progress(min(1.0, exact_n / total_calls), text=f"\u2705 Exact: {exact_n}")
        with ts_cols[1]:
            st.progress(min(1.0, est_n / total_calls), text=f"\u23F3 Estimated: {est_n}")

    # --- Per-provider cost & token detail ---
    ptb = summary.get("provider_token_breakdown", [])
    if ptb:
        with st.expander("\U0001F4B0 Provider cost & token breakdown", expanded=False):
            for row in ptb:
                prov = row["provider"]
                in_tok = row.get("input_tokens", 0)
                out_tok = row.get("output_tokens", 0)
                cost_val = row.get("cost_usd", 0.0)
                cnt = row.get("count", 0)
                st.markdown(
                    f"**{prov}** \u00B7 {cnt} calls \u00B7 "
                    f"in: {in_tok:,} / out: {out_tok:,} tokens \u00B7 "
                    f"${cost_val:.6f}"
                )

    # --- Per-API-key breakdown ---
    akb = summary.get("api_key_breakdown", [])
    if akb:
        with st.expander("\U0001F511 API key breakdown", expanded=False):
            for row in akb:
                kid = row.get("api_key_id", "unknown")
                prov = row.get("provider", "unknown")
                cnt = row.get("count", 0)
                in_tok = row.get("input_tokens", 0)
                out_tok = row.get("output_tokens", 0)
                cost_val = row.get("cost_usd", 0.0)
                st.markdown(
                    f"**{kid}** [{prov}] \u00B7 {cnt} calls \u00B7 "
                    f"in: {in_tok:,} / out: {out_tok:,} tokens \u00B7 "
                    f"${cost_val:.6f}"
                )

    with st.expander("\U0001F4DC Recent call log (last 20)", expanded=False):
        if not summary["recent_calls"]:
            st.caption("Log is empty.")
        for r in summary["recent_calls"]:
            status_icon = "\u2705" if r.get("status") == "success" else "\u274C"
            raw_ts = r.get("ts", "")
            try:
                dt = datetime.fromisoformat(raw_ts.rstrip("Z"))
                display_ts = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                display_ts = raw_ts if raw_ts else "?"
            token_src = r.get("token_source", "estimated")
            src_badge = "\u2705 exact" if token_src == "exact" else "\u23F3 estimated"
            provider = r.get("provider", "")
            prov_tag = f" [{provider}]" if provider and provider != "unknown" else ""
            in_tok = r.get("input_tokens", 0)
            out_tok = r.get("output_tokens", 0)
            tok_tag = f" \u00B7 in:{in_tok:,} out:{out_tok:,}" if (in_tok or out_tok) else ""
            line = (
                f"`{display_ts}` {status_icon} **{r.get('command','?')}** "
                f"\u2192 `{r.get('model','?')}`{prov_tag} \u00B7 "
                f"{r.get('duration_ms',0)}ms{tok_tag} \u00B7 {src_badge}"
            )
            st.markdown(line)
            if r.get("error"):
                st.caption(f"  error: {r['error'][:120]}")

    st.markdown("---")
    st.caption(f"Log file: `{USAGE_LOG_PATH}`")
    new_track = st.checkbox(
        "Track API calls",
        value=bool(usage_settings.get("track_calls", True)),
        help="When disabled, future calls will not be appended to the log.",
    )
    if new_track != usage_settings.get("track_calls", True):
        usage_settings["track_calls"] = new_track
        st.rerun()
    if usage_settings.get("track_calls", True):
        st.success("\U0001F4CA Tracking is enabled.")
    else:
        st.warning("\u26A0\ufe0F Tracking is paused. Re-enable to resume logging.")

    rcol1, rcol2 = st.columns(2)
    with rcol1:
        if st.button("\u23F9 Reset stats window", key="usage_reset_window", width='stretch'):
            usage_settings["reset_at"] = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
            st.toast("Stats window reset.", icon="\U0001F4CA")
            st.rerun()
    with rcol2:
        if st.button("\U0001F5D1\ufe0F Truncate log file", key="usage_truncate", width='stretch'):
            if reset_log():
                usage_settings["reset_at"] = None
                st.toast("Log file cleared.", icon="\U0001F5D1\ufe0F")
                st.rerun()
            else:
                st.error("Failed to clear log.")


# ============================================================================
# TAB 3: APPEARANCE
# ============================================================================

_FONT_FAMILY_OPTIONS = [
    "Georgia", "Inter", "Merriweather", "Lora",
    "Open Sans", "Roboto", "System default",
]
_CODE_FONT_OPTIONS = [
    "Fira Code", "JetBrains Mono", "Consolas", "Source Code Pro",
]
_FONT_SIZE_OPTIONS = [
    ("small", "Small (14px)"),
    ("medium", "Medium (16px)"),
    ("large", "Large (18px)"),
    ("extra_large", "Extra Large (20px)"),
]
_DENSITY_OPTIONS = ["comfortable", "compact"]
_ACCENT_PRESETS = [
    ("#2C4A7C", "Ink Blue"),
    ("#2D8659", "Forest Green"),
    ("#B5344A", "Burgundy"),
]

# Preset background colors (paper tones)
_BG_PRESETS = [
    ("#FAF8F5", "Warm Paper"),
    ("#F4F1EC", "Parchment"),
    ("#E8EEF5", "Cool Mist"),
    ("#FFFFFF", "Pure White"),
    ("#1B2A4A", "Midnight Ink"),
    ("#0F1626", "Deep Night"),
]

# Preset box/card surface colors
_BOX_PRESETS = [
    ("#FFFFFF", "White"),
    ("#F5F6FA", "Light Gray"),
    ("#E8EEF5", "Pale Blue"),
    ("#F0F4FA", "Soft Slate"),
    ("#1F2C49", "Dark Surface"),
    ("#2A3654", "Twilight"),
]

# Preset box border colors
_BOX_BORDER_PRESETS = [
    ("#C8D0DC", "Steel"),
    ("#A8B2C0", "Slate"),
    ("#7A8AA0", "Graphite"),
    ("#3D5A99", "Ink Bright"),
]

# Preset button colors
_BUTTON_PRESETS = [
    ("#2C4A7C", "Ink Blue"),
    ("#3D5A99", "Ink Bright"),
    ("#2D8659", "Forest Green"),
    ("#B5344A", "Burgundy"),
    ("#1B2A4A", "Deep Navy"),
    ("#4A5568", "Slate"),
]

# Preset sidebar colors
_SIDEBAR_PRESETS = [
    ("#1B2A4A", "Deep Navy"),
    ("#0F1626", "Deep Night"),
    ("#2C4A7C", "Ink Blue"),
    ("#1F2C49", "Dark Surface"),
    ("#3D5A99", "Ink Bright"),
    ("#2A3654", "Twilight"),
]

# Preset text colors (used when the user enables manual text-colour override)
_TEXT_PRESETS = [
    ("#1A1A2E", "Ink Black"),
    ("#FFFFFF", "Pure White"),
    ("#F0F2F5", "Cream"),
    ("#E2E8F0", "Pale Mist"),
    ("#4A5568", "Graphite"),
    ("#2C4A7C", "Ink Blue"),
]


# ============================================================================
# COLOUR HELPERS
# ============================================================================

def _darken_hex(hex_str: str, percent: float) -> str:
    """Darken a `#RRGGBB` or `#RGB` hex by `percent` (0.0–1.0). Returns a
    normalised 6-digit lowercase hex. Falls back to the input string if it
    cannot be parsed."""
    try:
        h = (hex_str or "").lstrip("#").lower()
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) != 6:
            return hex_str
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        factor = max(0.0, min(1.0, 1.0 - float(percent)))
        r = max(0, min(255, int(round(r * factor))))
        g = max(0, min(255, int(round(g * factor))))
        b = max(0, min(255, int(round(b * factor))))
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_str


def _normalize_hex(hex_str: Optional[str], fallback: str) -> str:
    """Return `hex_str` if it parses as a 3- or 6-digit hex prefixed with `#`,
    otherwise return `fallback`. Defends `build_dynamic_css` against
    malformed user settings."""
    if not isinstance(hex_str, str):
        return fallback
    h = hex_str.strip().lower()
    if not h.startswith("#"):
        return fallback
    body = h[1:]
    if len(body) == 3 and all(c in "0123456789abcdef" for c in body):
        return f"#{body[0]*2}{body[1]*2}{body[2]*2}"
    if len(body) == 6 and all(c in "0123456789abcdef" for c in body):
        return f"#{body}"
    return fallback


def _sanitize_key(s: str) -> str:
    """Streamlit widget keys must be simple identifiers. Strip `#` and
    any other characters that could confuse the key parser."""
    out = []
    for c in s:
        if c.isalnum() or c == "_":
            out.append(c)
        else:
            out.append("_")
    return "".join(out)


def _render_color_presets(
    *,
    label: str,
    presets: list,
    current: str,
    setting_key: str,
    state_dict: dict,
    swatch_kind: str = "fill",   # "fill" | "border" | "button" | "sidebar" | "text"
    picker_key: str = "",        # session_state key of the associated color_picker widget
) -> None:
    """Render a grid of clickable color swatches.

    Each preset is shown as a small color swatch (an HTML div filled with
    the preset color) with the name + hex printed below. Clicking the
    associated Streamlit button updates `state_dict[setting_key]` to the
    chosen hex and triggers a rerun so the change is immediately visible.

    `swatch_kind` controls how the swatch is drawn:
      - "fill"    : solid colored rectangle (default — for bg / box)
      - "border"  : rectangle with the color as a thick border + transparent
                    inside (for border color)
      - "button"  : pill shape resembling an actual button
      - "sidebar" : narrow vertical strip resembling a sidebar
      - "text"    : white square with a letter "T" rendered in the picked
                    colour (preview of how the text will read on a card)
    """
    safe_label = _sanitize_key(label)
    st.caption(label)
    n = len(presets)
    cols = st.columns(n)
    for col, (hex_val, name) in zip(cols, presets):
        with col:
            is_active = hex_val.lower() == (current or "").lower()
            border_color = "#1B2A4A" if is_active else "#C8D0DC"
            border_width = "3px" if is_active else "1px"
            # Pick a readable text color for the label underneath the
            # swatch based on the swatch's own luminance.
            def _luma(h: str) -> float:
                hh = h.lstrip("#")
                if len(hh) == 3:
                    hh = "".join(c * 2 for c in hh)
                try:
                    r, g, b = int(hh[0:2], 16), int(hh[2:4], 16), int(hh[4:6], 16)
                except Exception:
                    return 1.0
                def _ch(c):
                    c = c / 255.0
                    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
                return 0.2126 * _ch(r) + 0.7152 * _ch(g) + 0.0722 * _ch(b)
            text_col = "#FFFFFF" if _luma(hex_val) < 0.5 else "#1A1A2E"

            if swatch_kind == "border":
                swatch_inner = (
                    f'<div style="height:28px;border:4px solid {hex_val};'
                    f'border-radius:6px;background-color:#FFFFFF;"></div>'
                )
            elif swatch_kind == "button":
                swatch_inner = (
                    f'<div style="height:28px;border-radius:8px;'
                    f'background-color:{hex_val};color:{text_col};'
                    f'display:flex;align-items:center;justify-content:center;'
                    f'font-size:10px;font-weight:600;">Btn</div>'
                )
            elif swatch_kind == "sidebar":
                swatch_inner = (
                    f'<div style="height:28px;border-radius:4px;'
                    f'background-color:{hex_val};color:{text_col};'
                    f'display:flex;align-items:center;justify-content:center;'
                    f'font-size:10px;font-weight:600;">|||</div>'
                )
            elif swatch_kind == "text":
                # White "card" surface with a letter "T" rendered in the
                # picked colour \u2014 previews how the colour reads against a
                # real card / expander surface (the same #FFFFFF used by
                # `box_color` in light Scholarly Ink).
                swatch_inner = (
                    f'<div style="height:28px;border-radius:6px;'
                    f'background-color:#FFFFFF;color:{hex_val};'
                    f'display:flex;align-items:center;justify-content:center;'
                    f'font-size:14px;font-weight:700;'
                    f'font-family:Georgia,serif;">T</div>'
                )
            else:  # fill
                swatch_inner = (
                    f'<div style="height:28px;border-radius:6px;'
                    f'background-color:{hex_val};color:{text_col};'
                    f'display:flex;align-items:center;justify-content:center;'
                    f'font-size:10px;font-weight:600;">&nbsp;</div>'
                )

            st.markdown(
                f'<div style="border:{border_width} solid {border_color};'
                f'border-radius:8px;padding:3px;background-color:#FFFFFF;">'
                f'{swatch_inner}'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div style="text-align:center;font-size:0.7rem;'
                f'line-height:1.1;margin-top:2px;">'
                f'<b>{name}</b><br/>'
                f'<span style="color:#4A5568;">{hex_val}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            # Streamlit button — sanitized key, no `#`.
            btn_key = f"_hy_preset_{safe_label}_{_sanitize_key(hex_val)}"
            if st.button(
                "Apply",
                key=btn_key,
                width='stretch',
                type="primary" if is_active else "secondary",
            ):
                state_dict[setting_key] = hex_val
                if picker_key:
                    st.session_state.pop(picker_key, None)
                st.rerun()




def _render_appearance_tab(settings: Dict[str, Any]) -> None:
    st.markdown("### Appearance")
    app = settings.setdefault("appearance", {})

    # -----------------------------------------------------------------
    # Section 1: Theme
    # -----------------------------------------------------------------
    st.markdown("#### \U0001F312 Theme")
    cur_theme = app.get("theme", "scholarly_ink")
    st.markdown(
        '<div class="coming-soon-banner">\U0001F6A7 <b>Dark theme is in active development.</b> '
        'The Midnight Library palette is exposed here for visibility but is not yet '
        'selectable. Light Scholarly Ink is the only active theme.</div>',
        unsafe_allow_html=True,
    )
    theme_radio = st.radio(
        "Theme",
        options=["scholarly_ink", "midnight_library", "auto_system"],
        format_func=lambda v: {
            "scholarly_ink": "\u2600\ufe0f  Scholarly Ink (light) \u2014 current",
            "midnight_library": "\U0001F319  Midnight Library (dark) \u2014 coming soon",
            "auto_system": "\U0001F313  Auto (follow system) \u2014 coming soon",
        }[v],
        index=0 if cur_theme not in ("midnight_library", "auto_system") else 0,
        key="appearance_theme_radio",
        disabled=False,
        help="Only Scholarly Ink is active. Dark theme is on the roadmap.",
    )
    # Force store the active value (the disabled options still appear but can't be
    # committed because we always pin to 'scholarly_ink' in storage).
    app["theme"] = "scholarly_ink"
    st.caption(
        '<span class="coming-soon-badge">Coming soon</span> '
        '<span class="muted-small">Midnight Library &amp; Auto are queued for the next minor upgrade.</span>',
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # -----------------------------------------------------------------
    # Section 2: Typography
    # -----------------------------------------------------------------
    st.markdown("#### \U0001F4D6 Typography")

    cur_font = app.get("font_family", "Georgia")
    if cur_font not in _FONT_FAMILY_OPTIONS:
        cur_font = "Georgia"
    new_font = st.selectbox(
        "Font family",
        options=_FONT_FAMILY_OPTIONS,
        index=_FONT_FAMILY_OPTIONS.index(cur_font),
        key="appearance_font_family",
    )
    app["font_family"] = new_font

    cur_code = app.get("code_font_family", "Fira Code")
    if cur_code not in _CODE_FONT_OPTIONS:
        cur_code = "Fira Code"
    new_code = st.selectbox(
        "Code font",
        options=_CODE_FONT_OPTIONS,
        index=_CODE_FONT_OPTIONS.index(cur_code),
        key="appearance_code_font",
    )
    app["code_font_family"] = new_code

    cur_size = app.get("font_size", "medium")
    size_labels = [label for _, label in _FONT_SIZE_OPTIONS]
    size_keys = [key for key, _ in _FONT_SIZE_OPTIONS]
    if cur_size not in size_keys:
        cur_size = "medium"
    seg_cols = st.columns(len(size_keys))
    for col, key, label in zip(seg_cols, size_keys, size_labels):
        with col:
            is_active = (cur_size == key)
            if st.button(
                label,
                key=f"appearance_size_{key}",
                width='stretch',
                type="primary" if is_active else "secondary",
            ):
                app["font_size"] = key
                st.rerun()

    # Live preview
    st.markdown("**Live preview**")
    preview_css = (
        f"font-family: '{new_font}', 'Palatino Linotype', serif; "
        f"font-size: {_FONT_SIZE_MAP.get(app.get('font_size','medium'),16)}px; "
        f"border-left: 4px solid {app.get('accent_color','#2C4A7C')}; "
        f"padding: 8px 14px; background:#FFFFFF; border-radius:6px;"
    )
    st.markdown(
        f'<div style="{preview_css}">The quick brown fox jumps over the lazy dog. '
        f'<code style="font-family:\'{new_code}\', monospace;">x = \\int_0^1 t^2 dt</code></div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # -----------------------------------------------------------------
    # Section 3: Magnification / Zoom
    # -----------------------------------------------------------------
    st.markdown("#### \U0001F50D Magnification / Zoom")
    cur_mag = int(app.get("magnification_pct", 100) or 100)
    new_mag = st.slider(
        "Zoom level",
        min_value=75, max_value=150, step=5,
        value=cur_mag,
        key="appearance_mag",
        help="Scales the entire app interface. 100% = default.",
    )
    app["magnification_pct"] = int(new_mag)
    c1, c2 = st.columns([1, 5])
    with c1:
        if st.button("Reset to 100%", key="appearance_mag_reset", width='stretch'):
            app["magnification_pct"] = 100
            st.rerun()
    with c2:
        st.caption(f"Current scale: **{new_mag}%**")

    st.markdown("---")

    # -----------------------------------------------------------------
    # Section 4: UI Density
    # -----------------------------------------------------------------
    st.markdown("#### \U0001F4D0 UI Density")
    cur_density = app.get("ui_density", "comfortable")
    if cur_density not in _DENSITY_OPTIONS:
        cur_density = "comfortable"
    new_density = st.radio(
        "Density",
        options=_DENSITY_OPTIONS,
        format_func=lambda v: {
            "comfortable": "\u263A\ufe0f  Comfortable (default, more breathing room)",
            "compact":     "\U0001F4E6  Compact (denser, fits more on screen)",
        }[v],
        index=_DENSITY_OPTIONS.index(cur_density),
        key="appearance_density",
        horizontal=True,
    )
    app["ui_density"] = new_density

    st.markdown("---")

    # -----------------------------------------------------------------
    # Section 5: Accent Color
    # -----------------------------------------------------------------
    st.markdown("#### \U0001F3A8 Accent Color")
    cur_accent = app.get("accent_color", "#2C4A7C")
    st.color_picker(
        "Pick an accent color",
        value=cur_accent,
        key="appearance_accent",
        on_change=lambda: app.__setitem__("accent_color", st.session_state.appearance_accent),
    )
    _render_color_presets(
        label="Preset accent colors (one click):",
        presets=_ACCENT_PRESETS,
        current=cur_accent,
        setting_key="accent_color",
        state_dict=app,
        swatch_kind="fill",
        picker_key="appearance_accent",
    )

    st.markdown("---")

    # -----------------------------------------------------------------
    # Section 5b: Background Color
    # -----------------------------------------------------------------
    st.markdown("#### \U0001F5DC\ufe0F Background Color")
    cur_bg = app.get("background_color", "#FAF8F5")
    st.color_picker(
        "Pick a dashboard background color",
        value=cur_bg,
        key="appearance_background",
        help="Sets the page background for the main dashboard area.",
        on_change=lambda: app.__setitem__("background_color", st.session_state.appearance_background),
    )
    _render_color_presets(
        label="Preset background tones (one click):",
        presets=_BG_PRESETS,
        current=cur_bg,
        setting_key="background_color",
        state_dict=app,
        swatch_kind="fill",
        picker_key="appearance_background",
    )

    st.markdown("---")

    # -----------------------------------------------------------------
    # Section 5c: Box / Card Colors
    # -----------------------------------------------------------------
    st.markdown("#### \U0001F4E6 Box / Card Colors")
    st.caption(
        "These control the surface color of cards, expanders, and form panels "
        "across the dashboard."
    )

    cur_box = app.get("box_color", "#FFFFFF")
    st.color_picker(
        "Pick a box / card background color",
        value=cur_box,
        key="appearance_box_color",
        help="Sets the background color of cards, expanders, forms, and metric tiles.",
        on_change=lambda: app.__setitem__("box_color", st.session_state.appearance_box_color),
    )
    _render_color_presets(
        label="Preset surface colors (one click):",
        presets=_BOX_PRESETS,
        current=cur_box,
        setting_key="box_color",
        state_dict=app,
        swatch_kind="fill",
        picker_key="appearance_box_color",
    )

    cur_box_border = app.get("box_border_color", "#C8D0DC")
    st.color_picker(
        "Pick a box / card border color",
        value=cur_box_border,
        key="appearance_box_border_color",
        help="Sets the border color of cards, expanders, and forms.",
        on_change=lambda: app.__setitem__("box_border_color", st.session_state.appearance_box_border_color),
    )
    _render_color_presets(
        label="Preset border colors (one click):",
        presets=_BOX_BORDER_PRESETS,
        current=cur_box_border,
        setting_key="box_border_color",
        state_dict=app,
        swatch_kind="border",
        picker_key="appearance_box_border_color",
    )

    st.markdown("---")

    # -----------------------------------------------------------------
    # Section 5d: Button Color
    # -----------------------------------------------------------------
    st.markdown("#### \U0001F518 Button Color")
    st.caption(
        "Changes the background color of all primary action buttons "
        "(Settings, Run, Save, Apply, etc.)."
    )
    cur_btn = app.get("button_color", "#2C4A7C")
    st.color_picker(
        "Pick a button color",
        value=cur_btn,
        key="appearance_button_color",
        help="Sets the background color of all standard Streamlit buttons.",
        on_change=lambda: app.__setitem__("button_color", st.session_state.appearance_button_color),
    )
    _render_color_presets(
        label="Preset button colors (one click):",
        presets=_BUTTON_PRESETS,
        current=cur_btn,
        setting_key="button_color",
        state_dict=app,
        swatch_kind="button",
        picker_key="appearance_button_color",
    )

    st.markdown("---")

    # -----------------------------------------------------------------
    # Section 5e: Sidebar Color
    # -----------------------------------------------------------------
    st.markdown("#### \U0001F4D2 Sidebar Color")
    st.caption(
        "Changes the background color of the left navigation sidebar."
    )
    cur_sidebar = app.get("sidebar_color", "#1B2A4A")
    st.color_picker(
        "Pick a sidebar background color",
        value=cur_sidebar,
        key="appearance_sidebar_color",
        help="Sets the background color of the left navigation sidebar.",
        on_change=lambda: app.__setitem__("sidebar_color", st.session_state.appearance_sidebar_color),
    )
    _render_color_presets(
        label="Preset sidebar colors (one click):",
        presets=_SIDEBAR_PRESETS,
        current=cur_sidebar,
        setting_key="sidebar_color",
        state_dict=app,
        swatch_kind="sidebar",
        picker_key="appearance_sidebar_color",
    )

    st.markdown("---")

    # -----------------------------------------------------------------
    # Section 5f: Text Color
    # -----------------------------------------------------------------
    # By default the dashboard auto-derives the main text colour from the
    # background luminance (light text on dark backgrounds, dark text on
    # light backgrounds). The toggle below lets the user override that
    # automatic behaviour with an explicit manual pick.
    st.markdown("#### \U0001F524 Text Color")
    st.caption(
        "Automatic mode picks light text for dark backgrounds and dark text for "
        "light backgrounds. Enable the toggle below to override with a manual colour."
    )
    cur_text_enabled = bool(app.get("text_color_enabled", False))
    new_text_enabled = st.toggle(
        "Use custom text colour (override auto-derive)",
        value=cur_text_enabled,
        key="appearance_text_color_enabled",
        help="When OFF (default), the app picks black or white based on background luminance. "
             "When ON, the colour you pick below is used as the main text colour.",
    )
    app["text_color_enabled"] = new_text_enabled
    cur_text = _normalize_hex(app.get("text_color", "#1A1A2E"), "#1A1A2E")
    st.color_picker(
        "Pick a main text colour",
        value=cur_text,
        key="appearance_text_color",
        disabled=not new_text_enabled,
        help="Sets the colour of body text, headings, and labels in the main dashboard area.",
        on_change=lambda: app.__setitem__("text_color", st.session_state.appearance_text_color),
    )
    _render_color_presets(
        label="Preset text colours (one click):",
        presets=_TEXT_PRESETS,
        current=cur_text,
        setting_key="text_color",
        state_dict=app,
        swatch_kind="text",
        picker_key="appearance_text_color",
    )
    if not new_text_enabled:
        st.caption(
            "Currently in **automatic** mode \u2014 the picker above is ignored until "
            "you enable the toggle."
        )

    st.markdown("---")

    # -----------------------------------------------------------------
    # Section 6: Accessibility & Motion
    # -----------------------------------------------------------------
    st.markdown("#### \u267F Accessibility & Motion")

    new_reduce = st.toggle(
        "Reduce motion",
        value=bool(app.get("reduce_motion", False)),
        key="appearance_reduce_motion",
        help="Disables transitions and animations throughout the app.",
    )
    app["reduce_motion"] = new_reduce
    new_contrast = st.toggle(
        "High-contrast borders",
        value=bool(app.get("high_contrast_borders", False)),
        key="appearance_high_contrast",
        help="Thickens and darkens all panel borders for visual clarity.",
    )
    app["high_contrast_borders"] = new_contrast


# ============================================================================
# TAB 4: FILES & STORAGE
# ============================================================================

_FILE_EXTENSIONS = {".json", ".md", ".pdf", ".txt"}


def _dir_size(path: Path) -> int:
    """Return the total size in bytes of a directory tree (no follow symlinks)."""
    total = 0
    if not path.exists():
        return 0
    try:
        for p in path.rglob("*"):
            try:
                if p.is_file():
                    total += p.stat().st_size
            except Exception:
                pass
    except Exception:
        pass
    return total


def _count_files(path: Path, extensions: Optional[set] = None) -> int:
    if not path.exists():
        return 0
    try:
        if extensions is None:
            return sum(1 for _ in path.rglob("*") if _.is_file())
        return sum(1 for _ in path.rglob("*") if _.is_file() and _.suffix.lower() in extensions)
    except Exception:
        return 0


def _human_bytes(n: int) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024.0:
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024.0
    return f"{n:.1f} PB"


def _scan_subject_workspaces() -> List[Dict[str, Any]]:
    """Discover subject workspaces and report their stats."""
    subj_root = _project_root() / "data_library" / "subject_workspaces"
    legacy_root = _project_root() / "data_library" / "active_workspace"
    rows: List[Dict[str, Any]] = []

    seen_subjects: set = set()
    if subj_root.exists():
        for p in sorted(subj_root.iterdir()):
            if not p.is_dir():
                continue
            seen_subjects.add(p.name)
            chunks_dir = p / "active_chunk"
            chapter_cache = p / "chapter_cache"
            rows.append({
                "subject": p.name,
                "workspace": "per-subject",
                "size_bytes": _dir_size(p),
                "chunks_ready": _count_files(chunks_dir, {".md", ".json"}),
                "chapter_files": _count_files(p / "raw_sources" / "ncert_textbooks" / p.name, _FILE_EXTENSIONS),
            })

    if legacy_root.exists() and not seen_subjects:
        rows.append({
            "subject": "(legacy)",
            "workspace": "active_workspace",
            "size_bytes": _dir_size(legacy_root),
            "chunks_ready": _count_files(legacy_root / "active_chunk", {".md", ".json"}),
            "chapter_files": _count_files(legacy_root / "raw_sources" / "ncert_textbooks", _FILE_EXTENSIONS),
        })

    return rows


def _integrity_scan() -> List[Dict[str, str]]:
    """Check that the canonical paths from paths.py all exist."""
    try:
        from utils.paths import (
            PROJECT_ROOT, DATA_LIBRARY, METADATA_DIR,
            SUBJECT_WORKSPACES_DIR, INTERFACE_DIR,
            CONFIG_DIR, get_subject_vector_db, get_current_subject,
            MASTER_SYLLABUS_PATH, ENV_PATH, GLOBAL_TRACKER_PATH,
        )

    except Exception as e:
        return [{"name": "import paths", "path": "(import failed)", "status": "fail", "detail": str(e)}]

    checks = [
        ("Project root", PROJECT_ROOT, "dir"),
        ("config/", CONFIG_DIR, "dir"),
        ("config/.env", ENV_PATH, "file"),
        ("data_library/", DATA_LIBRARY, "dir"),
        ("data_library/metadata/", METADATA_DIR, "dir"),
        ("Master syllabus", MASTER_SYLLABUS_PATH, "file"),
        ("Global tracker", GLOBAL_TRACKER_PATH, "file"),
        ("subject_workspaces/", SUBJECT_WORKSPACES_DIR, "dir"),
        ("interface/", INTERFACE_DIR, "dir"),
        ("vector_db/", get_subject_vector_db(get_current_subject() or "") if get_current_subject() else _project_root() / "data_library" / "vector_db", "dir"),
    ]
    results: List[Dict[str, str]] = []
    for name, p, kind in checks:
        if p.exists():
            actual = "file" if p.is_file() else "dir" if p.is_dir() else "other"
            results.append({
                "name": name,
                "path": str(p.relative_to(_project_root())),
                "status": "ok" if actual == kind else "warn",
                "detail": f"exists as {actual}",
            })
        else:
            results.append({
                "name": name,
                "path": str(p.relative_to(_project_root())),
                "status": "missing",
                "detail": "not found",
            })
    return results


def _render_files_tab(settings: Dict[str, Any]) -> None:
    st.markdown("### Files & Storage")
    fs = settings.setdefault("files_storage", {})
    fs.setdefault("auto_cleanup_on_exit", False)
    fs.setdefault("show_disk_usage_banner", True)

    # -----------------------------------------------------------------
    # Section 1: Disk usage overview
    # -----------------------------------------------------------------
    st.markdown("#### \U0001F4CA Disk Usage Overview")
    buckets = [
        ("data_library",       _project_root() / "data_library"),
        ("chapter_cache",      _project_root() / "chapter_cache"),
        ("config",             _project_root() / "config"),
        ("vector_db",         _project_root() / "data_library" / "vector_db"),
    ]
    sizes: List[Tuple[str, int]] = []
    for name, path in buckets:
        sizes.append((name, _dir_size(path)))
    total_bytes = sum(s for _, s in sizes) or 1
    for name, sz in sizes:
        pct = sz / total_bytes if total_bytes else 0
        st.progress(min(1.0, pct), text=f"{name}: {_human_bytes(sz)} ({pct*100:.1f}%)")
    st.caption(f"Total: **{_human_bytes(total_bytes)}** across {len(buckets)} top-level directories")

    total_files = _count_files(_project_root() / "data_library", _FILE_EXTENSIONS)
    st.markdown(
        f'<div class="metric-tile"><div class="label">Total files in data_library</div>'
        f'<div class="value">{total_files:,}</div>'
        f'<div class="sub">.json, .md, .pdf, .txt</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # -----------------------------------------------------------------
    # Section 2: Subject workspaces
    # -----------------------------------------------------------------
    st.markdown("#### \U0001F4DA Subject Workspaces")
    rows = _scan_subject_workspaces()
    if not rows:
        st.info("No subject workspaces detected yet. Upload materials in the main UI to create one.")
    else:
        try:
            import pandas as pd
            df = pd.DataFrame(rows)
            df["size"] = df["size_bytes"].apply(_human_bytes)
            df = df.drop(columns=["size_bytes"])
            st.dataframe(df, width='stretch', hide_index=True)
        except Exception:
            for r in rows:
                st.markdown(
                    f"**{r['subject']}** &middot; {r['workspace']} &middot; "
                    f"{_human_bytes(r['size_bytes'])} &middot; "
                    f"{r['chunks_ready']} chunks &middot; "
                    f"{r['chapter_files']} chapter files"
                )

    st.markdown("---")

    # -----------------------------------------------------------------
    # Section 3: File integrity scan
    # -----------------------------------------------------------------
    st.markdown("#### \U0001F50D File Integrity Scan")
    if st.button("\u27F3 Run scan", key="files_integrity_run", width='content'):
        st.session_state["_hytutor_integrity_cache"] = _integrity_scan()
    integrity = st.session_state.get("_hytutor_integrity_cache") or _integrity_scan()
    if integrity:
        ok_count = sum(1 for c in integrity if c["status"] == "ok")
        warn_count = sum(1 for c in integrity if c["status"] == "warn")
        miss_count = sum(1 for c in integrity if c["status"] == "missing")
        fail_count = sum(1 for c in integrity if c["status"] == "fail")
        c1, c2, c3, c4 = st.columns(4)
        for col, (label, count) in zip(
            [c1, c2, c3, c4],
            [("OK", ok_count), ("Warnings", warn_count), ("Missing", miss_count), ("Errors", fail_count)],
        ):
            color = {"OK": "#2D8659", "Warnings": "#D4A843", "Missing": "#B5344A", "Errors": "#B5344A"}[label]
            with col:
                st.markdown(
                    f'<div class="metric-tile"><div class="label">{label}</div>'
                    f'<div class="value" style="color:{color};">{count}</div></div>',
                    unsafe_allow_html=True,
                )
        with st.expander("View detailed results", expanded=False):
            for c in integrity:
                icon = {"ok": "\u2705", "warn": "\u26A0\ufe0F", "missing": "\u274C", "fail": "\u274C"}[c["status"]]
                st.markdown(f"{icon} **{c['name']}** &mdash; `{c['path']}` &middot; {c['detail']}")

    st.markdown("---")

    # -----------------------------------------------------------------
    # Section 4: Cleanup actions
    # -----------------------------------------------------------------
    st.markdown("#### \U0001F5D1\ufe0F Cleanup Actions")
    st.caption("Each action requires a confirmation step. The original data is not recoverable after deletion.")

    # Chapter cache
    _render_cleanup_button(
        key="clear_chapter_cache",
        label="\U0001F5D1\ufe0F Clear chapter cache",
        target_path=_project_root() / "chapter_cache",
        confirm_text="delete chapter cache",
        description=f"Deletes all files in `chapter_cache/` "
                    f"({_human_bytes(_dir_size(_project_root() / 'chapter_cache'))} currently).",
    )

    # Vector DB
    _render_cleanup_button(
        key="clear_vector_db",
        label="\U0001F5D1\ufe0F Clear vector DB",
        target_path=_project_root() / "data_library" / "vector_db",
        confirm_text="delete vector db",
        description=f"Deletes the ChromaDB collection "
                    f"({_human_bytes(_dir_size(_project_root() / 'data_library' / 'vector_db'))} currently). "
                    f"Problems will need to be re-indexed.",
    )

    # Active chunk temp
    _render_cleanup_button(
        key="clear_active_chunk",
        label="\U0001F5D1\ufe0F Clear active chunk temp files",
        target_path=_project_root() / "data_library" / "active_workspace" / "active_chunk",
        confirm_text="delete active chunk",
        description="Deletes the per-chunk working files (Unified_Lesson.md, "
                    "NCERT_chunk.json, etc.) from the active chunk dir.",
    )

    # Recovery state
    st.markdown("**Recovery state**")
    if st.button("\U0001F5D1\ufe0F Clear all recovery state", key="files_clear_recovery", width='content'):
        try:
            from utils.recovery import RecoveryManager
            rm = RecoveryManager()
            rm.clear_all()
            st.success("Recovery state cleared.")
        except Exception as e:
            st.error(f"Could not clear recovery: {e}")

    st.markdown("---")

    # -----------------------------------------------------------------
    # Section 5: Storage preferences
    # -----------------------------------------------------------------
    st.markdown("#### \u2699\ufe0F Storage Preferences")
    new_auto = st.toggle(
        "Auto-cleanup on exit (not yet implemented)",
        value=bool(fs.get("auto_cleanup_on_exit", False)),
        key="files_auto_cleanup",
        disabled=True,
        help="When enabled, transient files are removed on app shutdown. "
             "This is reserved for a future release.",
    )
    fs["auto_cleanup_on_exit"] = new_auto
    new_banner = st.toggle(
        "Show disk usage banner on dashboard",
        value=bool(fs.get("show_disk_usage_banner", True)),
        key="files_show_banner",
        help="When enabled, the main UI shows a small banner with current disk usage.",
    )
    fs["show_disk_usage_banner"] = new_banner


def _render_cleanup_button(
    *,
    key: str,
    label: str,
    target_path: Path,
    confirm_text: str,
    description: str,
) -> None:
    """Render a destructive cleanup button with a two-step confirm."""
    confirm_key = f"{key}_confirm"
    armed_key = f"{key}_armed"

    st.markdown(f"**{label}**")
    st.caption(description)

    if st.session_state.get(armed_key):
        st.warning(
            f"\u26A0\ufe0F This will permanently delete everything under "
            f"`{target_path.relative_to(_project_root())}`. Type **{confirm_text}** to confirm."
        )
        user_input = st.text_input("Type to confirm", key=confirm_key, label_visibility="collapsed")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("\u2705 Confirm", key=f"{key}_do", width='stretch'):
                if user_input.strip().lower() == confirm_text.lower():
                    try:
                        if target_path.exists():
                            shutil.rmtree(target_path)
                        st.session_state[armed_key] = False
                        st.toast(f"Cleared `{target_path.name}`.", icon="\U0001F5D1\ufe0F")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Cleanup failed: {e}")
                else:
                    st.error(f"Type exactly: {confirm_text}")
        with cc2:
            if st.button("\u274C Cancel", key=f"{key}_cancel", width='stretch'):
                st.session_state[armed_key] = False
                st.rerun()
    else:
        if st.button(label, key=f"{key}_arm", width='content'):
            st.session_state[armed_key] = True
            st.rerun()


# ============================================================================
# TAB 5: BEHAVIOR
# ============================================================================

_DIFFICULTY_OPTIONS = ["All", "Easy", "Medium", "Hard"]
_RESULTS_OPTIONS = [3, 5, 10]


def _render_behavior_tab(settings: Dict[str, Any]) -> None:
    st.markdown("### Behavior")
    bh = settings.setdefault("behavior", {})

    st.caption("These settings influence how the main UI behaves. Changes take effect on the next rerun.")

    # -----------------------------------------------------------------
    # Section 1: Navigation & flow
    # -----------------------------------------------------------------
    st.markdown("#### \U0001F6E4\ufe0F Navigation & Flow")
    new_auto_advance = st.toggle(
        "Auto-advance to next chunk on mastery",
        value=bool(bh.get("auto_advance_chunk", False)),
        key="behavior_auto_advance",
        help="When enabled, clicking 'Mastered' automatically proceeds to the next chunk without confirmation.",
    )
    bh["auto_advance_chunk"] = new_auto_advance
    new_confirm_rerun = st.toggle(
        "Confirm before pipeline re-run",
        value=bool(bh.get("confirm_before_rerun", True)),
        key="behavior_confirm_rerun",
        help="Show a confirmation prompt before re-running any pipeline command.",
    )
    bh["confirm_before_rerun"] = new_confirm_rerun

    # -----------------------------------------------------------------
    # Section 2: Tooltips & help
    # -----------------------------------------------------------------
    st.markdown("#### \u2753 Tooltips & Help")
    new_tooltips = st.toggle(
        "Show tooltips on buttons",
        value=bool(bh.get("show_button_tooltips", True)),
        key="behavior_tooltips",
        help="When enabled, hovering over buttons displays a short help description.",
    )
    bh["show_button_tooltips"] = new_tooltips
    new_verbose = st.toggle(
        "Verbose pipeline logs",
        value=bool(bh.get("verbose_pipeline_logs", False)),
        key="behavior_verbose",
        help="When enabled, each pipeline command shows its full stdout in an expander.",
    )
    bh["verbose_pipeline_logs"] = new_verbose

    # -----------------------------------------------------------------
    # Section 3: Similar Problems defaults
    # -----------------------------------------------------------------
    st.markdown("#### \U0001F50E Similar Problems Defaults")
    cur_diff = bh.get("default_difficulty_filter", "All")
    if cur_diff not in _DIFFICULTY_OPTIONS:
        cur_diff = "All"
    new_diff = st.selectbox(
        "Default difficulty filter",
        options=_DIFFICULTY_OPTIONS,
        index=_DIFFICULTY_OPTIONS.index(cur_diff),
        key="behavior_diff",
        help="The default filter shown when you open the Similar Problems section.",
    )
    bh["default_difficulty_filter"] = new_diff

    cur_results = int(bh.get("default_results_count", 5))
    if cur_results not in _RESULTS_OPTIONS:
        cur_results = 5
    new_results = st.selectbox(
        "Default result count",
        options=_RESULTS_OPTIONS,
        index=_RESULTS_OPTIONS.index(cur_results),
        key="behavior_results",
        help="How many similar problems to display by default.",
    )
    bh["default_results_count"] = new_results

    # -----------------------------------------------------------------
    # Section 4: Chat & session
    # -----------------------------------------------------------------
    st.markdown("#### \U0001F4AC Chat & Session")
    new_chat_save = st.toggle(
        "Chat auto-save",
        value=bool(bh.get("chat_auto_save", True)),
        key="behavior_chat_save",
        help="Persist the current session's chat history to disk so it survives F5 refreshes.",
    )
    bh["chat_auto_save"] = new_chat_save

    # -----------------------------------------------------------------
    # Section 5: Feedback
    # -----------------------------------------------------------------
    st.markdown("#### \U0001F514 Feedback")
    new_sound = st.toggle(
        "Sound on pipeline completion",
        value=bool(bh.get("sound_on_completion", False)),
        key="behavior_sound",
        help="Play a soft chime when a pipeline command finishes successfully.",
    )
    bh["sound_on_completion"] = new_sound
    if new_sound:
        st.caption("\U0001F50A Audio is generated locally using `st.audio` and a tiny in-memory WAV.")


# ============================================================================
# TAB 6: ABOUT & DIAGNOSTICS (with Updates subsection + export/import)
# ============================================================================

_UPDATE_CHANNEL_OPTIONS = ["stable", "beta"]


def _safe_importlib_version(dist_name: str) -> Optional[str]:
    try:
        from importlib.metadata import version, PackageNotFoundError
        try:
            return version(dist_name)
        except PackageNotFoundError:
            return None
    except Exception:
        return None


def _gather_versions() -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    try:
        from core_pipeline import __version__, __codename__, __released__
        out.append(("HY-TUTOR pipeline", f"{__version__} \u2014 {__codename__} ({__released__})"))
    except Exception:
        pass
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    out.append(("Python", py_ver))
    for pkg in ("streamlit", "google-genai", "chromadb", "pypdf", "pdfminer.six", "pydantic"):
        v = _safe_importlib_version(pkg)
        out.append((pkg, v or "(not installed)"))
    return out


def _run_diagnostics() -> Dict[str, Any]:
    """Run a series of system checks and return a structured result."""
    results: Dict[str, Any] = {"checks": []}

    # API key
    env_path = _project_root() / "config" / ".env"
    api_key_ok = False
    if env_path.exists():
        try:
            content = env_path.read_text(encoding="utf-8")
            api_key_ok = "GEMINI_API_KEY=" in content and "GEMINI_API_KEY=\n" not in content
        except Exception:
            pass
    results["checks"].append({
        "name": "Gemini API key",
        "status": "ok" if api_key_ok else "missing",
        "detail": "GEMINI_API_KEY present in config/.env" if api_key_ok else "Add GEMINI_API_KEY to config/.env",
    })

    # Ollama health
    ollama_ok = False
    try:
        sys.path.insert(0, str(_project_root() / "core_pipeline"))
        from utils.genai_client import check_ollama_health
        ollama_ok = check_ollama_health()
    except Exception:
        pass
    results["checks"].append({
        "name": "Ollama fallback",
        "status": "ok" if ollama_ok else "unavailable",
        "detail": "Local Ollama server reachable on :11434" if ollama_ok else "Not running (optional)",
    })

    # ChromaDB
    chroma_ok = False
    try:
        from utils.vector_db import get_vector_db
        vdb = get_vector_db()
        chroma_ok = vdb is not None
    except Exception:
        pass
    results["checks"].append({
        "name": "Vector DB",
        "status": "ok" if chroma_ok else "unavailable",
        "detail": "ChromaDB client initialized" if chroma_ok else "ChromaDB not installed or uninitialized",
    })

    # Recent errors
    try:
        from utils.usage_tracker import get_summary
        summary = get_summary()
        recent_fail = summary.get("failed_calls", 0)
        results["checks"].append({
            "name": "Recent API errors",
            "status": "ok" if recent_fail == 0 else "warn",
            "detail": f"{recent_fail} failed call(s) in current window",
        })
    except Exception:
        pass

    # Disk free
    try:
        import shutil as _sh
        usage = _sh.disk_usage(_project_root())
        free_gb = usage.free / (1024 ** 3)
        results["checks"].append({
            "name": "Disk space",
            "status": "ok" if free_gb > 1.0 else "warn",
            "detail": f"{free_gb:.2f} GB free on project drive",
        })
    except Exception:
        pass

    return results


def _render_about_tab(settings: Dict[str, Any]) -> None:
    st.markdown("### About & Diagnostics")
    upd = settings.setdefault("updates", {})
    upd.setdefault("channel", "stable")
    upd.setdefault("auto_check_on_boot", True)
    upd.setdefault("last_check_iso", None)
    upd.setdefault("last_known_local_head", None)

    # -----------------------------------------------------------------
    # Section 1: Version info
    # -----------------------------------------------------------------
    st.markdown("#### \U0001F4E6 Version Information")
    versions = _gather_versions()
    proj_root = str(_project_root())
    for name, val in versions:
        st.markdown(f"**{name}:** `{val}`")
    st.caption(f"Project root: `{proj_root}`")
    if (USER_SETTINGS_PATH.exists()):
        try:
            with open(USER_SETTINGS_PATH, "r", encoding="utf-8") as f:
                user_blob = json.load(f)
            last_mod = user_blob.get("last_modified", "never")
        except Exception:
            last_mod = "unknown"
    else:
        last_mod = "never (defaults only)"
    st.caption(f"Settings last modified: `{last_mod}`")

    st.markdown("---")

    # -----------------------------------------------------------------
    # Section 2: Diagnostics
    # -----------------------------------------------------------------
    st.markdown("#### \U0001F9EA Diagnostics")
    if st.button("\U0001F50D Run diagnostics", key="about_run_diagnostics"):
        st.session_state["_hytutor_diag_cache"] = _run_diagnostics()
    diag = st.session_state.get("_hytutor_diag_cache")
    if diag:
        for c in diag["checks"]:
            icon = {"ok": "\u2705", "warn": "\u26A0\ufe0F", "missing": "\u274C", "unavailable": "\u26A0\ufe0F"}.get(c["status"], "\u2753")
            color = {"ok": "#2D8659", "warn": "#D4A843", "missing": "#B5344A", "unavailable": "#4A5568"}.get(c["status"], "#4A5568")
            st.markdown(
                f'<div class="metric-tile"><div class="label">{icon} {c["name"]}</div>'
                f'<div class="sub" style="color:{color};">{c["detail"]}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # -----------------------------------------------------------------
    # Section 3: Updates
    # -----------------------------------------------------------------
    st.markdown("#### \U0001F504 Updates")
    st.caption("HY-TUTOR is self-hosted from a git repository. 'Updates' means a `git pull` against the remote.")

    # Channel
    cur_channel = upd.get("channel", "stable")
    if cur_channel not in _UPDATE_CHANNEL_OPTIONS:
        cur_channel = "stable"
    new_channel = st.radio(
        "Update channel",
        options=_UPDATE_CHANNEL_OPTIONS,
        format_func=lambda v: {
            "stable": "\U0001F7E2 Stable (main branch)",
            "beta":   "\U0001F7E1 Beta (develop branch)",
        }[v],
        index=_UPDATE_CHANNEL_OPTIONS.index(cur_channel),
        key="about_update_channel",
        horizontal=True,
    )
    upd["channel"] = new_channel

    # Cached status (read on first render, refreshed manually)
    if "_hytutor_update_status" not in st.session_state:
        try:
            sys.path.insert(0, str(_project_root() / "core_pipeline"))
            from utils.update_checker import get_update_status
            st.session_state["_hytutor_update_status"] = get_update_status(force_refresh=False)
        except Exception as e:
            st.session_state["_hytutor_update_status"] = {"status": "error", "error": str(e)}

    status = st.session_state["_hytutor_update_status"]
    state = status.get("status", "unknown")
    try:
        sys.path.insert(0, str(_project_root() / "core_pipeline"))
        from utils.update_checker import format_state_badge
        emoji, label = format_state_badge(state)
    except Exception:
        emoji, label = "\u2753", state

    badge_color = {
        "up_to_date":    "#2D8659",
        "behind":        "#D4A843",
        "local_changes": "#B5344A",
        "offline":       "#4A5568",
        "no_remote":     "#4A5568",
        "not_git":       "#4A5568",
        "no_git":        "#4A5568",
    }.get(state, "#4A5568")

    st.markdown(
        f'<div class="metric-tile"><div class="label">Update status</div>'
        f'<div class="value"><span class="update-badge" style="background-color:{badge_color};color:#FFFFFF;">{emoji} {label}</span></div></div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        local_head = status.get('current_head_short') or '?'
        local_branch = status.get('current_branch') or '?'
        st.caption(f"**Local:** `{local_head}` on `{local_branch}`")
    with c2:
        rb = status.get("remote_branch")
        rh = status.get("remote_head_short")
        st.caption(f"**Remote:** `{rh or '?'}` on `{rb or '?'}`" if rb else "**Remote:** not configured")

    if status.get("error"):
        st.caption(f"\u26A0\ufe0F {status['error']}")

    last_iso = status.get("last_check_iso")
    if last_iso:
        st.caption(f"Last checked: `{last_iso}`")

    behind_count = int(status.get("commits_behind_count", 0) or 0)
    if behind_count > 0:
        with st.expander(f"\U0001F4DC {behind_count} commit(s) behind \u2014 show diff", expanded=False):
            for c in status.get("commits_behind", []):
                st.markdown(
                    f"- `{c.get('date','')}` `{c.get('hash','')}` "
                    f"**{c.get('author','')}** \u2014 {c.get('subject','')}"
                )

    btn_cols = st.columns(3)
    with btn_cols[0]:
        if st.button("\U0001F504 Check now", key="about_update_check", width='stretch'):
            try:
                from utils.update_checker import check_now
                st.session_state["_hytutor_update_status"] = check_now()
                upd["last_check_iso"] = st.session_state["_hytutor_update_status"].get("last_check_iso")
                st.toast("Update check complete.", icon="\U0001F504")
                st.rerun()
            except Exception as e:
                st.error(f"Check failed: {e}")
    with btn_cols[1]:
        can_pull = state == "behind"
        if st.button(
            "\u2B07\ufe0F Pull updates",
            key="about_update_pull",
            width='stretch',
            disabled=not can_pull,
            help="Fast-forward pull. Disabled unless there are commits to pull.",
        ):
            st.session_state["_hytutor_pull_confirm"] = True
            st.rerun()
    with btn_cols[2]:
        if st.button("\U0001F4C2 View changelog", key="about_update_changelog", width='stretch'):
            st.session_state["_hytutor_show_changelog"] = True

    # Pull confirm dialog
    if st.session_state.get("_hytutor_pull_confirm"):
        st.warning(
            f"\u26A0\ufe0F This will run `git pull --ff-only` against "
            f"`origin/{status.get('remote_branch') or 'main'}` **and then** "
            f"`pip install -r requirements.txt` to upgrade any packages whose "
            f"versions changed. Type **pull** to confirm."
        )
        confirm = st.text_input("Type 'pull' to confirm", key="about_pull_confirm_input", label_visibility="collapsed")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("\u2705 Update & install now", key="about_pull_do", width='stretch'):
                if confirm.strip().lower() == "pull":
                    try:
                        from utils.update_checker import do_pull_and_install, get_update_status
                        with st.spinner("Pulling code & installing packages\u2026 (this can take a minute)"):
                            update_result = do_pull_and_install()
                        st.session_state["_hytutor_pull_confirm"] = False
                        st.session_state["_hytutor_last_update_result"] = update_result
                        # Refresh the status badge so the new commit count is reflected.
                        st.session_state["_hytutor_update_status"] = get_update_status(force_refresh=True)
                    except Exception as e:
                        st.error(f"Update failed: {e}")
                else:
                    st.error("Type 'pull' exactly.")
        with cc2:
            if st.button("\u274C Cancel", key="about_pull_cancel", width='stretch'):
                st.session_state["_hytutor_pull_confirm"] = False
                st.rerun()

    # ---------------------------------------------------------------
    # Last update result (rendered after a Pull+install cycle)
    # ---------------------------------------------------------------
    last_result = st.session_state.get("_hytutor_last_update_result")
    if last_result and not st.session_state.get("_hytutor_pull_confirm"):
        st.markdown("---")
        st.markdown("##### \U0001F4E6 Last update result")
        if not last_result.get("pulled"):
            st.error(
                f"\u274C Pull failed: {last_result.get('pull_message') or 'unknown error'}"
            )
        else:
            # 1) Git pull summary
            pulled_msg = (last_result.get("pull_message") or "").strip()
            if pulled_msg:
                # Show only the last meaningful lines of the git output
                tail = [ln.strip() for ln in pulled_msg.splitlines() if ln.strip()][-3:]
                summary = " \u00b7 ".join(tail)
                st.success(f"\u2705 Code pulled: {summary}")
            else:
                st.success("\u2705 Code is already up to date.")

            # 2) Pip install result
            if last_result.get("pip_ok"):
                n = len(last_result.get("upgraded_packages") or [])
                if n:
                    bullets = "\n".join(f"- `{p}`" for p in last_result["upgraded_packages"][:25])
                    extra = f"\n- \u2026and {n - 25} more" if n > 25 else ""
                    st.info(f"\U0001F4E6 Upgraded {n} package(s):\n\n{bullets}{extra}")
                elif last_result.get("requirements_changed"):
                    st.info(
                        "\U0001F4E6 `requirements.txt` changed in this pull, but no "
                        "packages needed upgrading (already on target versions)."
                    )
                else:
                    st.caption(
                        "\U0001F4E6 No package changes (requirements.txt was not "
                        "modified in this pull)."
                    )
            else:
                pip_err = last_result.get("pip_error") or "unknown error"
                pip_msg = (last_result.get("pip_message") or "")[-2000:]
                st.error(
                    f"\u26A0\ufe0F pip install failed: {pip_err}\n\n"
                    f"```\n{pip_msg}\n```\n\n"
                    f"You can retry from a terminal: `bash install.sh`"
                )

            # 3) Restart CTA (only if pull succeeded)
            if last_result.get("needs_restart"):
                st.warning(
                    "\U0001F504 **Restart HY-TUTOR** for the new code and "
                    "packages to take effect."
                )
                if st.button(
                    "\U0001F501 Restart HY-TUTOR",
                    key="about_restart_after_update",
                    type="primary",
                ):
                    try:
                        st.cache_data.clear()
                    except Exception:
                        pass
                    st.rerun()

    # Changelog viewer
    if st.session_state.get("_hytutor_show_changelog"):
        st.markdown("##### \U0001F4DC Changelog")
        for fname in ("CHANGES_PHASE1.md", "docs/PIPELINE_PROGRESS.md"):
            fpath = _project_root() / fname
            if fpath.exists():
                with st.expander(f"`{fname}`", expanded=False):
                    try:
                        content = fpath.read_text(encoding="utf-8")
                        if len(content) > 8000:
                            st.caption(f"(Showing first 8000 of {len(content)} chars)")
                            content = content[:8000]
                        st.code(content, language="markdown")
                    except Exception as e:
                        st.error(f"Could not read: {e}")
        if st.button("\u2715 Close changelog", key="about_changelog_close"):
            st.session_state["_hytutor_show_changelog"] = False
            st.rerun()

    st.markdown("---")

    # -----------------------------------------------------------------
    # Section 4: Export / Import settings
    # -----------------------------------------------------------------
    st.markdown("#### \U0001F4E4 Export / Import Settings")
    st.caption("Save your settings to a JSON file you can back up or sync across machines.")

    try:
        data = export_settings_bytes()
        st.download_button(
            label="\u2B07\ufe0F Download settings.json",
            data=data,
            file_name=f"hytutor-settings-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json",
            mime="application/json",
            key="about_export_settings",
            width='content',
        )
    except Exception as e:
        st.error(f"Export failed: {e}")

    uploaded = st.file_uploader(
        "Import settings.json",
        type=["json"],
        key="about_import_settings",
        help="Upload a previously exported settings file. Unknown keys are preserved, missing keys fall back to defaults.",
    )
    if uploaded is not None:
        if st.button("\u26A0\ufe0F Apply imported settings", key="about_import_apply"):
            try:
                raw = uploaded.read()
                if import_settings_bytes(raw):
                    st.session_state["hytutor_settings"] = load_settings()
                    st.success("Settings imported. Reloading...")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Could not parse the uploaded file. Make sure it is a valid HY-TUTOR settings JSON.")
            except Exception as e:
                st.error(f"Import failed: {e}")

    st.markdown("---")

    # -----------------------------------------------------------------
    # Section 5: Reset all
    # -----------------------------------------------------------------
    st.markdown("#### \u26A0\ufe0F Reset All Settings")
    st.caption("This will delete your saved preferences and restore the defaults on next reload.")
    if st.button("\U0001F5D1\ufe0F Reset everything to defaults", key="about_reset_all", type="secondary"):
        st.session_state["_hytutor_reset_confirm"] = True
        st.rerun()
    if st.session_state.get("_hytutor_reset_confirm"):
        st.warning("\u26A0\ufe0F Type **reset** to confirm wiping all your settings.")
        confirm = st.text_input("Type 'reset' to confirm", key="about_reset_input", label_visibility="collapsed")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("\u2705 Confirm reset", key="about_reset_do", width='stretch'):
                if confirm.strip().lower() == "reset":
                    reset_settings_to_defaults()
                    st.session_state["hytutor_settings"] = load_settings()
                    st.session_state["_hytutor_reset_confirm"] = False
                    st.toast("All settings reset to defaults.", icon="\U0001F5D1\ufe0F")
                    st.rerun()
                else:
                    st.error("Type 'reset' exactly.")
        with cc2:
            if st.button("\u274C Cancel", key="about_reset_cancel", width='stretch'):
                st.session_state["_hytutor_reset_confirm"] = False
                st.rerun()


# ============================================================================
# __all__
# ============================================================================

__all__ = [
    "render_settings_popover",
    "load_settings",
    "save_settings",
    "reset_settings_to_defaults",
    "export_settings_bytes",
    "import_settings_bytes",
    "build_dynamic_css",
    "USER_SETTINGS_PATH",
    "DEFAULTS_PATH",
]
