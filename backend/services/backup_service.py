import sqlite3
import os
import shutil
from datetime import datetime
from pathlib import Path
from config import Config

def perform_database_backup(db_path=None, backup_dir=None) -> str:
    """
    Perform a consistent online backup using SQLite's backup API.
    Returns the absolute path to the generated backup file.
    """
    source_path = db_path or Config.DATABASE_PATH
    dest_dir = backup_dir or Config.BACKUP_DIR
    Path(dest_dir).mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"gst_backup_{timestamp}.sqlite"
    backup_path = os.path.join(dest_dir, backup_filename)
    
    source_conn = sqlite3.connect(source_path)
    dest_conn = sqlite3.connect(backup_path)
    try:
        source_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        source_conn.close()
        
    return backup_path

def restore_database_backup(backup_file_path: str, target_db_path=None):
    """
    Restore a database snapshot into the target database path.
    """
    dest_path = target_db_path or Config.DATABASE_PATH
    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
    
    source_conn = sqlite3.connect(backup_file_path)
    dest_conn = sqlite3.connect(dest_path)
    try:
        source_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        source_conn.close()
