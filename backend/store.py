"""
Application state store backed by durable SQLite persistence.
Supports single-user and multi-user isolation, process restarts, and multi-worker WSGI servers.
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from database import get_db_connection, init_db

logger = logging.getLogger(__name__)


class _FilesProxy(dict):
    """
    Dictionary proxy that dynamically queries the SQLite database for files,
    preserving exact compatibility with `store.files.items()`, `store.files.get()`, `in store.files`.
    """
    def __init__(self, store):
        super().__init__()
        self._store = store

    def _load_all(self) -> Dict[str, Dict]:
        with get_db_connection(self._store.db_path) as conn:
            query = "SELECT id, user_id, filename, gst_type, period, status, error, uploaded_at, is_active FROM files"
            params = []
            if self._store.current_user_id:
                query += " WHERE user_id = ? OR user_id = 'default_user' OR user_id IS NULL"
                params.append(self._store.current_user_id)
            rows = conn.execute(query, params).fetchall()
            return {
                r["id"]: {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "filename": r["filename"],
                    "gst_type": r["gst_type"],
                    "period": r["period"] or "",
                    "status": r["status"],
                    "error": r["error"],
                    "uploaded_at": r["uploaded_at"],
                    "is_active": bool(r["is_active"]),
                }
                for r in rows
            }

    def __getitem__(self, key):
        res = self.get(key)
        if res is None:
            raise KeyError(key)
        return res

    def __contains__(self, key):
        return self.get(key) is not None

    def get(self, key, default=None):
        with get_db_connection(self._store.db_path) as conn:
            row = conn.execute(
                "SELECT id, user_id, filename, gst_type, period, status, error, uploaded_at, is_active FROM files WHERE id = ?",
                (key,),
            ).fetchone()
            if not row:
                return default
            return {
                "id": row["id"],
                "user_id": row["user_id"],
                "filename": row["filename"],
                "gst_type": row["gst_type"],
                "period": row["period"] or "",
                "status": row["status"],
                "error": row["error"],
                "uploaded_at": row["uploaded_at"],
                "is_active": bool(row["is_active"]),
            }

    def items(self):
        return self._load_all().items()

    def values(self):
        return self._load_all().values()

    def keys(self):
        return self._load_all().keys()

    def __len__(self):
        return len(self._load_all())

    def __bool__(self):
        return len(self._load_all()) > 0


class AppStore:
    """Central store for all application state, persisted to SQLite."""

    def __init__(self, db_path=None):
        self.db_path = db_path
        self.current_user_id = None
        init_db(self.db_path)

    @property
    def files(self) -> _FilesProxy:
        return _FilesProxy(self)

    @property
    def active_file_id(self) -> Optional[str]:
        with get_db_connection(self.db_path) as conn:
            query = "SELECT id FROM files WHERE is_active = 1"
            params = []
            if self.current_user_id:
                query += " AND (user_id = ? OR user_id = 'default_user' OR user_id IS NULL)"
                params.append(self.current_user_id)
            query += " ORDER BY uploaded_at DESC LIMIT 1"
            row = conn.execute(query, params).fetchone()
            if row:
                return row["id"]
            # Fallback to latest file
            q2 = "SELECT id FROM files"
            p2 = []
            if self.current_user_id:
                q2 += " WHERE (user_id = ? OR user_id = 'default_user' OR user_id IS NULL)"
                p2.append(self.current_user_id)
            q2 += " ORDER BY uploaded_at DESC LIMIT 1"
            r2 = conn.execute(q2, p2).fetchone()
            return r2["id"] if r2 else None

    @active_file_id.setter
    def active_file_id(self, fid: Optional[str]):
        if fid:
            self.set_active_file(fid)

    # ── File management ────────────────────────────────────────────────────────

    def add_file(self, file_id: str, filename: str, gst_type: str, period: str = "", user_id: str = None):
        uid = user_id or self.current_user_id or "default_user"
        now = datetime.now().isoformat()
        with get_db_connection(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO files 
                   (id, user_id, filename, gst_type, period, status, uploaded_at, is_active)
                   VALUES (?, ?, ?, ?, ?, 'processing', ?, 1)""",
                (file_id, uid, filename, gst_type, period or "", now),
            )
            # Deactivate other files
            conn.execute("UPDATE files SET is_active = 0 WHERE id != ?", (file_id,))

    def mark_file_ready(self, file_id: str):
        with get_db_connection(self.db_path) as conn:
            conn.execute("UPDATE files SET status = 'ready' WHERE id = ?", (file_id,))

    def mark_file_error(self, file_id: str, error: str):
        with get_db_connection(self.db_path) as conn:
            conn.execute("UPDATE files SET status = 'error', error = ? WHERE id = ?", (error, file_id))

    def list_files(self, user_id: str = None) -> List[Dict]:
        uid = user_id or self.current_user_id
        with get_db_connection(self.db_path) as conn:
            q = "SELECT id, user_id, filename, gst_type, period, status, error, uploaded_at, is_active FROM files"
            params = []
            if uid:
                q += " WHERE user_id = ? OR user_id = 'default_user' OR user_id IS NULL"
                params.append(uid)
            q += " ORDER BY uploaded_at ASC"
            rows = conn.execute(q, params).fetchall()
            return [
                {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "filename": r["filename"],
                    "gst_type": r["gst_type"],
                    "period": r["period"] or "",
                    "status": r["status"],
                    "error": r["error"],
                    "uploaded_at": r["uploaded_at"],
                    "is_active": bool(r["is_active"]),
                }
                for r in rows
            ]

    def get_files_by_period(self, user_id: str = None) -> Dict[str, Dict]:
        groups: Dict[str, Dict] = {}
        for file_info in self.list_files(user_id):
            period   = file_info.get("period") or "Unknown Period"
            gst_type = file_info.get("gst_type") or "UNKNOWN"
            if period not in groups:
                groups[period] = {}
            groups[period][gst_type] = file_info
        return groups

    def get_period_for_file(self, file_id: str) -> Optional[str]:
        f = self.files.get(file_id)
        return f.get("period") if f else None

    def find_counterpart(self, file_id: str) -> Optional[str]:
        this_file = self.files.get(file_id)
        if not this_file:
            return None

        this_period   = this_file.get("period")
        this_gst_type = this_file.get("gst_type")

        if this_gst_type == "GSTR-1":
            counterpart_type = "GSTR-3B"
        elif this_gst_type == "GSTR-3B":
            counterpart_type = "GSTR-1"
        else:
            return None

        for fid, finfo in self.files.items():
            if fid == file_id:
                continue
            if finfo.get("period") == this_period and finfo.get("gst_type") == counterpart_type:
                return fid
        return None

    # ── Data management ────────────────────────────────────────────────────────

    def set_extracted_data(self, file_id: str, data: Dict):
        now = datetime.now().isoformat()
        with get_db_connection(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO extracted_data (file_id, data_json, updated_at) VALUES (?, ?, ?)",
                (file_id, json.dumps(data), now),
            )
        self.set_active_file(file_id)

    def get_extracted_data(self, file_id: str) -> Optional[Dict]:
        with get_db_connection(self.db_path) as conn:
            row = conn.execute("SELECT data_json FROM extracted_data WHERE file_id = ?", (file_id,)).fetchone()
            if row:
                return json.loads(row["data_json"])
            return None

    def set_analytics(self, file_id: str, analytics: Dict):
        now = datetime.now().isoformat()
        with get_db_connection(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO analytics (file_id, data_json, updated_at) VALUES (?, ?, ?)",
                (file_id, json.dumps(analytics), now),
            )

    def get_analytics(self, file_id: str) -> Optional[Dict]:
        with get_db_connection(self.db_path) as conn:
            row = conn.execute("SELECT data_json FROM analytics WHERE file_id = ?", (file_id,)).fetchone()
            if row:
                return json.loads(row["data_json"])
            return None

    # ── Reconciliation ─────────────────────────────────────────────────────────

    def set_reconciliation(self, period: str, recon: Dict, user_id: str = None):
        uid = user_id or self.current_user_id or "default_user"
        now = datetime.now().isoformat()
        with get_db_connection(self.db_path) as conn:
            conn.execute(
                """INSERT INTO reconciliations (user_id, period, data_json, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(user_id, period) DO UPDATE SET data_json=excluded.data_json, updated_at=excluded.updated_at""",
                (uid, period, json.dumps(recon), now),
            )

    def get_reconciliation(self, period: str, user_id: str = None) -> Optional[Dict]:
        uid = user_id or self.current_user_id
        with get_db_connection(self.db_path) as conn:
            q = "SELECT data_json FROM reconciliations WHERE period = ?"
            params = [period]
            if uid:
                q += " AND (user_id = ? OR user_id = 'default_user' OR user_id IS NULL)"
                params.append(uid)
            q += " ORDER BY updated_at DESC LIMIT 1"
            row = conn.execute(q, params).fetchone()
            if row:
                return json.loads(row["data_json"])
            return None

    def get_all_reconciliations(self, user_id: str = None) -> Dict[str, Dict]:
        uid = user_id or self.current_user_id
        with get_db_connection(self.db_path) as conn:
            q = "SELECT period, data_json FROM reconciliations"
            params = []
            if uid:
                q += " WHERE user_id = ? OR user_id = 'default_user' OR user_id IS NULL"
                params.append(uid)
            rows = conn.execute(q, params).fetchall()
            return {r["period"]: json.loads(r["data_json"]) for r in rows}

    # ── Chat management ────────────────────────────────────────────────────────

    def add_message(self, role: str, content: str, sources: Optional[List] = None, user_id: str = None):
        uid = user_id or self.current_user_id or "default_user"
        now = datetime.now().isoformat()
        with get_db_connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO chat_messages (user_id, role, content, sources_json, timestamp) VALUES (?, ?, ?, ?, ?)",
                (uid, role, content, json.dumps(sources or []), now),
            )

    def get_chat_history(self, user_id: str = None) -> List[Dict]:
        uid = user_id or self.current_user_id
        with get_db_connection(self.db_path) as conn:
            q = "SELECT id, role, content, sources_json, timestamp FROM chat_messages"
            params = []
            if uid:
                q += " WHERE user_id = ? OR user_id = 'default_user' OR user_id IS NULL"
                params.append(uid)
            q += " ORDER BY id ASC"
            rows = conn.execute(q, params).fetchall()
            return [
                {
                    "id": r["id"],
                    "role": r["role"],
                    "content": r["content"],
                    "sources": json.loads(r["sources_json"]) if r["sources_json"] else [],
                    "timestamp": r["timestamp"],
                }
                for r in rows
            ]

    def clear_chat(self, user_id: str = None):
        uid = user_id or self.current_user_id
        with get_db_connection(self.db_path) as conn:
            if uid:
                conn.execute("DELETE FROM chat_messages WHERE user_id = ? OR user_id = 'default_user'", (uid,))
            else:
                conn.execute("DELETE FROM chat_messages")

    # ── Active context ─────────────────────────────────────────────────────────

    def get_active_context(self, user_id: str = None) -> Optional[Dict[str, Any]]:
        fid = self.active_file_id
        if not fid:
            return None
        file_info = self.files.get(fid)
        period = file_info.get("period") if file_info else None
        return {
            "file_info":      file_info,
            "extracted_data": self.get_extracted_data(fid),
            "analytics":      self.get_analytics(fid),
            "reconciliation": self.get_reconciliation(period, user_id) if period else None,
        }

    def get_full_context(self, user_id: str = None) -> Dict[str, Any]:
        by_period = self.get_files_by_period(user_id)
        reconciliations = self.get_all_reconciliations(user_id)
        context = {
            "files_by_period": {},
            "all_analytics":   {},
        }
        for period, type_map in by_period.items():
            context["files_by_period"][period] = {}
            for gst_type, file_info in type_map.items():
                fid = file_info["id"]
                context["files_by_period"][period][gst_type] = {
                    "file_info":      file_info,
                    "extracted_data": self.get_extracted_data(fid),
                    "analytics":      self.get_analytics(fid),
                }
            context["files_by_period"][period]["reconciliation"] = reconciliations.get(period)
        return context

    def set_active_file(self, file_id: str, user_id: str = None):
        with get_db_connection(self.db_path) as conn:
            conn.execute("UPDATE files SET is_active = 0")
            conn.execute("UPDATE files SET is_active = 1 WHERE id = ?", (file_id,))

    def clear_all(self, user_id: str = None):
        uid = user_id or self.current_user_id
        with get_db_connection(self.db_path) as conn:
            if uid:
                conn.execute("DELETE FROM files WHERE user_id = ? OR user_id = 'default_user'", (uid,))
                conn.execute("DELETE FROM reconciliations WHERE user_id = ? OR user_id = 'default_user'", (uid,))
                conn.execute("DELETE FROM chat_messages WHERE user_id = ? OR user_id = 'default_user'", (uid,))
            else:
                conn.execute("DELETE FROM files")
                conn.execute("DELETE FROM reconciliations")
                conn.execute("DELETE FROM chat_messages")

    def has_data(self, user_id: str = None) -> bool:
        fid = self.active_file_id
        return fid is not None and self.get_extracted_data(fid) is not None

    def get_gstr1_for_period(self, period: str, user_id: str = None) -> Optional[Dict]:
        for file_info in self.list_files(user_id):
            if file_info.get("period") == period and file_info.get("gst_type") == "GSTR-1":
                return self.get_extracted_data(file_info["id"])
        return None

    def get_gstr3b_for_period(self, period: str, user_id: str = None) -> Optional[Dict]:
        for file_info in self.list_files(user_id):
            if file_info.get("period") == period and file_info.get("gst_type") == "GSTR-3B":
                return self.get_extracted_data(file_info["id"])
        return None


# Global singleton matching existing import patterns
store = AppStore()
