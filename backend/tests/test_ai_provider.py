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
    
    import config
    import importlib
    importlib.reload(config)
    
    from services.ai_provider import ask_ai, get_ai_status
    
    status = get_ai_status()
    assert status["provider"] == "ollama"
    assert status["model"] == "llama3:8b"
    assert status["available"] is False
    
    resp = ask_ai("Explain the discrepancy in my return")
    assert "Ollama is not running" in resp or "not reachable" in resp.lower()

def test_ai_provider_hosted_mock(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "hosted")
    monkeypatch.setenv("HOSTED_AI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("HOSTED_AI_API_KEY", "sk-mock-key")
    monkeypatch.setenv("HOSTED_AI_MODEL", "gpt-4o-mini")
    
    import config
    import importlib
    importlib.reload(config)
    
    from services.ai_provider import ask_ai, get_ai_status
    
    status = get_ai_status()
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
        
        reply = ask_ai("Explain GST analytics")
        assert reply == "Here is an analysis of your return."
