import json
import logging
import time
from typing import Dict, Any, Generator, Tuple
import httpx
import config

logger = logging.getLogger(__name__)

# Cache for Ollama reachability check to prevent repeated connection latency
_ollama_cache = {
    "last_check": 0.0,
    "is_available": False,
}

def check_ollama_available(force: bool = False) -> bool:
    """Check if local Ollama daemon is reachable and responding."""
    now = time.time()
    if not force and (now - _ollama_cache["last_check"] < 10.0):
        return _ollama_cache["is_available"]

    base_url = config.Config.OLLAMA_BASE_URL
    is_up = False
    try:
        with httpx.Client(timeout=1.5) as client:
            r = client.get(f"{base_url}/api/tags")
            if r.status_code == 200:
                is_up = True
    except Exception:
        is_up = False

    _ollama_cache["last_check"] = now
    _ollama_cache["is_available"] = is_up
    return is_up


def resolve_ai_provider() -> Tuple[str, bool]:
    """
    Determine the active AI provider.
    Returns: (provider_name, is_fallback)
    where provider_name is 'openrouter', 'hosted', or 'ollama'.
    """
    configured = config.Config.AI_PROVIDER.lower()
    has_openrouter = bool(config.Config.OPENROUTER_API_KEY)
    has_hosted = bool(config.Config.HOSTED_AI_API_KEY)

    if configured == "openrouter":
        return ("openrouter", False)

    if configured == "hosted":
        return ("hosted", False)

    # For 'ollama' or 'auto'
    if check_ollama_available():
        return ("ollama", False)

    # Ollama is not available — check fallback options
    if has_openrouter and config.Config.AI_FALLBACK_TO_OPENROUTER:
        return ("openrouter", True)

    if has_hosted:
        return ("hosted", True)

    return ("ollama", False)


def get_ai_status() -> Dict[str, Any]:
    """Check AI provider configuration, reachability, and fallback state."""
    active_provider, is_fallback = resolve_ai_provider()
    configured_provider = config.Config.AI_PROVIDER
    ollama_up = check_ollama_available()
    openrouter_configured = bool(config.Config.OPENROUTER_API_KEY)
    hosted_configured = bool(config.Config.HOSTED_AI_API_KEY)

    if active_provider == "openrouter":
        return {
            "provider": "openrouter",
            "active_provider": "openrouter",
            "configured_provider": configured_provider,
            "model": config.Config.OPENROUTER_MODEL,
            "base_url": config.Config.OPENROUTER_BASE_URL,
            "available": openrouter_configured,
            "is_fallback": is_fallback,
            "ollama_available": ollama_up,
            "openrouter_available": openrouter_configured,
            "message": (
                f"Using OpenRouter ({config.Config.OPENROUTER_MODEL}) as fallback — Ollama offline"
                if is_fallback else
                "OpenRouter online and configured"
                if openrouter_configured else
                "OPENROUTER_API_KEY is not configured"
            ),
        }
    elif active_provider == "hosted":
        return {
            "provider": "hosted",
            "active_provider": "hosted",
            "configured_provider": configured_provider,
            "model": config.Config.HOSTED_AI_MODEL,
            "base_url": config.Config.HOSTED_AI_BASE_URL,
            "available": hosted_configured,
            "is_fallback": is_fallback,
            "ollama_available": ollama_up,
            "message": (
                f"Using Hosted AI ({config.Config.HOSTED_AI_MODEL}) as fallback — Ollama offline"
                if is_fallback else
                "Hosted AI provider configured"
                if hosted_configured else
                "HOSTED_AI_API_KEY is not configured"
            ),
        }
    else:  # ollama
        return {
            "provider": "ollama",
            "active_provider": "ollama",
            "configured_provider": configured_provider,
            "model": config.Config.OLLAMA_MODEL,
            "base_url": config.Config.OLLAMA_BASE_URL,
            "available": ollama_up,
            "is_fallback": False,
            "ollama_available": ollama_up,
            "openrouter_available": openrouter_configured,
            "message": "Ollama service online" if ollama_up else "Ollama is not running or unreachable",
        }


def _call_openrouter(prompt: str) -> str:
    """Execute single prompt against OpenRouter API."""
    api_key = config.Config.OPENROUTER_API_KEY
    if not api_key:
        return (
            "⚠️ **OpenRouter is selected but `OPENROUTER_API_KEY` is not set.**\n\n"
            "Please configure `OPENROUTER_API_KEY` in your environment or Railway variables.\n\n"
            "**Note:** For numeric questions (tax, ITC, sales figures), answers are computed "
            "directly from your return without requiring an AI model."
        )

    base_url = config.Config.OPENROUTER_BASE_URL
    url = f"{base_url}/chat/completions" if not base_url.endswith("/chat/completions") else base_url
    model = config.Config.OPENROUTER_MODEL
    timeout = config.Config.OPENROUTER_TIMEOUT

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": config.Config.OPENROUTER_SITE_URL,
        "X-Title": config.Config.OPENROUTER_SITE_NAME,
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 1024,
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
    except httpx.ConnectError:
        return f"⚠️ **OpenRouter unreachable.** Failed to connect to `{base_url}`."
    except httpx.HTTPStatusError as exc:
        return f"⚠️ **OpenRouter API error:** HTTP {exc.response.status_code}: {exc.response.text}"
    except Exception as exc:
        logger.exception("OpenRouter request failed: %s", exc)
        return f"⚠️ An error occurred while contacting OpenRouter: {exc}"


def _stream_openrouter(prompt: str) -> Generator[str, None, None]:
    """Stream token generator from OpenRouter SSE endpoint."""
    api_key = config.Config.OPENROUTER_API_KEY
    if not api_key:
        yield "⚠️ OpenRouter is enabled but `OPENROUTER_API_KEY` is not set."
        return

    base_url = config.Config.OPENROUTER_BASE_URL
    url = f"{base_url}/chat/completions" if not base_url.endswith("/chat/completions") else base_url
    model = config.Config.OPENROUTER_MODEL
    timeout = config.Config.OPENROUTER_TIMEOUT

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": config.Config.OPENROUTER_SITE_URL,
        "X-Title": config.Config.OPENROUTER_SITE_NAME,
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "stream": True,
        "max_tokens": 1024,
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            with client.stream("POST", url, json=payload, headers=headers) as response:
                for line in response.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    chunk_str = line[6:].strip()
                    if chunk_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(chunk_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        token = delta.get("content", "")
                        if token:
                            yield token
                    except json.JSONDecodeError:
                        continue
    except Exception as exc:
        yield f"⚠️ OpenRouter stream error: {exc}"


def _call_hosted(prompt: str) -> str:
    """Execute single prompt against OpenAI-compatible hosted provider."""
    base_url = config.Config.HOSTED_AI_BASE_URL
    api_key = config.Config.HOSTED_AI_API_KEY
    model = config.Config.HOSTED_AI_MODEL
    timeout = config.Config.HOSTED_AI_TIMEOUT

    if not api_key:
        return (
            "⚠️ **Hosted AI is selected but no API key was provided.**\n\n"
            "Please set `HOSTED_AI_API_KEY` in your environment or `.env` file.\n\n"
            "**Note:** For numeric questions (tax, ITC, sales figures), answers are computed "
            "directly from your return without requiring an AI model."
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 1024
    }
    try:
        url = f"{base_url}/chat/completions" if not base_url.endswith("/chat/completions") else base_url
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
    except httpx.ConnectError:
        return f"⚠️ **Hosted AI provider unreachable.** Failed to connect to `{base_url}`."
    except httpx.HTTPStatusError as exc:
        return f"⚠️ **Hosted AI API error:** HTTP {exc.response.status_code}: {exc.response.text}"
    except Exception as exc:
        logger.exception("Hosted AI call failed: %s", exc)
        return f"⚠️ An error occurred while contacting the AI service: {exc}"


def _stream_hosted(prompt: str) -> Generator[str, None, None]:
    """Stream token generator for OpenAI-compatible hosted provider."""
    base_url = config.Config.HOSTED_AI_BASE_URL
    api_key = config.Config.HOSTED_AI_API_KEY
    model = config.Config.HOSTED_AI_MODEL
    timeout = config.Config.HOSTED_AI_TIMEOUT

    if not api_key:
        yield "⚠️ Hosted AI is enabled but HOSTED_AI_API_KEY is not configured."
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "stream": True,
        "max_tokens": 1024
    }
    try:
        url = f"{base_url}/chat/completions" if not base_url.endswith("/chat/completions") else base_url
        with httpx.Client(timeout=timeout) as client:
            with client.stream("POST", url, json=payload, headers=headers) as response:
                for line in response.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    chunk_str = line[6:].strip()
                    if chunk_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(chunk_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        token = delta.get("content", "")
                        if token:
                            yield token
                    except json.JSONDecodeError:
                        continue
    except Exception as exc:
        yield f"⚠️ Hosted AI stream error: {exc}"


def ask_ai(prompt: str) -> str:
    """Send prompt to the active AI provider (Ollama, OpenRouter, or hosted LLM)."""
    active_provider, is_fallback = resolve_ai_provider()

    if active_provider == "openrouter":
        return _call_openrouter(prompt)

    if active_provider == "hosted":
        return _call_hosted(prompt)

    # Otherwise Ollama
    base_url = config.Config.OLLAMA_BASE_URL
    model = config.Config.OLLAMA_MODEL
    timeout = config.Config.OLLAMA_TIMEOUT

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "top_p": 0.9, "num_predict": 1024},
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(f"{base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()
    except httpx.ConnectError:
        # If Ollama failed and OpenRouter is configured, try immediate fallback
        if config.Config.OPENROUTER_API_KEY and config.Config.AI_FALLBACK_TO_OPENROUTER:
            logger.info("Ollama unreachable at %s, falling back to OpenRouter", base_url)
            return _call_openrouter(prompt)
        if config.Config.HOSTED_AI_API_KEY:
            logger.info("Ollama unreachable at %s, falling back to Hosted AI", base_url)
            return _call_hosted(prompt)

        return (
            "⚠️ **Ollama is not running.**\n\n"
            "• **Local deployment:** Start Ollama with `ollama serve` and pull `ollama pull "
            f"{model}`\n"
            "• **Cloud deployment (Railway/Render):** Provide `OPENROUTER_API_KEY` in your "
            "environment variables to use OpenRouter without running a local Ollama daemon.\n\n"
            "**Note:** For numeric questions (tax, ITC, sales figures), answers are computed "
            "directly from your return without requiring an AI model."
        )
    except httpx.TimeoutException:
        return "⚠️ The AI model took too long to respond. Try asking a more specific question."
    except Exception as exc:
        logger.exception("Ollama call failed: %s", exc)
        return f"⚠️ An error occurred while contacting Ollama: {exc}"


def stream_ai(prompt: str) -> Generator[str, None, None]:
    """Stream token generator for the active AI provider."""
    active_provider, is_fallback = resolve_ai_provider()

    if active_provider == "openrouter":
        yield from _stream_openrouter(prompt)
        return

    if active_provider == "hosted":
        yield from _stream_hosted(prompt)
        return

    # Ollama stream
    base_url = config.Config.OLLAMA_BASE_URL
    model = config.Config.OLLAMA_MODEL
    timeout = config.Config.OLLAMA_TIMEOUT

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {"temperature": 0.1, "top_p": 0.9, "num_predict": 1024},
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            with client.stream("POST", f"{base_url}/api/generate", json=payload) as response:
                for line in response.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("response", "")
                            if token:
                                yield token
                            if chunk.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
    except httpx.ConnectError:
        if config.Config.OPENROUTER_API_KEY and config.Config.AI_FALLBACK_TO_OPENROUTER:
            logger.info("Ollama unreachable during stream at %s, falling back to OpenRouter", base_url)
            yield from _stream_openrouter(prompt)
            return
        if config.Config.HOSTED_AI_API_KEY:
            logger.info("Ollama unreachable during stream at %s, falling back to Hosted AI", base_url)
            yield from _stream_hosted(prompt)
            return

        yield (
            f"⚠️ Ollama is not running. Start with `ollama serve` and pull `ollama pull {model}`, "
            "or set `OPENROUTER_API_KEY` to use OpenRouter."
        )
    except Exception as exc:
        yield f"⚠️ AI stream error: {exc}"
