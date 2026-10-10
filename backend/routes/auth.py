from functools import wraps
from flask import Blueprint, request, jsonify, g
from config import Config
from store import store
from services.auth_service import register_user, authenticate_user, validate_session, terminate_session

auth_bp = Blueprint("auth", __name__)

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif "X-Auth-Token" in request.headers:
            token = request.headers["X-Auth-Token"].strip()
            
        user = validate_session(token) if token else None
        
        if not user:
            guest_id = request.headers.get("X-Guest-ID", "").strip() or "default_user"
            if not Config.AUTH_REQUIRED or Config.ALLOW_GUEST_ACCESS:
                user = {"id": guest_id, "username": "Guest", "email": "guest@gst-intelligence.app", "is_guest": True}
            else:
                return jsonify(error="Authentication required. Please sign in or register to upload returns.", code="UNAUTHORIZED"), 401
                
        g.current_user = user
        store.current_user_id = user["id"]
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.post("/auth/register")
def register():
    data = request.get_json() or {}
    username = data.get("username", "")
    email = data.get("email", "")
    password = data.get("password", "")
    
    if not username or not email or not password:
        return jsonify(error="Username, email, and password are required"), 400
        
    try:
        user = register_user(username, email, password)
        session = authenticate_user(email, password)
        return jsonify(user=user, token=session["token"]), 201
    except ValueError as e:
        return jsonify(error=str(e)), 400


@auth_bp.post("/auth/login")
def login():
    data = request.get_json() or {}
    identifier = data.get("email") or data.get("username") or ""
    password = data.get("password", "")
    
    if not identifier or not password:
        return jsonify(error="Email/username and password are required"), 400
        
    session = authenticate_user(identifier, password)
    if not session:
        return jsonify(error="Invalid email or password"), 401
        
    return jsonify(session), 200


@auth_bp.post("/auth/logout")
def logout():
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""
    if token:
        terminate_session(token)
    return jsonify(status="logged_out"), 200


@auth_bp.get("/auth/me")
@require_auth
def me():
    if g.current_user.get("is_guest"):
        return jsonify(error="Authentication required", code="UNAUTHORIZED"), 401
    return jsonify(user=g.current_user), 200
