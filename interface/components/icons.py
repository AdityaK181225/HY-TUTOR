"""
HY-TUTOR: Centralized SVG Icon Utility
Provides inline SVG icons for UI elements that need graphical indicators
beyond what Unicode emoji can offer.
"""

import streamlit as st
import streamlit.components.v1 as components


# ── SVG Icon Registry ──────────────────────────────────────────────────────
# Each value is the inner SVG content (paths, circles, etc.) sized to a
# 24×24 viewBox. The `icon()` helper wraps it in a <span>.

ICONS: dict[str, str] = {
    "send": (
        '<path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" fill="currentColor"/>'
    ),
    "arrow_back": (
        '<path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z" fill="currentColor"/>'
    ),
    "arrow_forward": (
        '<path d="M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8z" fill="currentColor"/>'
    ),
    "chevron_right": (
        '<path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z" fill="currentColor"/>'
    ),
    "chevron_left": (
        '<path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z" fill="currentColor"/>'
    ),
    "chevron_down": (
        '<path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z" fill="currentColor"/>'
    ),
    "chevron_up": (
        '<path d="M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z" fill="currentColor"/>'
    ),
    "play_arrow": (
        '<path d="M8 5v14l11-7z" fill="currentColor"/>'
    ),
    "skip_next": (
        '<path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z" fill="currentColor"/>'
    ),
    "skip_previous": (
        '<path d="M6 6h2v12H6zm3.5 6l8.5 6V6z" fill="currentColor"/>'
    ),
    "refresh": (
        '<path d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z" fill="currentColor"/>'
    ),
    "restart_alt": (
        '<path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z" fill="currentColor"/>'
    ),
    "delete": (
        '<path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="currentColor"/>'
    ),
    "flag": (
        '<path d="M14.4 6L14 4H5v17h2v-7h5.6l.4 2h7V6z" fill="currentColor"/>'
    ),
    "logout": (
        '<path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z" fill="currentColor"/>'
    ),
    "rocket_launch": (
        '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" fill="currentColor"/>'
    ),
    "search": (
        '<path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" fill="currentColor"/>'
    ),
    "build": (
        '<path d="M22.7 19l-9.1-9.1c.9-2.3.4-5-1.5-6.9-2-2-5-2.4-7.4-1.3L9 6 6 9 1.6 4.7C.4 7.1.9 10.1 2.9 12.1c1.9 1.9 4.6 2.4 6.9 1.5l9.1 9.1c.4.4 1 .4 1.4 0l2.3-2.3c.5-.4.5-1.1.1-1.4z" fill="currentColor"/>'
    ),
    "check_circle": (
        '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" fill="currentColor"/>'
    ),
}


def icon(
    name: str,
    size: int = 18,
    color: str = "currentColor",
    className: str = "",
    vertical_align: str = "middle",
) -> str:
    """
    Return an inline HTML <span> wrapping an SVG icon.

    Parameters
    ----------
    name : str
        Key from the ICONS registry.
    size : int
        Icon size in pixels (width and height).
    color : str
        CSS color value.
    className : str
        Optional CSS class to add to the <span>.
    vertical_align : str
        CSS vertical-align value.

    Returns
    -------
    str
        Raw HTML string safe for ``unsafe_allow_html=True``.
    """
    svg_inner = ICONS.get(name, "")
    if not svg_inner:
        return ""
    cls_attr = f' class="{className}"' if className else ""
    return (
        f'<span{cls_attr} style="display:inline-flex;align-items:center;'
        f"vertical-align:{vertical_align};line-height:1;"
        f'width:{size}px;height:{size}px;margin:0 4px;">'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'width="{size}" height="{size}" style="color:{color};">'
        f"{svg_inner}</svg></span>"
    )


def icon_button(
    icon_name: str,
    label: str,
    key: str,
    button_type: str = "secondary",
    use_container_width: bool = False,
    help_text: str = "",
    size: int = 18,
) -> bool:
    """
    Render a Streamlit button with an inline SVG icon to its left.

    Because ``st.button`` only accepts plain-text labels, we render the icon
    as a tiny ``st.html`` component positioned just above a minimal text
    button, giving the visual effect of an icon button.

    For a simpler approach, this actually renders the button label with an
    emoji prefix (since emoji render as graphics in button text). The SVG
    icon is only used in the ``st.markdown`` companion above the button.

    Returns True if the button was clicked.
    """
    # Use emoji for button labels (Streamlit limitation) — consistent set
    _EMOJI_MAP = {
        "arrow_back": "⬅️",
        "arrow_forward": "➡️",
        "chevron_right": "▸",
        "chevron_left": "◂",
        "play_arrow": "▶",
        "skip_next": "⏭️",
        "skip_previous": "⏪",
        "refresh": "🔄",
        "restart_alt": "🔁",
        "delete": "🗑️",
        "flag": "🏁",
        "logout": "🚪",
        "rocket_launch": "🚀",
        "search": "🔍",
        "build": "🔨",
        "check_circle": "✅",
        "send": "➤",
    }
    emoji = _EMOJI_MAP.get(icon_name, "")
    full_label = f"{emoji} {label}" if emoji else label
    return st.button(
        full_label,
        key=key,
        type=button_type,
        use_container_width=width,
        help=help_text or None,
    )


__all__ = ["icon", "icon_button", "ICONS"]