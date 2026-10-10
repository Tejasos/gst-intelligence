import pytest
from unittest.mock import patch, MagicMock

def test_direct_numeric_answer_bypasses_llm():
    from services.chat_service import get_direct_answer
    
    extracted = {
        "b2b_taxable_value": 500000.0,
        "total_taxable_value": 750000.0,
        "gstin": "27AAAAA0000A1Z5",
        "period": "March 2024"
    }
    analytics = {"kpis": []}
    
    ans = get_direct_answer("What is the B2B sales?", extracted, analytics)
    assert ans is not None
    assert "₹500,000.00" in ans or "500,000" in ans
    
    gstin_ans = get_direct_answer("What is my GSTIN?", extracted, analytics)
    assert gstin_ans is not None
    assert "27AAAAA0000A1Z5" in gstin_ans


def test_ai_provider_ollama_fallback(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9999")  # Non-existent port
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("HOSTED_AI_API_KEY", "")
    
    import config
    import importlib
    importlib.reload(config)
    
    import services.ai_provider as ai_provider
    importlib.reload(ai_provider)
    
    status = ai_provider.get_ai_status()
    assert status["provider"] == "ollama"
    assert status["model"] == "llama3:8b"
    assert status["available"] is False
    
    resp = ai_provider.ask_ai("Explain the discrepancy in my return")
    assert "Ollama is not running" in resp or "not reachable" in resp.lower()


def test_ai_provider_hosted_mock(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "hosted")
    monkeypatch.setenv("HOSTED_AI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("HOSTED_AI_API_KEY", "sk-mock-key")
    monkeypatch.setenv("HOSTED_AI_MODEL", "gpt-4o-mini")
    
    import config
    import importlib
    importlib.reload(config)
    
    import services.ai_provider as ai_provider
    importlib.reload(ai_provider)
    
    status = ai_provider.get_ai_status()
    assert status["provider"] == "hosted"
    assert status["model"] == "gpt-4o-mini"
    
    # Mock httpx client response
    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Here is an analysis of your return."}}]
        }
        mock_post.return_value = mock_resp
        
        reply = ai_provider.ask_ai("Explain GST analytics")
        assert reply == "Here is an analysis of your return."


def test_ai_provider_openrouter_direct(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-mockkey")
    monkeypatch.setenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
    
    import config
    import importlib
    importlib.reload(config)
    
    import services.ai_provider as ai_provider
    importlib.reload(ai_provider)
    
    status = ai_provider.get_ai_status()
    assert status["provider"] == "openrouter"
    assert status["active_provider"] == "openrouter"
    assert status["available"] is True
    assert status["model"] == "meta-llama/llama-3.3-70b-instruct:free"
    
    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "OpenRouter insight on tax rates."}}]
        }
        mock_post.return_value = mock_resp
        
        reply = ai_provider.ask_ai("Explain GST tax rate changes")
        assert reply == "OpenRouter insight on tax rates."
        
        # Verify headers passed to OpenRouter
        called_args, called_kwargs = mock_post.call_args
        assert "Authorization" in called_kwargs["headers"]
        assert called_kwargs["headers"]["Authorization"] == "Bearer sk-or-v1-mockkey"
        assert "HTTP-Referer" in called_kwargs["headers"]


def test_ai_provider_ollama_not_present_falls_back_to_openrouter(monkeypatch):
    """When Ollama is selected but not reachable, it seamlessly falls back to OpenRouter."""
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9999")  # Unreachable port
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-fallback-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
    monkeypatch.setenv("AI_FALLBACK_TO_OPENROUTER", "true")
    
    import config
    import importlib
    importlib.reload(config)
    
    import services.ai_provider as ai_provider
    importlib.reload(ai_provider)
    
    status = ai_provider.get_ai_status()
    assert status["active_provider"] == "openrouter"
    assert status["is_fallback"] is True
    assert status["available"] is True
    assert "OpenRouter" in status["message"]
    
    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Seamless fallback answer from OpenRouter."}}]
        }
        mock_post.return_value = mock_resp
        
        reply = ai_provider.ask_ai("Explain why GSTR-3B differs from GSTR-1")
        assert reply == "Seamless fallback answer from OpenRouter."
