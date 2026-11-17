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
