import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
_BASE_DIR = Path(__file__).resolve().parent
load_dotenv(_BASE_DIR / ".env")
load_dotenv(_BASE_DIR.parent / ".env")

class Config:
    APP_ENV = os.getenv("APP_ENV", "development").lower()
    DEBUG = APP_ENV == "development"
    
    # Secrets
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-gst-intelligence-secret-change-in-production")
    
    # Storage and Persistence
    DATA_DIR = os.getenv("DATA_DIR", str(_BASE_DIR / "data"))
    DATABASE_PATH = os.getenv("DATABASE_PATH", str(Path(DATA_DIR) / "gst_intelligence.db"))
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", str(Path(DATA_DIR) / "uploads"))
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", str(Path(DATA_DIR) / "output"))
    BACKUP_DIR = os.getenv("BACKUP_DIR", str(Path(DATA_DIR) / "backups"))
    
    # Security & CORS
    ALLOWED_ORIGINS = [
        origin.strip()
        for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
        if origin.strip()
    ]
    AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "true").lower() in ("true", "1", "yes")
    SESSION_EXPIRY_HOURS = int(os.getenv("SESSION_EXPIRY_HOURS", "72"))
    
    # AI Provider Configuration
    AI_PROVIDER = os.getenv("AI_PROVIDER", "ollama").lower()
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:8b")
    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))
    
    # Hosted AI Provider
    HOSTED_AI_BASE_URL = os.getenv("HOSTED_AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    HOSTED_AI_API_KEY = os.getenv("HOSTED_AI_API_KEY", "")
    HOSTED_AI_MODEL = os.getenv("HOSTED_AI_MODEL", "gpt-4o-mini")
    HOSTED_AI_TIMEOUT = int(os.getenv("HOSTED_AI_TIMEOUT", "60"))
    
    # File limits
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024

    @classmethod
    def ensure_directories(cls):
        for directory in [Path(cls.DATABASE_PATH).parent, Path(cls.UPLOAD_DIR), Path(cls.OUTPUT_DIR), Path(cls.BACKUP_DIR)]:
            os.makedirs(directory, exist_ok=True)
