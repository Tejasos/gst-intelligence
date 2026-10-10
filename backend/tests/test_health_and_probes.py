import pytest

def test_health_and_readiness_endpoints():
    from main import app
    client = app.test_client()
    
    # 1. Health endpoint
    health_res = client.get("/api/health")
    assert health_res.status_code == 200
    assert health_res.get_json()["status"] == "ok"
    
    # 2. Readiness endpoint
    ready_res = client.get("/api/ready")
    assert ready_res.status_code == 200
    ready_data = ready_res.get_json()
    assert ready_data["status"] == "ready"
    assert ready_data["database"] == "ok"
    assert ready_data["storage"] == "ok"

def test_wsgi_entrypoint_exists():
    import wsgi
    assert hasattr(wsgi, "app")
    assert hasattr(wsgi, "application")
