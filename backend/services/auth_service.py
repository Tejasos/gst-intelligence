import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db_connection
from config import Config

def register_user(username: str, email: str, password: str, db_path=None) -> Dict:
    username = username.strip()
    email = email.strip().lower()
    if not username or not email or not password:
        raise ValueError("Username, email, and password are required")
        
    password_hash = generate_password_hash(password)
    user_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    with get_db_connection(db_path) as conn:
        # Check uniqueness
        existing = conn.execute(
            "SELECT username, email FROM users WHERE username = ? OR email = ?",
            (username, email)
        ).fetchone()
        if existing:
            if existing["username"] == username:
                raise ValueError(f"Username '{username}' is already registered")
            raise ValueError(f"Email '{email}' is already registered")
            
        conn.execute(
            "INSERT INTO users (id, username, email, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, email, password_hash, now)
        )
        
    return {
        "id": user_id,
        "username": username,
        "email": email,
        "created_at": now
    }

def authenticate_user(identifier: str, password: str, db_path=None) -> Optional[Dict]:
    identifier = identifier.strip().lower()
    with get_db_connection(db_path) as conn:
        row = conn.execute(
            "SELECT id, username, email, password_hash, created_at FROM users WHERE lower(email) = ? OR lower(username) = ?",
            (identifier, identifier)
        ).fetchone()
        
        if not row:
            return None
            
        if not check_password_hash(row["password_hash"], password):
            return None
            
        token = secrets.token_urlsafe(32)
        now = datetime.now()
        expires_at = (now + timedelta(hours=Config.SESSION_EXPIRY_HOURS)).isoformat()
        
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (token, row["id"], expires_at, now.isoformat())
        )
        
        return {
            "token": token,
            "expires_at": expires_at,
            "user": {
                "id": row["id"],
                "username": row["username"],
                "email": row["email"],
                "created_at": row["created_at"]
            }
        }

def validate_session(token: str, db_path=None) -> Optional[Dict]:
    if not token:
        return None
        
    now = datetime.now().isoformat()
    with get_db_connection(db_path) as conn:
        row = conn.execute(
            """SELECT u.id, u.username, u.email, u.created_at, s.expires_at
               FROM sessions s
               JOIN users u ON s.user_id = u.id
               WHERE s.token = ? AND s.expires_at > ?""",
            (token, now)
        ).fetchone()
        
        if not row:
            return None
            
        return {
            "id": row["id"],
            "username": row["username"],
            "email": row["email"],
            "created_at": row["created_at"]
        }

def terminate_session(token: str, db_path=None):
    if not token:
        return
    with get_db_connection(db_path) as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
