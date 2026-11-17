import os
import sys

# Ensure backend directory is in sys.path
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Configure environment overrides for serverless read-only environment
os.environ["APP_ENV"] = os.getenv("APP_ENV", "production")
if os.getenv("VERCEL"):
    os.environ.setdefault("DATA_DIR", "/tmp/data")
    os.environ.setdefault("DATABASE_PATH", "/tmp/data/gst_intelligence.db")
    os.environ.setdefault("UPLOAD_DIR", "/tmp/data/uploads")
    os.environ.setdefault("OUTPUT_DIR", "/tmp/data/output")
    os.environ.setdefault("BACKUP_DIR", "/tmp/data/backups")

# Import the WSGI Flask app
from main import app
from database import init_db

# Initialize database tables on serverless cold-start
try:
    init_db()
except Exception as e:
    print(f"[VERCEL COLD-START] DB Init Notice: {e}")
