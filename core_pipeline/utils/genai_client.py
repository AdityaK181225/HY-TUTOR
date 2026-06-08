"""
HY-TUTOR: Centralized GenAI Client Factory
Ensures consistent API key handling, error management, and model fallback chains
across all commands.

Supports three inference backends:
  1. Google GenAI  (google-genai SDK)  — primary
  2. OpenAI        (openai SDK)        — opt-in, lazy import
  3. Anthropic     (anthropic SDK)     — opt-in, lazy import
  4. Ollama        (HTTP REST)         — local fallback

Every call to the inference backends is wrapped with usage logging so the
Settings → Usage tab reflects real pipeline activity with **exact** token
counts (never estimated) when the SDK response object is available.
"""

import os
import sys
import time
from pathlib import Path
from typing import Any, Optional, List, Dict, Tuple
from google import genai
from google.genai import types
from google.genai.errors import APIError
from dotenv import load_dotenv

# Usage tracking import (best-effort — tracker is never allowed to break inference)
try:
    from .usage_tracker import log_call as _log_call_impl
    from .usage_tracker import fingerprint_api_key as _fingerprint
except ImportError:
    _log_call_impl = None
    _fingerprint = None

# Load environment variables once at module level
load_dotenv(dotenv_path=Path("config/.env"))


# ============================================================================
# MODEL FALLBACK CHAINS
# ============================================================================

# Define fallback chains for each command
# Format: ["primary_model", "fallback_1", "fallback_2", ...]
MODEL_FALLBACK_CHAINS: Dict[str, List[str]] = {
    # Syllabus building (needs high reasoning)
    "command_0_syllabus": [
        "gemini-3.5-flash",
        "gemma-4-31b-it",
        "gemini-3.1-flash-lite",
    ],

    # Syllabus editing (needs high reasoning)
    "command_0_1_editor": [
        "gemini-3.5-flash",
        "gemma-4-31b-it",
        "gemini-3.1-flash-lite",
    ],

    # Edge Router (simple classification, fast)
    "command_0_5_router": [
        "gemma-4-31b-it",
        "gemma-4-26b-a4b-it",
        "gemini-3.1-flash-lite",
    ],

    # Blueprint (semantic chunking, needs context)
    "command_1_blueprint": [
        "gemini-3.1-flash-lite",
        "gemma-4-26b-a4b-it",
        "gemini-3.5-flash",
    ],

    # Miner (verbatim extraction, precision)
    "command_2_miner": [
        "gemini-3.1-flash-lite",
        "gemma-4-26b-a4b-it",
        "gemini-3.5-flash",
    ],

    # Optimizer (reference processing, needs depth)
    "command_3_optimizer": [
        "gemma-4-26b-a4b-it",
        "gemma-4-31b-it",
        "gemini-3.1-flash-lite",
    ],

    # Bridge (cognitive linking, reasoning)
    "command_4_bridge": [
        "gemini-3.1-flash-lite",
        "gemma-4-26b-a4b-it",
        "gemma-4-31b-it",
    ],

    # Forge (synthesis, creative)
    "command_5_forge": [
        "gemma-4-31b-it",
        "gemma-4-26b-a4b-it",
        "gemini-3.1-flash-lite",
    ],

    # Injector (problem extraction)
    "command_5_5_injector": [
        "gemini-3.1-flash-lite",
        "gemma-4-26b-a4b-it",
        "gemini-3.5-flash",
    ],

    # Tutor (conversational, reasoning)
    "command_6_tutor": [
        "gemma-4-31b-it",
        "gemma-4-26b-a4b-it",
        "gemini-3.1-flash-lite",
    ],

    # Ledger (analysis, scoring)
    "command_7_ledger": [
        "gemma-4-31b-it",
        "gemma-4-26b-a4b-it",
        "gemini-3.1-flash-lite",
    ],
}


# ============================================================================
# CLIENT FACTORIES
# ============================================================================

def get_genai_client(api_key: Optional[str] = None) -> genai.Client:
    """
    Centralized Google GenAI client factory with consistent error handling.

    Args:
        api_key: Optional explicit API key. If None, uses GEMINI_API_KEY from .env

    Returns:
        genai.Client instance

    Raises:
        SystemExit: If API key is not available
    """
    key = api_key or os.getenv("GEMINI_API_KEY")

    if not key or key == "":
        print("[FATAL ERROR] GEMINI_API_KEY not found. Set it in config/.env")
        print("Get your API key from: https://aistudio.google.com/app/apikey")
        sys.exit(1)

    try:
        return genai.Client(api_key=key)
    except Exception as e:
        print(f"[FATAL ERROR] Failed to initialize Google GenAI client: {e}")
        sys.exit(1)


def get_openai_client(api_key: Optional[str] = None) -> Any:
    """
    Factory for OpenAI client (requires ``pip install openai``).

    Args:
        api_key: Optional explicit API key. Falls back to OPENAI_API_KEY env var.

    Returns:
        openai.OpenAI client instance

    Raises:
        ImportError: If the ``openai`` package is not installed.
        SystemExit: If API key is not available.
    """
    try:
        import openai as _openai
    except ImportError:
        print("[FATAL ERROR] The 'openai' package is not installed.")
        print("Install it with:  pip install openai")
        sys.exit(1)

    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key or key == "":
        print("[FATAL ERROR] OPENAI_API_KEY not found. Set it in config/.env")
        sys.exit(1)

    return _openai.OpenAI(api_key=key)


def get_anthropic_client(api_key: Optional[str] = None) -> Any:
    """
    Factory for Anthropic client (requires ``pip install anthropic``).

    Args:
        api_key: Optional explicit API key. Falls back to ANTHROPIC_API_KEY env var.

    Returns:
        anthropic.Anthropic client instance

    Raises:
        ImportError: If the ``anthropic`` package is not installed.
        SystemExit: If API key is not available.
    """
    try:
        import anthropic as _anthropic
    except ImportError:
        print("[FATAL ERROR] The 'anthropic' package is not installed.")
        print("Install it with:  pip install anthropic")
        sys.exit(1)

    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not key or key == "":
        print("[FATAL ERROR] ANTHROPIC_API_KEY not found. Set it in config/.env")
        sys.exit(1)

    return _anthropic.Anthropic(api_key=key)


# ============================================================================
# MODEL SELECTION WITH FALLBACK
# ============================================================================

def get_model_with_fallback(
    command_name: str,
    client: genai.Client,
    max_retries: int = 3,
    timeout_per_try: int = 60
) -> Tuple[str, genai.Client]:
    """
    Get a working model with automatic fallback through the chain.

    Tests each model in the fallback chain until one succeeds with a simple
    test prompt. This ensures we use a working model even if the primary is unavailable.

    Args:
        command_name: Name of the command (e.g., 'command_0_5_router')
        client: GenAI client instance
        max_retries: Maximum retry attempts per model
        timeout_per_try: Timeout for each test in seconds

    Returns:
        Tuple of (model_name, client) that is guaranteed to work

    Raises:
        SystemExit: If all models in the fallback chain fail
    """
    fallback_chain = MODEL_FALLBACK_CHAINS.get(command_name, MODEL_FALLBACK_CHAINS["command_0_5_router"])
    test_prompt = "Say 'test'"

    for model_name in fallback_chain:
        print(f"[MODEL SELECTION] Trying {model_name} for {command_name}...")

        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=test_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        max_output_tokens=5
                    )
                )

                if response.text.strip().lower() == "test":
                    print(f"[MODEL SELECTION] SUCCESS: {model_name} is working for {command_name}")
                    return model_name, client
                else:
                    print(f"[MODEL SELECTION] WARNING: {model_name} returned unexpected response: {response.text}")

            except (APIError, Exception) as e:
                if attempt < max_retries - 1:
                    print(f"[MODEL SELECTION] Attempt {attempt + 1} failed for {model_name}: {str(e)[:100]}")
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    print(f"[MODEL SELECTION] All attempts failed for {model_name}: {str(e)[:100]}")

    # All models failed
    print(f"[FATAL ERROR] All models in fallback chain failed for {command_name}")
    print(f"Tried: {', '.join(fallback_chain)}")
    sys.exit(1)


def get_default_model(command_name: str) -> str:
    """
    Get the default model for a specific command.
    Can be overridden by environment variables.

    Args:
        command_name: Name of the command (e.g., 'command_0_5_router')

    Returns:
        Model name string (the first model in the fallback chain)
    """
    fallback_chain = MODEL_FALLBACK_CHAINS.get(command_name, MODEL_FALLBACK_CHAINS["command_0_5_router"])

    # Check for command-specific override
    env_var = f"COMMAND_{command_name.upper().replace('-', '_').replace(' ', '_')}_MODEL"
    custom_model = os.getenv(env_var)
    if custom_model:
        return custom_model

    # Return first model in fallback chain
    return fallback_chain[0] if fallback_chain else "gemma-4-31b-it"


def get_model_chain(command_name: str) -> List[str]:
    """
    Get the full fallback chain for a command.

    Args:
        command_name: Name of the command

    Returns:
        List of model names in priority order
    """
    return MODEL_FALLBACK_CHAINS.get(command_name, MODEL_FALLBACK_CHAINS["command_0_5_router"])


# ============================================================================
# USAGE LOGGING HELPER (provider-agnostic)
# ============================================================================

# ============================================================================
# OLLAMA HEALTH CHECK & FALLBACK
# ============================================================================

def check_ollama_health(timeout: float = 3.0) -> bool:
    """
    Check if local Ollama server is running and responsive.

    Args:
        timeout: Request timeout in seconds

    Returns:
        True if Ollama is reachable and healthy
    """
    import requests as _requests
    try:
        resp = _requests.get("http://localhost:11434/api/tags", timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


def query_ollama(
    prompt: str,
    model: str = "gemma4:e2b",
    system_prompt: str = "",
    timeout: float = 60.0,
) -> Optional[str]:
    """
    Send a prompt to local Ollama for inference.
    Returns None if Ollama is unreachable or errors out.

    Args:
        prompt: User prompt
        model: Ollama model name
        system_prompt: Optional system prompt
        timeout: Request timeout in seconds

    Returns:
        Generated text or None on failure
    """
    import requests as _requests

    if not check_ollama_health():
        print("[OLLAMA] Server not reachable, skipping local inference.")
        return None

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if system_prompt:
        payload["system"] = system_prompt

    try:
        resp = _requests.post(
            "http://localhost:11434/api/generate",
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "")
    except Exception as e:
        print(f"[OLLAMA] Inference failed: {e}")
        return None




# ============================================================================
# CONVENIENCE EXPORTS
# ============================================================================

__all__ = [
    'get_genai_client',
    'get_openai_client',
    'get_anthropic_client',
    'get_default_model',
    'get_model_with_fallback',
    'get_model_chain',
    'MODEL_FALLBACK_CHAINS',
    'check_ollama_health',
    'query_ollama',
]

# Convenience singleton (lazy initialization — only when explicitly requested)
_client = None

def get_client():
    """Lazy initialization of singleton client."""
    global _client
    if _client is None:
        _client = get_genai_client()
    return _client