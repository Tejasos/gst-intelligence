import os
import tempfile
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
    IS_VERCEL = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
    _TEMP_GST_DATA = str(Path(tempfile.gettempdir()) / "gst_data")
    _DEFAULT_DATA_DIR = _TEMP_GST_DATA if IS_VERCEL else str(_BASE_DIR / "data")
    
    _raw_data = os.getenv("DATA_DIR", _DEFAULT_DATA_DIR)
    DATA_DIR = _TEMP_GST_DATA if (IS_VERCEL and (not _raw_data or _raw_data.startswith("/app") or not _raw_data.startswith(tempfile.gettempdir()))) else _raw_data

    @staticmethod
    def _clean_path(val: str, default_path: str, is_vercel: bool) -> str:
        if is_vercel:
            if not val or val.startswith("/app") or not val.startswith(tempfile.gettempdir()):
                return default_path
            return val
        return val if val else default_path

    DATABASE_PATH = _clean_path(os.getenv("DATABASE_PATH"), str(Path(DATA_DIR) / "gst_intelligence.db"), IS_VERCEL)
    UPLOAD_DIR    = _clean_path(os.getenv("UPLOAD_DIR"),    str(Path(DATA_DIR) / "uploads"),             IS_VERCEL)
    OUTPUT_DIR    = _clean_path(os.getenv("OUTPUT_DIR"),    str(Path(DATA_DIR) / "output"),              IS_VERCEL)
    BACKUP_DIR    = _clean_path(os.getenv("BACKUP_DIR"),    str(Path(DATA_DIR) / "backups"),             IS_VERCEL)

    # Sync sanitized paths back to os.environ so child modules/subprocesses see them
    if IS_VERCEL:
        os.environ["DATA_DIR"] = DATA_DIR
        os.environ["DATABASE_PATH"] = DATABASE_PATH
        os.environ["UPLOAD_DIR"] = UPLOAD_DIR
        os.environ["OUTPUT_DIR"] = OUTPUT_DIR
        os.environ["BACKUP_DIR"] = BACKUP_DIR

    # File limits (Vercel serverless hard limit is 4.5 MB)
    MAX_UPLOAD_MB = 4.5 if IS_VERCEL else float(os.getenv("MAX_UPLOAD_MB", "50"))
    MAX_CONTENT_LENGTH = int(MAX_UPLOAD_MB * 1024 * 1024)
    
    # Security & CORS
    ALLOWED_ORIGINS = [
        origin.strip()
        for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
        if origin.strip()
    ]
    AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "false").lower() in ("true", "1", "yes")
    ALLOW_GUEST_ACCESS = os.getenv("ALLOW_GUEST_ACCESS", "true").lower() in ("true", "1", "yes")
    SESSION_EXPIRY_HOURS = int(os.getenv("SESSION_EXPIRY_HOURS", "72"))
    
    # AI Provider Configuration
    AI_PROVIDER = os.getenv("AI_PROVIDER", "ollama").lower()
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:8b")
    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))
    
    # OpenRouter AI Provider
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
    OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
    OPENROUTER_TIMEOUT = int(os.getenv("OPENROUTER_TIMEOUT", "60"))
    OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "https://github.com/Tejasos/gst-intelligence")
    OPENROUTER_SITE_NAME = os.getenv("OPENROUTER_SITE_NAME", "GST Intelligence")
    AI_FALLBACK_TO_OPENROUTER = os.getenv("AI_FALLBACK_TO_OPENROUTER", "true").lower() in ("true", "1", "yes")

    # Hosted AI Provider (Generic OpenAI-compatible)
    HOSTED_AI_BASE_URL = os.getenv("HOSTED_AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    HOSTED_AI_API_KEY = os.getenv("HOSTED_AI_API_KEY", "")
    HOSTED_AI_MODEL = os.getenv("HOSTED_AI_MODEL", "gpt-4o-mini")
    HOSTED_AI_TIMEOUT = int(os.getenv("HOSTED_AI_TIMEOUT", "60"))
    
    # File limits
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024

    @classmethod
    def ensure_directories(cls):
        for directory in [Path(cls.DATABASE_PATH).parent, Path(cls.UPLOAD_DIR), Path(cls.OUTPUT_DIR), Path(cls.BACKUP_DIR)]:
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as e:
                print(f"[Config] Warning creating directory {directory}: {e}")
