import io
import os
import pytest
from flask import json
from main import app
from config import Config

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_upload_missing_file_returns_400(client):
    r = client.post("/api/upload")
    assert r.status_code == 400
    data = r.get_json()
    assert "No file provided" in data["error"]
    assert "request_id" in data
    assert r.headers.get("X-Request-ID") == data["request_id"]

def test_upload_empty_filename_returns_400(client):
    data = {"file": (io.BytesIO(b""), "")}
    r = client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert r.status_code == 400
    assert "No file selected" in r.get_json()["error"]

def test_upload_invalid_extension_returns_400(client):
    data = {"file": (io.BytesIO(b"not a pdf"), "invoice.txt")}
    r = client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert r.status_code == 400
    assert "Only PDF files accepted" in r.get_json()["error"]

def test_upload_corrupt_magic_bytes_returns_400(client):
    data = {"file": (io.BytesIO(b"NOT_A_PDF_MAGIC_BYTES"), "invoice.pdf")}
    r = client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert r.status_code == 400
    assert "file signature verification failed" in r.get_json()["error"]

def test_upload_corrupt_pdf_structure_returns_400(client):
    data = {"file": (io.BytesIO(b"%PDF-1.4 garbage corruption without catalog or root"), "invoice.pdf")}
    r = client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert r.status_code == 400
    assert "Corrupted PDF file" in r.get_json()["error"]

def test_upload_unsupported_gst_format_sample_test_pdf_returns_422(client):
    if os.path.exists("sample_test.pdf"):
        with open("sample_test.pdf", "rb") as f:
            data = {"file": (f, "sample_test.pdf")}
            r = client.post("/api/upload", data=data, content_type="multipart/form-data")
            assert r.status_code == 422
            res = r.get_json()
            assert "Unsupported PDF format" in res["error"]
            assert res["form_type"] == "UNKNOWN"
            assert "request_id" in res

def test_upload_oversized_payload_returns_413(client):
    # Payload exceeding 4.5 MB
    large_size = int(4.6 * 1024 * 1024)
    data = {"file": (io.BytesIO(b"%PDF-1.4 " + b"0" * large_size), "large.pdf")}
    r = client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert r.status_code == 413
    res = r.get_json()
    assert "exceeds maximum allowed limit" in res["error"]

def test_upload_valid_gstr1_returns_200(client):
    gstr1_path = "Bengal SHRISTI/GSTR 1/GSTR 1 25-26/GSTR1_19AABCB8990N1ZV_042025.pdf"
    if os.path.exists(gstr1_path):
        with open(gstr1_path, "rb") as f:
            data = {"file": (f, "GSTR1_042025.pdf")}
            r = client.post("/api/upload", data=data, content_type="multipart/form-data", headers={"X-Request-ID": "test_req_gstr1"})
            assert r.status_code == 200
            res = r.get_json()
            assert res["gst_type"] == "GSTR-1"
            assert res["period"] == "April 2025"
            assert res["parse_success"] is True
            assert res["request_id"] == "test_req_gstr1"
            assert r.headers.get("X-Request-ID") == "test_req_gstr1"

def test_upload_valid_gstr3b_returns_200(client):
    gstr3b_path = "Bengal SHRISTI/GSTR 3B/GSTR 3B 25-26/GSTR3B_19AABCB8990N1ZV_042025.pdf"
    if os.path.exists(gstr3b_path):
        with open(gstr3b_path, "rb") as f:
            data = {"file": (f, "GSTR3B_042025.pdf")}
            r = client.post("/api/upload", data=data, content_type="multipart/form-data")
            assert r.status_code == 200
            res = r.get_json()
            assert res["gst_type"] == "GSTR-3B"
            assert res["period"] == "April 2025"
            assert res["parse_success"] is True
