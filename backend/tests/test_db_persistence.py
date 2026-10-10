import os
import tempfile
import pytest

def test_sqlite_persistence_across_restarts(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_gst.db")
        monkeypatch.setenv("DATABASE_PATH", db_path)
        monkeypatch.setenv("DATA_DIR", tmpdir)
        
        import config
        import importlib
        importlib.reload(config)
        
        from database import init_db, get_db_connection
        init_db(db_path)
        
        # Verify WAL mode and foreign keys
        with get_db_connection(db_path) as conn:
            mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            fk = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
            assert mode.lower() == "wal"
            assert fk == 1
        
        # Instantiate store and write records
        from store import AppStore
        store1 = AppStore(db_path=db_path)
        
        file_id = "test-file-uuid-001"
        store1.add_file(file_id, "GSTR1_Apr2023.pdf", "GSTR-1", "April 2023")
        store1.set_extracted_data(file_id, {"b2b_taxable_value": 1500000.0, "period": "April 2023"})
        store1.set_analytics(file_id, {"total_turnover": 1500000.0, "kpis": []})
        store1.mark_file_ready(file_id)
        
        store1.set_reconciliation("April 2023", {"turnover_diff": 0.0, "status": "MATCH"})
        store1.add_message("user", "What is my total turnover?")
        store1.add_message("assistant", "Your turnover is ₹15,00,000.00")
        
        # Simulate restart: Instantiate brand new store2 pointing to the same db
        store2 = AppStore(db_path=db_path)
        
        # Check files list and dict
        assert file_id in store2.files
        assert store2.files[file_id]["filename"] == "GSTR1_Apr2023.pdf"
        assert store2.files[file_id]["status"] == "ready"
        assert store2.files[file_id]["period"] == "April 2023"
        
        # Check extracted data
        ext = store2.get_extracted_data(file_id)
        assert ext is not None
        assert ext["b2b_taxable_value"] == 1500000.0
        
        # Check analytics
        analytics = store2.get_analytics(file_id)
        assert analytics is not None
        assert analytics["total_turnover"] == 1500000.0
        
        # Check reconciliation
        recon = store2.get_reconciliation("April 2023")
        assert recon is not None
        assert recon["status"] == "MATCH"
        
        # Check chat history
        chat = store2.get_chat_history()
        assert len(chat) == 2
        assert chat[0]["role"] == "user"
        assert chat[1]["content"] == "Your turnover is ₹15,00,000.00"

def test_backup_restore(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "primary.db")
        backup_dir = os.path.join(tmpdir, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        from database import init_db
        from store import AppStore
        from services.backup_service import perform_database_backup, restore_database_backup
        
        init_db(db_path)
        store = AppStore(db_path=db_path)
        store.add_file("backup-test-id", "Test.pdf", "GSTR-3B", "May 2023")
        
        backup_file = perform_database_backup(db_path, backup_dir)
        assert os.path.exists(backup_file)
        
        # Corrupt / clear original db
        restored_db = os.path.join(tmpdir, "restored.db")
        restore_database_backup(backup_file, restored_db)
        
        store_restored = AppStore(db_path=restored_db)
        assert "backup-test-id" in store_restored.files
