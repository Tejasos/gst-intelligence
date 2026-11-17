import os
import sys
import tempfile
from pathlib import Path

# Ensure backend directory is in sys.path
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Configure environment overrides for serverless environment
# Uses /tmp on Vercel/Linux, or %TEMP% on Windows
temp_dir = str(Path(tempfile.gettempdir()) / "gst_data")

os.environ["APP_ENV"] = os.getenv("APP_ENV", "production")
os.environ.setdefault("DATA_DIR", temp_dir)
os.environ.setdefault("DATABASE_PATH", str(Path(temp_dir) / "gst_intelligence.db"))
os.environ.setdefault("UPLOAD_DIR", str(Path(temp_dir) / "uploads"))
os.environ.setdefault("OUTPUT_DIR", str(Path(temp_dir) / "output"))
os.environ.setdefault("BACKUP_DIR", str(Path(temp_dir) / "backups"))

# Import the WSGI Flask app
from main import app
from database import init_db

# Initialize database tables on serverless cold-start
try:
    init_db()
except Exception as e:
    print(f"[VERCEL COLD-START] DB Init Notice: {e}")

# Safe diagnostic logging at serverless entrypoint (no tokens, no bodies)
class DiagnosticLoggingMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        method = environ.get("REQUEST_METHOD", "UNKNOWN")
        path = environ.get("PATH_INFO", "")
        qs = environ.get("QUERY_STRING", "")
        
        status_holder = ["unknown"]
        def logging_start_response(status, response_headers, exc_info=None):
            status_holder[0] = status
            return start_response(status, response_headers, exc_info)

        result = self.wsgi_app(environ, logging_start_response)
        resolved = environ.get("PATH_INFO", path)
        print(f"[VERCEL-ENTRY] {method} {path} (resolved: {resolved}) -> {status_holder[0]}")
        return result

app.wsgi_app = DiagnosticLoggingMiddleware(app.wsgi_app)
