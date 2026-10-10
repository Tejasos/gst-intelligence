import os
import tempfile
import pytest

def test_storage_validation_and_saving(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        upload_dir = os.path.join(tmpdir, "uploads")
        output_dir = os.path.join(tmpdir, "output")
        monkeypatch.setenv("UPLOAD_DIR", upload_dir)
        monkeypatch.setenv("OUTPUT_DIR", output_dir)
        
        import config
        import importlib
        importlib.reload(config)
        
        from services.storage_service import validate_pdf_content, validate_excel_content, save_uploaded_file, get_upload_path
        
        # 1. Valid PDF magic bytes
        valid_pdf_bytes = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        assert validate_pdf_content(valid_pdf_bytes) is True
        
        # 2. Fake PDF (text disguised as pdf)
        fake_pdf_bytes = b"Hello world, I am not a real PDF file!"
        assert validate_pdf_content(fake_pdf_bytes) is False
        
        # 3. Valid Excel signature
        valid_excel_bytes = b"PK\x03\x04\x14\x00\x06\x00\x08\x00"
        assert validate_excel_content(valid_excel_bytes) is True
        assert validate_excel_content(b"not a zip file") is False
        
        # 4. Save uploaded file with path traversal attempt in filename
        malicious_filename = "../../../etc/passwd.pdf"
        file_id, saved_path = save_uploaded_file(valid_pdf_bytes, malicious_filename)
        
        assert os.path.exists(saved_path)
        # Saved path must be strictly inside upload_dir
        assert os.path.dirname(os.path.abspath(saved_path)) == os.path.abspath(upload_dir)
        # Resolved path matches
        assert get_upload_path(file_id) == saved_path
