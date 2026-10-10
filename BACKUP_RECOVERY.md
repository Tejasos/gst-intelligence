# GST Intelligence — Backup and Disaster Recovery Guide

## 1. Overview
The GST Intelligence persistence layer stores state across two locations on durable storage:
1. **SQLite Database** (`/app/data/gst_intelligence.db`): Contains user accounts, sessions, file metadata, extracted financial data, reconciliations, and chat messages.
2. **File Storage** (`/app/data/uploads` and `/app/data/output`): Contains uploaded GST returns and generated Excel workbooks.

---

## 2. Automated Online Backups

Because the database runs in SQLite WAL (Write-Ahead Logging) mode, copying the `.db` file directly with `cp` while transactions are occurring can result in an inconsistent snapshot. 

The application includes a built-in online backup utility utilizing Python's `sqlite3.Connection.backup()` API, which performs a non-blocking, atomic snapshot of the live database.

### Manual Backup Command
To execute a manual online backup:
```bash
# In the backend directory or container:
python -c "from services.backup_service import perform_database_backup; print('Backup created at:', perform_database_backup())"
```
Snapshots are written to the configured `BACKUP_DIR` (e.g. `/app/data/backups/gst_backup_YYYYMMDD_HHMMSS.sqlite`).

### Scheduled Automated Backups via Cron
On your host server or container, add a nightly cron task:
```bash
0 2 * * * docker compose exec -T backend python -c "from services.backup_service import perform_database_backup; perform_database_backup()"
```

---

## 3. Disaster Recovery and Restoration Procedure

### Step 1: Stop the Application
Stop the web service to prevent incoming write transactions during recovery:
```bash
docker compose stop backend
```

### Step 2: Select the Backup Snapshot
Locate the desired backup snapshot in your backup directory:
```bash
ls -lt /app/data/backups/
# Example: gst_backup_20261010_020000.sqlite
```

### Step 3: Execute Restoration
Use the restoration utility:
```bash
python -c "from services.backup_service import restore_database_backup; restore_database_backup('/app/data/backups/gst_backup_20261010_020000.sqlite', '/app/data/gst_intelligence.db')"
```

Alternatively, copy the snapshot directly to replace the target database file when the backend is stopped:
```bash
cp /app/data/backups/gst_backup_20261010_020000.sqlite /app/data/gst_intelligence.db
# Remove leftover WAL/SHM temporary files if present
rm -f /app/data/gst_intelligence.db-wal /app/data/gst_intelligence.db-shm
```

### Step 4: Restart and Verify
1. Restart the backend service:
   ```bash
   docker compose start backend
   ```
2. Verify system readiness:
   ```bash
   curl http://localhost:8000/api/ready
   ```
   Expected response:
   ```json
   {"database": "ok", "status": "ready", "storage": "ok"}
   ```
3. Log into the application and confirm that files, periods, and audit reports are present.

---

## 4. Retention Policy
- Retain daily database backups for **30 days**.
- Export weekly off-site backups to external secure object storage (e.g. AWS S3 Glacier, Backblaze B2, or Cloudflare R2).
- Uploaded GST return PDFs and generated workbooks should be archived or purged according to organizational data retention guidelines.
