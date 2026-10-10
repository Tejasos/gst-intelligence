import os
import uuid
from pathlib import Path
from typing import Tuple, Optional
import config

def get_upload_dir() -> Path:
    d = Path(config.Config.UPLOAD_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d

def get_output_dir() -> Path:
    d = Path(config.Config.OUTPUT_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d

def validate_pdf_content(content: bytes) -> bool:
    """Validate that the binary content begins with the PDF magic header."""
    if not content or len(content) < 5:
        return False
    return content[:1024].lstrip().startswith(b"%PDF")

def validate_excel_content(content: bytes) -> bool:
    """Validate that the binary content begins with PK zip signature (used by .xlsx)."""
    if not content or len(content) < 4:
        return False
    return content.startswith(b"PK\x03\x04")

def save_uploaded_file(content: bytes, original_filename: str = "", upload_dir=None) -> Tuple[str, str]:
    """
    Save uploaded bytes with a server-generated UUID to prevent path traversal.
    Returns (file_id, saved_absolute_path).
    """
    file_id = str(uuid.uuid4())
    dest_dir = Path(upload_dir) if upload_dir else get_upload_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    dest_path = dest_dir / f"{file_id}.pdf"
    with open(dest_path, "wb") as f:
        f.write(content)
        
    return file_id, str(dest_path.resolve())

def get_upload_path(file_id: str, upload_dir=None) -> Optional[str]:
    """Retrieve full path to uploaded PDF file by file_id."""
    clean_id = os.path.basename(file_id)
    dest_dir = Path(upload_dir) if upload_dir else get_upload_dir()
    candidate = dest_dir / f"{clean_id}.pdf"
    if candidate.exists():
        return str(candidate.resolve())
    alt = dest_dir / clean_id
    if alt.exists():
        return str(alt.resolve())
    return str(candidate.resolve())

def get_output_path(filename: str, output_dir=None) -> str:
    """Generate safe destination path inside output directory."""
    clean_filename = os.path.basename(filename)
    dest_dir = Path(output_dir) if output_dir else get_output_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    return str((dest_dir / clean_filename).resolve())

def delete_upload_file(file_id: str, upload_dir=None):
    """Safely delete uploaded file from disk."""
    clean_id = os.path.basename(file_id)
    dest_dir = Path(upload_dir) if upload_dir else get_upload_dir()
    target = dest_dir / f"{clean_id}.pdf"
    if target.exists():
        try:
            target.unlink()
        except OSError:
            pass
