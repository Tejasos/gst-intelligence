import os
import tempfile
import pytest

def test_auth_service(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "auth_test.db")
        monkeypatch.setenv("DATABASE_PATH", db_path)
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-456")
        
        import config
        import importlib
        importlib.reload(config)
        
        from database import init_db
        init_db(db_path)
        
        from services.auth_service import register_user, authenticate_user, validate_session, terminate_session
        
        # 1. Register
        user = register_user("caindia", "ca@example.com", "SecurePass123!", db_path=db_path)
        assert user["username"] == "caindia"
        assert user["email"] == "ca@example.com"
        assert "password_hash" not in user
        
        # 2. Duplicate registration fails
        with pytest.raises(ValueError, match="already registered"):
            register_user("caindia", "ca2@example.com", "password", db_path=db_path)
            
        with pytest.raises(ValueError, match="already registered"):
            register_user("other", "ca@example.com", "password", db_path=db_path)
            
        # 3. Authenticate with wrong password fails
        assert authenticate_user("ca@example.com", "WrongPass", db_path=db_path) is None
        
        # 4. Authenticate with right password succeeds
        session = authenticate_user("ca@example.com", "SecurePass123!", db_path=db_path)
        assert session is not None
        assert "token" in session
        assert session["user"]["username"] == "caindia"
        
        # 5. Validate session
        valid_user = validate_session(session["token"], db_path=db_path)
        assert valid_user is not None
        assert valid_user["username"] == "caindia"
        
        # 6. Logout / terminate session
        terminate_session(session["token"], db_path=db_path)
        assert validate_session(session["token"], db_path=db_path) is None

def test_auth_api_routes(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "api_auth_test.db")
        monkeypatch.setenv("DATABASE_PATH", db_path)
        monkeypatch.setenv("AUTH_REQUIRED", "true")
        
        from main import app
        client = app.test_client()
        
        # Register
        res = client.post("/api/auth/register", json={
            "username": "auditor1",
            "email": "auditor1@tax.gov.in",
            "password": "Password999!"
        })
        assert res.status_code == 201
        data = res.get_json()
        assert "token" in data
        token = data["token"]
        
        # Access /api/auth/me with Bearer token
        me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_res.status_code == 200
        assert me_res.get_json()["user"]["username"] == "auditor1"
        
        # Access /api/auth/me without token -> 401
        unauth_res = client.get("/api/auth/me")
        assert unauth_res.status_code == 401
