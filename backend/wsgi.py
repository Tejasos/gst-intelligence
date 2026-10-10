"""
WSGI entrypoint for production application servers (Gunicorn, Waitress, uWSGI).
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from main import app

# Standard WSGI aliases
application = app

if __name__ == "__main__":
    from config import Config
    import waitress
    port = int(os.getenv("PORT", "8000"))
    print(f"Starting Waitress production server on port {port}...")
    waitress.serve(app, host="0.0.0.0", port=port)
