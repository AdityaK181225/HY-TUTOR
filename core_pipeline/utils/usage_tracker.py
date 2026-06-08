"""
HY-TUTOR: Usage Tracker
Non-invasive JSONL logger for API calls. Wraps genai_client so every
inference (success or failure) is recorded with model, command, latency,
status, and an optional token estimate. Aggregates are derived on demand
for the Settings -> Usage tab.

The tracker never raises -- logging failures must not break the pipeline.

Token extraction is 100% precise when the caller passes the SDK response
object: the tracker inspects Google GenAI ``usage_metadata``, OpenAI
``usage``, and Anthropic ``usage`` via duck-typing so no third-party
SDK import is needed at module level.
"""

import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Iterable, List, Optional


# ============================================================================
# PATHS
# ============================================================================

def _project_root() -> Path:
    """Return the project root regardless of cwd (this file lives 3 levels deep)."""
    return Path(__file__).resolve().parent.parent.parent


USAGE_LOG_PATH = _project_root() / "data_library" / "usage_log.jsonl"
USAGE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


# ============================================================================
# PRICING (per 1K tokens, USD)
# Used for the cost tile in the Settings -> Usage tab.
# Numbers are best-effort defaults so the cost figure is informative, not
# authoritative. Users can mentally scale by model tier.
# ============================================================================

PRICING_PER_1K_TOKENS: Dict[str, Dict[str, float]] = {
    # -- Google Gemini --
    "gemini-2.5-pro":          {"input": 0.00125, "output": 0.01000},
    "gemini-2.5-flash":        {"input": 0.00015, "output": 0.00060},
    "gemini-2.0-flash":        {"input": 0.00010, "output": 0.00040},
    "gemini-1.5-pro":          {"input": 0.00125, "output": 0.00500},
    "gemini-1.5-flash":        {"input": 0.000075,"output": 0.00030},
    "gemini-3.5-flash":        {"input": 0.000075, "output": 0.00030},
    "gemini-3.1-flash-lite":   {"input": 0.00002,  "output": 0.00006},
    "gemma-4-31b-it":          {"input": 0.0,      "output": 0.0},
    "gemma-4-26b-a4b-it":      {"input": 0.0,      "output": 0.0},
    "ollama:gemma4:e2b":       {"input": 0.0,      "output": 0.0},

    # -- OpenAI --
    "gpt-4o":                  {"input": 0.00250, "output": 0.01000},
    "gpt-4o-mini":             {"input": 0.00015, "output": 0.00060},
    "gpt-4-turbo":             {"input": 0.01000, "output": 0.03000},
    "gpt-4":                   {"input": 0.03000, "output": 0.06000},
    "gpt-3.5-turbo":           {"input": 0.00050, "output": 0.00150},
    "o1":                      {"input": 0.01500, "output": 0.06000},
    "o1-mini":                 {"input": 0.00300, "output": 0.01200},
    "o1-preview":              {"input": 0.01500, "output": 0.06000},
    "o3-mini":                 {"input": 0.00110, "output": 0.00440},
    "o3":                      {"input": 0.01000, "output": 0.04000},
    "o4-mini":                 {"input": 0.00110, "output": 0.00440},

    # -- Anthropic Claude --
    "claude-sonnet-4-20250514":    {"input": 0.00300, "output": 0.01500},
    "claude-3-5-sonnet-20241022":  {"input": 0.00300, "output": 0.01500},
    "claude-3-5-sonnet-20240620":  {"input": 0.00300, "output": 0.01500},
    "claude-3-opus-20240229":      {"input": 0.01500, "output": 0.07500},
    "claude-3-haiku-20240307":     {"input": 0.00025, "output": 0.00125},
    "claude-3-5-haiku-20241022":   {"input": 0.00100, "output": 0.00500},
}


# ============================================================================
# WRITE LOCK -- streamlit + subprocesses may share this file
# ============================================================================

_write_lock = Lock()


# ============================================================================
# PROVIDER-AGNOSTIC TOKEN EXTRACTION
# ============================================================================

@dataclass
class ExtractedUsage:
    """Token counts extracted from an API response object via duck-typing."""
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    total_tokens: Optional[int]
    cached_tokens: Optional[int]
    provider_tag: str   # "google_genai" | "openai" | "anthropic" | "unknown"


def extract_usage_from_response(response: Any) -> ExtractedUsage:
    """
    Provider-agnostic token-count extraction from an SDK response object.

    Uses duck-typing -- works with google.genai, openai, and anthropic
    response objects without importing any of those packages at module level.

    Resolution order:
      1. Google GenAI: response.usage_metadata.prompt_token_count /
         .candidates_token_count
      2. OpenAI:      response.usage.prompt_tokens / .completion_tokens
         / .cached_tokens
      3. Anthropic:   response.usage.input_tokens / .output_tokens
      4. Fallback:    returns all None (caller falls back to char estimation)
    """
    if response is None:
        return ExtractedUsage(None, None, None, None, "unknown")

    # --- Google GenAI: response.usage_metadata ---
    try:
        um = response.usage_metadata  # type: ignore[union-attr]
        if um is not None:
            in_tok = getattr(um, "prompt_token_count", None)
            out_tok = getattr(um, "candidates_token_count", None)
            total = getattr(um, "total_token_count", None)
            if in_tok is not None or out_tok is not None:
                return ExtractedUsage(
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    total_tokens=total,
                    cached_tokens=getattr(um, "cached_content_token_count", None),
                    provider_tag="google_genai",
                )
    except AttributeError:
        pass

    # --- OpenAI: response.usage ---
    try:
        usage = response.usage  # type: ignore[union-attr]
        if usage is not None:
            in_tok = getattr(usage, "prompt_tokens", None)
            out_tok = getattr(usage, "completion_tokens", None)
            total = getattr(usage, "total_tokens", None)
            if in_tok is not None or out_tok is not None:
                return ExtractedUsage(
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    total_tokens=total,
                    cached_tokens=getattr(usage, "cached_tokens", None),
                    provider_tag="openai",
                )
    except AttributeError:
        pass

    # --- Anthropic: response.usage ---
    try:
        usage = response.usage  # type: ignore[union-attr]
        if usage is not None:
            in_tok = getattr(usage, "input_tokens", None)
            out_tok = getattr(usage, "output_tokens", None)
            if in_tok is not None or out_tok is not None:
                # Anthropic does not expose total_tokens; derive it.
                total = (in_tok or 0) + (out_tok or 0) if (in_tok is not None or out_tok is not None) else None
                return ExtractedUsage(
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    total_tokens=total,
                    cached_tokens=getattr(usage, "cache_read_input_tokens", None),
                    provider_tag="anthropic",
                )
    except AttributeError:
        pass

    # --- No match ---
    return ExtractedUsage(None, None, None, None, "unknown")


# ============================================================================
# CORE API
# ============================================================================

def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _approx_tokens(text: str) -> int:
    """
    Rough token estimate when an API doesn't return a usage block.
    ~4 characters per token is a reasonable rule of thumb.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def fingerprint_api_key(key: Optional[str], provider: str = "") -> str:
    """
    Derive a short, safe identifier from an API key.

    Never logs the full key.  Returns e.g. ``"gemini:xyz9"`` or
    ``"openai:abc1"`` or ``"unknown:????"`` when the key is missing.
    """
    if not key or not key.strip():
        return f"{provider or 'unknown'}:????"
    tail = key.strip()[-4:]
    return f"{provider or 'unknown'}:{tail}"


def log_call(
    command: str,
    model: str,
    *,
    status: str = "success",
    prompt_chars: int = 0,
    response_chars: int = 0,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    duration_ms: int = 0,
    error: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    response: Any = None,
    provider: str = "unknown",
    api_key_id: Optional[str] = None,
) -> None:
    """
    Append a single record to the JSONL usage log.

    Args:
        command: Pipeline command name (e.g., "command_6_tutor").
        model: Model id used (e.g., "gemini-3.5-flash" or "ollama:gemma4:e2b").
        status: "success" | "failure" | "timeout" | "skipped".
        prompt_chars: Length of the input prompt (best effort).
        response_chars: Length of the response text (best effort).
        input_tokens: Optional explicit input token count.  When *None* and
            *response* is provided, extracted automatically via duck-typing.
        output_tokens: Optional explicit output token count. Same logic.
        duration_ms: Wall-clock duration of the call in milliseconds.
        error: Short error message (truncated to 500 chars).
        extra: Free-form additional context.
        response: Raw SDK response object.  When provided, the tracker
            extracts exact token counts via ``extract_usage_from_response``
            unless *input_tokens* / *output_tokens* are already set.
        provider: One of "google_genai", "openai", "anthropic", "ollama",
            or "unknown".
        api_key_id: Safe fingerprint of the API key used (e.g. ``"gemini:xyz9"``).
            Never store the raw key.
    """
    # -- Auto-extract tokens from the response object if not supplied --
    token_source = "estimated"
    if (input_tokens is None or output_tokens is None) and response is not None:
        extracted = extract_usage_from_response(response)
        if input_tokens is None:
            input_tokens = extracted.input_tokens
        if output_tokens is None:
            output_tokens = extracted.output_tokens
        if provider == "unknown" and extracted.provider_tag != "unknown":
            provider = extracted.provider_tag
        if extracted.input_tokens is not None or extracted.output_tokens is not None:
            token_source = "exact"

    # -- Finalise token counts (fall back to character estimation) --
    if input_tokens is None:
        input_tokens = _approx_tokens("x" * prompt_chars) if prompt_chars else 0
    if output_tokens is None:
        output_tokens = _approx_tokens("x" * response_chars) if response_chars else 0

    record = {
        "ts": _now_iso(),
        "command": command,
        "model": model,
        "provider": provider,
        "api_key_id": api_key_id,
        "status": status,
        "duration_ms": int(duration_ms),
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "prompt_chars": int(prompt_chars),
        "response_chars": int(response_chars),
        "token_source": token_source,
        "error": (error or "")[:500] or None,
        "extra": extra or {},
    }

    line = json.dumps(record, ensure_ascii=False)

    try:
        with _write_lock:
            with open(USAGE_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        # Never let logging break the pipeline.
        pass


@contextmanager
def track_call(command: str, model: str, prompt: str = ""):
    """
    Context manager that records success/failure + latency for a single call.

    Example:
        with track_call("command_6_tutor", "gemini-3.5-flash", prompt=text):
            response = client.models.generate_content(...)
    """
    start = time.time()
    err: Optional[str] = None
    status = "success"
    response_text = ""
    try:
        yield  # the caller is expected to set response_text via a side-channel
    except Exception as e:  # noqa: BLE001
        status = "failure"
        err = str(e)[:500]
        raise
    finally:
        elapsed_ms = int((time.time() - start) * 1000)
        log_call(
            command=command,
            model=model,
            status=status,
            prompt_chars=len(prompt or ""),
            response_chars=len(response_text or ""),
            duration_ms=elapsed_ms,
            error=err,
        )


# ============================================================================
# AGGREGATION -- used by the Settings -> Usage tab
# ============================================================================

def _read_records(since_iso: Optional[str] = None) -> Iterable[Dict[str, Any]]:
    if not USAGE_LOG_PATH.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with open(USAGE_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if since_iso and rec.get("ts", "") < since_iso:
                    continue
                out.append(rec)
    except Exception:
        return []
    return out


def get_summary(reset_at_iso: Optional[str] = None) -> Dict[str, Any]:
    """
    Return aggregated usage stats since *reset_at_iso* (or lifetime if None).

    Shape:
        {
            "total_calls": int,
            "success_calls": int,
            "failed_calls": int,
            "total_input_tokens": int,
            "total_output_tokens": int,
            "estimated_cost_usd": float,
            "calls_per_day": [{"date": "2026-03-06", "count": 12}, ...],
            "model_breakdown": [{"model": "...", "count": 7}, ...],
            "command_breakdown": [{"command": "...", "count": 4}, ...],
            "provider_breakdown": [{"provider": "...", "count": 5}, ...],
            "token_source_breakdown": [{"source": "exact", "count": 3}, ...],
            "exact_token_pct": float,
            "recent_calls": [record, ...]   # last 20
        }
    """
    records = list(_read_records(since_iso=reset_at_iso))

    total = len(records)
    success = sum(1 for r in records if r.get("status") == "success")
    failed = total - success

    total_in = sum(int(r.get("input_tokens", 0)) for r in records)
    total_out = sum(int(r.get("output_tokens", 0)) for r in records)

    # Cost
    cost = 0.0
    for r in records:
        model = r.get("model", "")
        pricing = PRICING_PER_1K_TOKENS.get(model)
        if not pricing:
            # try stripping "ollama:" prefix
            pricing = PRICING_PER_1K_TOKENS.get(model.split(":", 1)[-1], {"input": 0.0, "output": 0.0})
        cost += (int(r.get("input_tokens", 0)) / 1000.0) * pricing["input"]
        cost += (int(r.get("output_tokens", 0)) / 1000.0) * pricing["output"]

    # Calls per day -- last 14 days
    today = datetime.utcnow().date()
    days = [today - timedelta(days=i) for i in range(13, -1, -1)]
    per_day_counter = {d.isoformat(): 0 for d in days}
    for r in records:
        try:
            d = datetime.fromisoformat(r["ts"].rstrip("Z")).date().isoformat()
        except Exception:
            continue
        if d in per_day_counter:
            per_day_counter[d] += 1
    calls_per_day = [{"date": k, "count": v} for k, v in per_day_counter.items()]

    # Model breakdown
    model_counter: Dict[str, int] = {}
    for r in records:
        m = r.get("model", "unknown")
        model_counter[m] = model_counter.get(m, 0) + 1
    model_breakdown = sorted(
        [{"model": k, "count": v} for k, v in model_counter.items()],
        key=lambda x: -x["count"],
    )

    # Command breakdown
    cmd_counter: Dict[str, int] = {}
    for r in records:
        c = r.get("command", "unknown")
        cmd_counter[c] = cmd_counter.get(c, 0) + 1
    command_breakdown = sorted(
        [{"command": k, "count": v} for k, v in cmd_counter.items()],
        key=lambda x: -x["count"],
    )

    # Provider breakdown
    prov_counter: Dict[str, int] = {}
    for r in records:
        p = r.get("provider", "unknown")
        prov_counter[p] = prov_counter.get(p, 0) + 1
    provider_breakdown = sorted(
        [{"provider": k, "count": v} for k, v in prov_counter.items()],
        key=lambda x: -x["count"],
    )

    # Token source breakdown (exact vs estimated)
    source_counter: Dict[str, int] = {}
    for r in records:
        s = r.get("token_source", "estimated")
        source_counter[s] = source_counter.get(s, 0) + 1
    token_source_breakdown = [
        {"source": k, "count": v} for k, v in source_counter.items()
    ]

    exact_count = source_counter.get("exact", 0)
    exact_token_pct = round(exact_count / max(total, 1) * 100, 1)

    # Per-provider token aggregates
    prov_tok: Dict[str, Dict[str, int]] = {}
    prov_cost: Dict[str, float] = {}
    for r in records:
        p = r.get("provider", "unknown")
        if p not in prov_tok:
            prov_tok[p] = {"input_tokens": 0, "output_tokens": 0, "count": 0}
            prov_cost[p] = 0.0
        prov_tok[p]["input_tokens"] += int(r.get("input_tokens", 0))
        prov_tok[p]["output_tokens"] += int(r.get("output_tokens", 0))
        prov_tok[p]["count"] += 1
        # Per-provider cost
        model = r.get("model", "")
        pricing = PRICING_PER_1K_TOKENS.get(model)
        if not pricing:
            pricing = PRICING_PER_1K_TOKENS.get(model.split(":", 1)[-1], {"input": 0.0, "output": 0.0})
        prov_cost[p] += (int(r.get("input_tokens", 0)) / 1000.0) * pricing["input"]
        prov_cost[p] += (int(r.get("output_tokens", 0)) / 1000.0) * pricing["output"]

    provider_token_breakdown = sorted(
        [
            {
                "provider": k,
                "count": v["count"],
                "input_tokens": v["input_tokens"],
                "output_tokens": v["output_tokens"],
                "cost_usd": round(prov_cost.get(k, 0.0), 6),
            }
            for k, v in prov_tok.items()
        ],
        key=lambda x: -x["count"],
    )

    # Average latency
    total_duration = sum(int(r.get("duration_ms", 0)) for r in records)
    avg_latency_ms = round(total_duration / max(total, 1), 1)

    # Per-API-key breakdown
    key_data: Dict[str, Dict[str, Any]] = {}
    for r in records:
        kid = r.get("api_key_id") or "unknown"
        if kid not in key_data:
            key_data[kid] = {
                "api_key_id": kid,
                "provider": r.get("provider", "unknown"),
                "count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
            }
        kd = key_data[kid]
        kd["count"] += 1
        kd["input_tokens"] += int(r.get("input_tokens", 0))
        kd["output_tokens"] += int(r.get("output_tokens", 0))
        model = r.get("model", "")
        pricing = PRICING_PER_1K_TOKENS.get(model)
        if not pricing:
            pricing = PRICING_PER_1K_TOKENS.get(model.split(":", 1)[-1], {"input": 0.0, "output": 0.0})
        kd["cost_usd"] += (int(r.get("input_tokens", 0)) / 1000.0) * pricing["input"]
        kd["cost_usd"] += (int(r.get("output_tokens", 0)) / 1000.0) * pricing["output"]

    api_key_breakdown = sorted(
        [
            {
                **kd,
                "cost_usd": round(kd["cost_usd"], 6),
            }
            for kd in key_data.values()
        ],
        key=lambda x: -x["count"],
    )

    # Last 20 calls
    recent = records[-20:][::-1]

    return {
        "total_calls": total,
        "success_calls": success,
        "failed_calls": failed,
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "estimated_cost_usd": round(cost, 4),
        "avg_latency_ms": avg_latency_ms,
        "calls_per_day": calls_per_day,
        "model_breakdown": model_breakdown,
        "command_breakdown": command_breakdown,
        "provider_breakdown": provider_breakdown,
        "provider_token_breakdown": provider_token_breakdown,
        "api_key_breakdown": api_key_breakdown,
        "token_source_breakdown": token_source_breakdown,
        "exact_token_pct": exact_token_pct,
        "recent_calls": recent,
    }


def reset_log() -> bool:
    """Truncate the usage log. Returns True on success."""
    try:
        with _write_lock:
            if USAGE_LOG_PATH.exists():
                USAGE_LOG_PATH.unlink()
        return True
    except Exception:
        return False


# ============================================================================
# HIGH-LEVEL INFERENCE LOGGER — used by inference.py gateway
# ============================================================================

def _read_track_calls_flag() -> bool:
    """Check the 'Track API calls' toggle from user_settings.json.

    Returns True (track) if the file is missing, malformed, or the key is absent
    — i.e. tracking is ON by default.  The only way to silence logging is to
    explicitly uncheck the toggle in Settings → Usage.
    """
    try:
        settings_path = _project_root() / "data_library" / "active_workspace" / "user_settings.json"
        if not settings_path.exists():
            return True
        import json as _json
        raw = _json.loads(settings_path.read_text(encoding="utf-8"))
        return bool(raw.get("usage", {}).get("track_calls", True))
    except Exception:
        return True  # default: tracking ON


def record_inference(
    command: str,
    model: str,
    provider: str,
    *,
    status: str = "success",
    duration_ms: int = 0,
    prompt: str = "",
    response_text: str = "",
    response: Any = None,
    error: Optional[str] = None,
    api_key: Optional[str] = None,
) -> None:
    """Single entry-point for logging an inference call from the gateway.

    Respects the 'Track API calls' toggle — returns silently when disabled.
    Token counts are auto-extracted from *response* via duck-typing when the
    caller passes the raw SDK response object.
    """
    if not _read_track_calls_flag():
        return

    api_key_id = None
    if api_key:
        api_key_id = fingerprint_api_key(api_key, provider)

    log_call(
        command=command,
        model=model,
        status=status,
        prompt_chars=len(prompt or ""),
        response_chars=len(response_text or ""),
        duration_ms=duration_ms,
        error=error,
        response=response,
        provider=provider,
        api_key_id=api_key_id,
    )


__all__ = [
    "log_call",
    "track_call",
    "get_summary",
    "reset_log",
    "USAGE_LOG_PATH",
    "PRICING_PER_1K_TOKENS",
    "extract_usage_from_response",
    "ExtractedUsage",
    "fingerprint_api_key",
    "record_inference",
    "_read_track_calls_flag",
]
