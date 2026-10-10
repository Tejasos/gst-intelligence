"""
GST Intelligence API — Flask entry point (Python 3.14 compatible)
"""
import os
import sys
import logging

# Allow launching as `python backend/main.py` from any cwd (e.g. launch.json).
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from flask import Flask
from flask_cors import CORS

from routes.upload         import upload_bp
from routes.chat           import chat_bp
from routes.analytics      import analytics_bp
from routes.export         import export_bp
from routes.reconciliation import recon_bp
from routes.intelligence   import intelligence_bp
from routes.gstr2b         import gstr2b_bp
from routes.gstr2a         import gstr2a_bp
from routes.auth           import auth_bp
from config import Config

Config.ensure_directories()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(),                         # console
        logging.FileHandler("backend.log", encoding="utf-8"),  # file
    ],
)

# Also redirect print() to both console and log file so debug prints are captured
import sys, builtins as _builtins

# Reconfigure stdout/stderr to UTF-8 so PDF text containing ₹ (U+20B9)
# doesn't raise a charmap codec error on Windows when print() is called.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass  # Python < 3.7 or non-TextIOWrapper stdout

_log_file = open("backend.log", "a", encoding="utf-8", buffering=1)
_orig_print = _builtins.print
def _tee_print(*args, **kwargs):
    _orig_print(*args, **kwargs)
    kwargs.pop("file", None)
    _orig_print(*args, file=_log_file, **kwargs)
_builtins.print = _tee_print

app = Flask(__name__)

# Configure CORS globally for all endpoints (supporting Vercel, Railway, and localhost)
CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    supports_credentials=False,
    allow_headers=["Content-Type", "Authorization", "X-Guest-ID", "X-Auth-Token", "X-Requested-With"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
)

class ApiPrefixAndCorsMiddleware:
    """WSGI middleware ensuring /api prefix rewriting and robust CORS headers on ALL responses."""
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path_info = environ.get("PATH_INFO", "")
        # Rewrite non-api paths to /api prefix so /upload routes to /api/upload
        if not path_info.startswith("/api/"):
            for ep in ("upload", "chat", "analytics", "export", "files", "reconciliation", "intelligence", "gstr2b", "gstr2a", "auth", "health", "ready", "session"):
                if path_info == f"/{ep}" or path_info.startswith(f"/{ep}/"):
                    environ["PATH_INFO"] = f"/api{path_info}"
                    break

        # Fast preflight handling
        if environ.get("REQUEST_METHOD") == "OPTIONS":
            origin = environ.get("HTTP_ORIGIN", "*")
            headers = [
                ("Access-Control-Allow-Origin", origin if origin else "*"),
                ("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS, HEAD, PATCH"),
                ("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Guest-ID, X-Auth-Token, X-Requested-With"),
                ("Access-Control-Max-Age", "86400"),
                ("Content-Length", "0"),
                ("Content-Type", "text/plain"),
            ]
            start_response("204 No Content", headers)
            return [b""]

        def custom_start_response(status, response_headers, exc_info=None):
            origin = environ.get("HTTP_ORIGIN", "*")
            filtered = [
                (k, v) for k, v in response_headers 
                if not k.lower().startswith("access-control-")
            ]
            filtered.extend([
                ("Access-Control-Allow-Origin", origin if origin else "*"),
                ("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS, HEAD, PATCH"),
                ("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Guest-ID, X-Auth-Token, X-Requested-With"),
                ("Access-Control-Max-Age", "86400"),
            ])
            return start_response(status, filtered, exc_info)

        return self.wsgi_app(environ, custom_start_response)

app.wsgi_app = ApiPrefixAndCorsMiddleware(app.wsgi_app)

app.register_blueprint(upload_bp,       url_prefix="/api")
app.register_blueprint(chat_bp,         url_prefix="/api")
app.register_blueprint(analytics_bp,    url_prefix="/api")
app.register_blueprint(export_bp,       url_prefix="/api")
app.register_blueprint(recon_bp,        url_prefix="/api")
app.register_blueprint(intelligence_bp, url_prefix="/api")
app.register_blueprint(gstr2b_bp,       url_prefix="/api")
app.register_blueprint(gstr2a_bp,       url_prefix="/api")
app.register_blueprint(auth_bp,         url_prefix="/api")


@app.get("/")
def root():
    return {"status": "running", "service": "GST Intelligence API", "version": "2.0.0"}


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "GST Intelligence API", "version": "2.0.0"}


@app.get("/api/ready")
def readiness():
    """Readiness probe checking database connectivity and storage health."""
    from database import get_db_connection
    status = {"status": "ready", "database": "unknown", "storage": "unknown"}
    
    # Check DB
    try:
        with get_db_connection() as conn:
            conn.execute("SELECT 1;").fetchone()
        status["database"] = "ok"
    except Exception as e:
        status["database"] = f"error: {e}"
        status["status"] = "not_ready"
        
    # Check Storage
    try:
        upload_path = os.path.abspath(Config.UPLOAD_DIR)
        os.makedirs(upload_path, exist_ok=True)
        test_file = os.path.join(upload_path, ".health_check")
        with open(test_file, "w") as f:
            f.write("ok")
        if os.path.exists(test_file):
            os.remove(test_file)
        status["storage"] = "ok"
    except Exception as e:
        status["storage"] = f"error: {e}"
        status["status"] = "not_ready"
        
    http_code = 200 if status["status"] == "ready" else 503
    return status, http_code


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=Config.DEBUG)
