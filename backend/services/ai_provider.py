import json
import logging
from typing import Dict, Any, Generator
import httpx
import config

logger = logging.getLogger(__name__)

def get_ai_status() -> Dict[str, Any]:
    """Check AI provider configuration and availability."""
    provider = config.Config.AI_PROVIDER
    if provider == "hosted":
        model = config.Config.HOSTED_AI_MODEL
        has_key = bool(config.Config.HOSTED_AI_API_KEY)
        return {
            "provider": "hosted",
            "model": model,
            "base_url": config.Config.HOSTED_AI_BASE_URL,
            "available": has_key,
            "configured": has_key,
            "message": "Hosted AI provider configured" if has_key else "HOSTED_AI_API_KEY is not configured"
        }
    else:  # default: ollama
        base_url = config.Config.OLLAMA_BASE_URL
        model = config.Config.OLLAMA_MODEL
        available = False
        try:
            with httpx.Client(timeout=3.0) as client:
                r = client.get(f"{base_url}/api/tags")
                if r.status_code == 200:
                    models = [m.get("name", "") for m in r.json().get("models", [])]
                    available = any(model.split(":")[0] in m for m in models) or len(models) > 0
        except Exception:
            available = False

        return {
            "provider": "ollama",
            "model": model,
            "base_url": base_url,
            "available": available,
            "message": "Ollama service online" if available else "Ollama is not running or unreachable"
        }

def ask_ai(prompt: str) -> str:
    """Send prompt to the configured AI provider (Ollama or hosted LLM)."""
    provider = config.Config.AI_PROVIDER
    
    if provider == "hosted":
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
            "messages": [
                {"role": "user", "content": prompt}
            ],
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

    else:  # Ollama provider
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
            return (
                "⚠️ **Ollama is not running.**\n\n"
                "Start Ollama with: `ollama serve`\n"
                f"Then pull the model: `ollama pull {model}`\n\n"
                "**Note:** For numeric questions (tax, ITC, sales figures), answers are computed "
                "directly from your return without requiring an AI model."
            )
        except httpx.TimeoutException:
            return "⚠️ The AI model took too long to respond. Try asking a more specific question."
        except Exception as exc:
            logger.exception("Ollama call failed: %s", exc)
            return f"⚠️ An error occurred while contacting Ollama: {exc}"

def stream_ai(prompt: str) -> Generator[str, None, None]:
    """Stream token generator for the configured AI provider."""
    provider = config.Config.AI_PROVIDER
    
    if provider == "hosted":
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
            yield f"⚠️ AI stream error: {exc}"
            
    else:  # Ollama provider
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
            yield f"⚠️ Ollama is not running. Start: `ollama serve` and pull: `ollama pull {model}`."
        except Exception as exc:
            yield f"⚠️ AI stream error: {exc}"
