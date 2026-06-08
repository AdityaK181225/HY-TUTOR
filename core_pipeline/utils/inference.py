"""
HY-TUTOR: Universal Inference Gateway (inference.py)

Single point of entry for ALL AI inference calls in the pipeline.
Every provider (Google GenAI, OpenAI, Anthropic, Ollama) is wrapped by
a function in this module that:

  1. Times the call
  2. Passes the raw SDK response to the usage tracker for logging
  3. Returns the response text so the caller can parse it

Commands import from here instead of calling the SDK directly.
Adding a new provider = one new function + one pricing row in usage_tracker.

Compatibility:
  - Works with google-genai, openai, anthropic, and ollama (HTTP).
  - All kwargs from the existing command code are supported
    (response_mime_type, response_schema, temperature, max_output_tokens,
     system_instruction, etc.).
  - Retries are transparent — each attempt is logged separately.
  - The 'Track API calls' toggle in Settings → Usage is respected.
"""

import os
import sys
import time
import json
from typing import Any, Dict, List, Optional, Tuple

# Lazy imports — these are resolved inside each call function so the
# module is importable even when a particular SDK is not installed.
# We do NOT import google.genai / openai / anthropic at module level.

from .usage_tracker import record_inference


# ============================================================================
# HELPER: log a single call attempt
# ============================================================================

def _log_attempt(
    command: str,
    model: str,
    provider: str,
    status: str,
    start: float,
    prompt: str,
    response_text: str,
    response: Any,
    error: Optional[str],
    api_key: Optional[str],
) -> None:
    """Write one usage record. Never raises."""
    try:
        duration_ms = int((time.time() - start) * 1000)
        record_inference(
            command=command,
            model=model,
            provider=provider,
            status=status,
            duration_ms=duration_ms,
            prompt=prompt,
            response_text=response_text,
            response=response,
            error=error,
            api_key=api_key,
        )
    except Exception:
        pass  # logging must never break the pipeline


# ============================================================================
# GOOGLE GENAI
# ============================================================================

def call_gemini(
    command: str,
    model: str,
    prompt: str,
    *,
    contents: Any = None,
    system_prompt: str = "",
    temperature: float = 0.1,
    max_output_tokens: int = 16384,
    response_mime_type: Optional[str] = None,
    response_schema: Any = None,
    max_retries: int = 5,
    backoff_delays: Optional[List[int]] = None,
) -> Tuple[str, str]:
    """Google GenAI generate_content with automatic logging and retries.

    Parameters
    ----------
    command : str
        Pipeline command name (e.g. ``"command_0_syllabus"``).
    model : str
        Model identifier (e.g. ``"gemini-3.5-flash"``).
    prompt : str
        The full user prompt / payload text.  Ignored if ``contents`` is given.
    contents : Any, optional
        Structured Gemini conversation contents (a list of ``Content`` /
        ``Part`` objects) for multi-turn chat.  When ``None`` (the default)
        the single ``prompt`` string is sent as the user turn.
    system_prompt : str, optional
        System instruction prepended to the call.
    temperature : float
        Sampling temperature (default 0.1 for structured output).
    max_output_tokens : int
        Max tokens in the response.
    response_mime_type : str, optional
        e.g. ``"application/json"`` for structured output.
    response_schema : Any, optional
        A pydantic model class for structured output.
    max_retries : int
        Number of retry attempts on transient errors (default 5).
    backoff_delays : list[int], optional
        Per-attempt sleep durations in seconds.  Defaults to
        exponential: [1, 2, 4, 8, 16].

    Returns
    -------
    (response_text, model_used) : Tuple[str, str]
        The raw response text and the model that was actually used.

    Raises
    ------
    RuntimeError
        If all retries are exhausted.  The last exception is chained.
    """
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError

    api_key = os.getenv("GEMINI_API_KEY", "")
    client = genai.Client(api_key=api_key) if api_key else _get_genai_client()

    delays = backoff_delays if backoff_delays is not None else [1, 2, 4, 8, 16]
    last_exc: Optional[Exception] = None

    for attempt in range(max_retries):
        start = time.time()
        response = None
        response_text = ""
        status = "success"
        error_msg = None

        try:
            config_kwargs: Dict[str, Any] = {
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
            }
            if system_prompt:
                config_kwargs["system_instruction"] = system_prompt
            if response_mime_type:
                config_kwargs["response_mime_type"] = response_mime_type
            if response_schema is not None:
                config_kwargs["response_schema"] = response_schema

            _call_contents = contents if contents is not None else prompt
            response = client.models.generate_content(
                model=model,
                contents=_call_contents,
                config=types.GenerateContentConfig(**config_kwargs),
            )
            response_text = response.text or ""
            return response_text, model

        except Exception as e:
            status = "failure"
            error_msg = str(e)[:500]
            last_exc = e
            if attempt < max_retries - 1:
                wait = delays[min(attempt, len(delays) - 1)]
                print(f"[INFERENCE] {command} attempt {attempt + 1}/{max_retries} "
                      f"failed ({type(e).__name__}). Retrying in {wait}s...")
                time.sleep(wait)

        finally:
            _log_attempt(
                command=command,
                model=model,
                provider="google_genai",
                status=status,
                start=start,
                prompt=prompt,
                response_text=response_text,
                response=response,
                error=error_msg,
                api_key=api_key,
            )

    raise RuntimeError(
        f"All {max_retries} retries exhausted for {command} on {model}: {last_exc}"
    )


def _get_genai_client():
    """Fallback client factory (mirrors genai_client.get_genai_client)."""
    from google import genai
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print("[FATAL ERROR] GEMINI_API_KEY not found. Set it in config/.env")
        sys.exit(1)
    return genai.Client(api_key=key)


# ============================================================================
# OPENAI
# ============================================================================

def call_openai(
    command: str,
    model: str,
    prompt: str,
    *,
    system_prompt: str = "",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    max_retries: int = 5,
    backoff_delays: Optional[List[int]] = None,
) -> Tuple[str, str]:
    """OpenAI chat.completions.create with automatic logging and retries.

    Returns (response_text, model_used).  Raises RuntimeError on exhaustion.
    """
    from openai import OpenAI as _OpenAI  # type: ignore[import-not-found]

    api_key = os.getenv("OPENAI_API_KEY", "")
    client = _OpenAI(api_key=api_key)

    delays = backoff_delays if backoff_delays is not None else [1, 2, 4, 8, 16]
    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    last_exc: Optional[Exception] = None

    for attempt in range(max_retries):
        start = time.time()
        response = None
        response_text = ""
        status = "success"
        error_msg = None

        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            response_text = (response.choices[0].message.content or "") if response.choices else ""
            return response_text, model

        except Exception as e:
            status = "failure"
            error_msg = str(e)[:500]
            last_exc = e
            if attempt < max_retries - 1:
                wait = delays[min(attempt, len(delays) - 1)]
                print(f"[INFERENCE] {command} attempt {attempt + 1}/{max_retries} "
                      f"failed ({type(e).__name__}). Retrying in {wait}s...")
                time.sleep(wait)

        finally:
            _log_attempt(
                command=command,
                model=model,
                provider="openai",
                status=status,
                start=start,
                prompt=prompt,
                response_text=response_text,
                response=response,
                error=error_msg,
                api_key=api_key,
            )

    raise RuntimeError(
        f"All {max_retries} retries exhausted for {command} on {model}: {last_exc}"
    )


# ============================================================================
# ANTHROPIC
# ============================================================================

def call_anthropic(
    command: str,
    model: str,
    prompt: str,
    *,
    system_prompt: str = "",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    max_retries: int = 5,
    backoff_delays: Optional[List[int]] = None,
) -> Tuple[str, str]:
    """Anthropic messages.create with automatic logging and retries.

    Returns (response_text, model_used).  Raises RuntimeError on exhaustion.
    """
    from anthropic import Anthropic as _Anthropic  # type: ignore[import-not-found]

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    client = _Anthropic(api_key=api_key)

    delays = backoff_delays if backoff_delays is not None else [1, 2, 4, 8, 16]
    last_exc: Optional[Exception] = None

    for attempt in range(max_retries):
        start = time.time()
        response = None
        response_text = ""
        status = "success"
        error_msg = None

        try:
            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if system_prompt:
                kwargs["system"] = system_prompt

            response = client.messages.create(**kwargs)

            # Anthropic returns a list of content blocks
            parts = []
            for block in response.content:
                if hasattr(block, "text"):
                    parts.append(block.text)
            response_text = "".join(parts)
            return response_text, model

        except Exception as e:
            status = "failure"
            error_msg = str(e)[:500]
            last_exc = e
            if attempt < max_retries - 1:
                wait = delays[min(attempt, len(delays) - 1)]
                print(f"[INFERENCE] {command} attempt {attempt + 1}/{max_retries} "
                      f"failed ({type(e).__name__}). Retrying in {wait}s...")
                time.sleep(wait)

        finally:
            _log_attempt(
                command=command,
                model=model,
                provider="anthropic",
                status=status,
                start=start,
                prompt=prompt,
                response_text=response_text,
                response=response,
                error=error_msg,
                api_key=api_key,
            )

    raise RuntimeError(
        f"All {max_retries} retries exhausted for {command} on {model}: {last_exc}"
    )


# ============================================================================
# OLLAMA (local HTTP)
# ============================================================================

def call_ollama(
    command: str,
    model: str,
    prompt: str,
    *,
    system_prompt: str = "",
    timeout: float = 60.0,
) -> Tuple[str, str]:
    """Local Ollama HTTP call with automatic logging.

    No retries — Ollama failures are local and deterministic.
    Returns (response_text, model_used).
    """
    import requests as _requests

    api_url = "http://localhost:11434/api/generate"
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if system_prompt:
        payload["system"] = system_prompt

    start = time.time()
    response = None
    response_text = ""
    status = "success"
    error_msg = None

    try:
        resp = _requests.post(api_url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        response_text = data.get("response", "")
        # Ollama doesn't return a structured response object for logging,
        # so we pass None and let the tracker estimate tokens from char length.
        return response_text, model

    except Exception as e:
        status = "failure"
        error_msg = str(e)[:500]
        print(f"[OLLAMA] {command} failed: {e}")
        raise RuntimeError(f"Ollama inference failed for {command}: {e}") from e

    finally:
        _log_attempt(
            command=command,
            model=f"ollama:{model}",
            provider="ollama",
            status=status,
            start=start,
            prompt=prompt,
            response_text=response_text,
            response=response,
            error=error_msg,
            api_key=None,
        )


# ============================================================================
# SMART DISPATCHER
# ============================================================================

def call_inference(
    command: str,
    prompt: str,
    *,
    system_prompt: str = "",
    provider: str = "google_genai",
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_output_tokens: int = 16384,
    response_mime_type: Optional[str] = None,
    response_schema: Any = None,
    max_retries: int = 5,
    backoff_delays: Optional[List[int]] = None,
    ollama_model: str = "gemma4:e2b",
) -> Tuple[str, str]:
    """Smart dispatcher — routes to the right provider.

    Parameters
    ----------
    provider : str
        One of ``"google_genai"``, ``"openai"``, ``"anthropic"``, ``"ollama"``.
    model : str, optional
        If None, resolved via ``utils.genai_client.get_default_model(command)``.

    Returns (response_text, model_used).
    """
    if model is None:
        from .genai_client import get_default_model
        model = get_default_model(command)

    if provider == "google_genai":
        return call_gemini(
            command, model, prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type=response_mime_type,
            response_schema=response_schema,
            max_retries=max_retries,
            backoff_delays=backoff_delays,
        )
    elif provider == "openai":
        return call_openai(
            command, model, prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_output_tokens,
            max_retries=max_retries,
            backoff_delays=backoff_delays,
        )
    elif provider == "anthropic":
        return call_anthropic(
            command, model, prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_output_tokens,
            max_retries=max_retries,
            backoff_delays=backoff_delays,
        )
    elif provider == "ollama":
        return call_ollama(
            command, ollama_model, prompt,
            system_prompt=system_prompt,
        )
    else:
        raise ValueError(f"Unknown provider: {provider!r}")


__all__ = [
    "call_gemini",
    "call_openai",
    "call_anthropic",
    "call_ollama",
    "call_inference",
]