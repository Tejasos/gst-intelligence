import os
import pytest

def test_default_config(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    monkeypatch.delenv("UPLOAD_DIR", raising=False)
    monkeypatch.delenv("OUTPUT_DIR", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    
    import importlib
    import config
    importlib.reload(config)
    from config import Config
    
    assert Config.APP_ENV == "development"
    assert Config.DATABASE_PATH.endswith("gst_intelligence.db")
    assert Config.UPLOAD_DIR.endswith("uploads")
    assert Config.OUTPUT_DIR.endswith("output")
    assert Config.AI_PROVIDER == "ollama"
    assert Config.OLLAMA_BASE_URL == "http://localhost:11434"

def test_override_config(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_PATH", "/durable/custom.db")
    monkeypatch.setenv("UPLOAD_DIR", "/durable/uploads")
    monkeypatch.setenv("OUTPUT_DIR", "/durable/output")
    monkeypatch.setenv("SECRET_KEY", "super-secret-key-123")
    monkeypatch.setenv("AI_PROVIDER", "hosted")
    monkeypatch.setenv("HOSTED_AI_BASE_URL", "https://api.hosted-ai.com/v1")
    monkeypatch.setenv("HOSTED_AI_API_KEY", "sk-secret-token")
    monkeypatch.setenv("HOSTED_AI_MODEL", "gpt-4o")

    from config import Config
    # Reload config
    import importlib
    import config
    importlib.reload(config)
    
    assert config.Config.APP_ENV == "production"
    assert config.Config.DATABASE_PATH == "/durable/custom.db"
    assert config.Config.UPLOAD_DIR == "/durable/uploads"
    assert config.Config.OUTPUT_DIR == "/durable/output"
    assert config.Config.SECRET_KEY == "super-secret-key-123"
    assert config.Config.AI_PROVIDER == "hosted"
    assert config.Config.HOSTED_AI_BASE_URL == "https://api.hosted-ai.com/v1"
    assert config.Config.HOSTED_AI_API_KEY == "sk-secret-token"
    assert config.Config.HOSTED_AI_MODEL == "gpt-4o"
