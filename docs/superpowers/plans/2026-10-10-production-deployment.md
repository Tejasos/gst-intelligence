# GST Intelligence — Production Deployment & Go-Live Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform GST Intelligence from a local development script into a secure, durable, multi-user, production-ready web application backed by SQLite persistence, dual AI inference, containerization, and automated verification.

**Architecture:** A containerized Flask WSGI backend (Gunicorn/Waitress) and React 18 production frontend served via an Nginx reverse proxy. Application state and user metadata persist in a WAL-mode SQLite database with foreign keys and busy timeout on durable storage. Document uploads and generated workbooks reside in dedicated persistent directories with magic-byte validation. The chat system abstracts inference across local Ollama and hosted OpenAI-compatible APIs while preserving deterministic regex calculations.

**Tech Stack:** Python 3.14/Flask 3.0, SQLite3 (WAL mode), Gunicorn, Waitress, React 18, Vite 5, TailwindCSS, Docker, Nginx, pytest.

**Spec:** User prompt requirements for Phase 1 through Phase 15.

## Global Constraints
- Python 3.14 compatibility without native C/Rust compilations.
- SQLite remains the database with durable persistent storage and WAL journal mode.
- Preserve all existing GST parsing, risk calculations, anomaly detection, reconciliation, and linked workbook generation logic.
- Support both Ollama and hosted AI inference through environment configuration.
- Enforce user authentication, session security, and tenant/user file isolation.
- Do not commit secrets to Git.

## Review Focus
1. **Concurrent SQLite writes during heavy file parsing**: PDF parsing and analytics are compute-heavy; database write transactions must be brief and isolated from parser execution.
2. **Backwards compatibility of `store.py`**: All existing modules (`risk_engine`, `risk_workbook`, `routes/export.py`) rely on `store.files` and store accessor methods; the SQLite-backed store must adhere strictly to these interfaces.
3. **Magic-byte validation on file uploads**: Prevent malicious file uploads by verifying `%PDF-` and zip headers rather than relying on file extensions alone.
4. **AI provider fallback resilience**: When neither Ollama nor a hosted LLM is available, direct numeric queries and core GST analytical workflows must continue functioning without throwing 500 errors.
5. **Nginx SPA routing and upload limit**: Nginx must support client body sizes up to 50MB and route non-API paths to `index.html`.

---

### Task 1: Environment Configuration & Dependencies Update

**Files:**
- Create: `backend/config.py`
- Create: `backend/.env.example`
- Create: `.env.example`
- Modify: `backend/requirements.txt`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: Environment variables (`DATABASE_PATH`, `UPLOAD_DIR`, `OUTPUT_DIR`, `SECRET_KEY`, `AI_PROVIDER`, etc.)
- Produces: `config` module exporting `Config` class with typed accessors.

- [ ] **Step 1: Write test for config loader**
Create `backend/tests/test_config.py` verifying default paths, environment variable overrides, and validation logic.

- [ ] **Step 2: Run test to verify it fails**
Run: `venv\Scripts\python.exe -m pytest backend/tests/test_config.py`
Expected: FAIL (module not found)

- [ ] **Step 3: Update `backend/requirements.txt` and install**
Add `pytest==8.2.2`, `gunicorn==22.0.0`, `waitress==3.0.0` to `backend/requirements.txt` and install in venv.

- [ ] **Step 4: Implement `backend/config.py`, `backend/.env.example`, `.env.example`, and `.gitignore`**
Implement centralized configuration with defaults and path resolution.

- [ ] **Step 5: Run config test to verify it passes**
Run: `venv\Scripts\python.exe -m pytest backend/tests/test_config.py`
Expected: PASS

---

### Task 2: SQLite Persistence Layer & Store Migration

**Files:**
- Create: `backend/database.py`
- Create: `backend/services/backup_service.py`
- Modify: `backend/store.py`
- Test: `backend/tests/test_db_persistence.py`

**Interfaces:**
- Consumes: `Config.DATABASE_PATH`
- Produces: `get_db_connection()`, `init_db()`, `store` singleton with identical public API (`store.files`, `add_file`, `set_extracted_data`, `get_extracted_data`, `set_reconciliation`, `get_all_reconciliations`, `add_message`, `get_chat_history`, etc.).

- [ ] **Step 1: Write failing persistence tests**
Test user isolation, file state persistence, reconciliation persistence across separate store instantiations (simulating server restart), and concurrent writes.

- [ ] **Step 2: Run tests to verify they fail**
Run: `venv\Scripts\python.exe -m pytest backend/tests/test_db_persistence.py`
Expected: FAIL

- [ ] **Step 3: Implement SQLite schema and connection manager in `backend/database.py`**
Enable WAL mode (`PRAGMA journal_mode = WAL`), foreign keys (`PRAGMA foreign_keys = ON`), busy timeout (`PRAGMA busy_timeout = 5000`). Create tables: `users`, `sessions`, `files`, `extracted_data`, `analytics`, `reconciliations`, `chat_messages`.

- [ ] **Step 4: Implement `backend/services/backup_service.py`**
Use `sqlite3.backup` API for online, non-blocking snapshot backups to a designated backup directory.

- [ ] **Step 5: Refactor `backend/store.py` to persist to SQLite**
Ensure `store.files` property maps dynamically to database records, and `store.get_extracted_data()`, `store.set_extracted_data()`, etc., serialize and deserialize JSON transparently.

- [ ] **Step 6: Run persistence tests to verify they pass**
Run: `venv\Scripts\python.exe -m pytest backend/tests/test_db_persistence.py`
Expected: PASS

---

### Task 3: Authentication & Multi-User Security

**Files:**
- Create: `backend/services/auth_service.py`
- Create: `backend/routes/auth.py`
- Modify: `backend/main.py`
- Modify: `backend/routes/upload.py`
- Modify: `backend/routes/export.py`
- Modify: `backend/routes/chat.py`
- Modify: `backend/routes/reconciliation.py`
- Modify: `backend/routes/intelligence.py`
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `database.py`, `Config.SECRET_KEY`
- Produces: `@require_auth` decorator, `/api/auth/register`, `/api/auth/login`, `/api/auth/logout`, `/api/auth/me`.

- [ ] **Step 1: Write failing authentication tests**
Test user registration, duplicate email rejection, password hashing, login token generation, authenticated access, unauthorized 401 response, and tenant data isolation.

- [ ] **Step 2: Run tests to verify they fail**
Run: `venv\Scripts\python.exe -m pytest backend/tests/test_auth.py`
Expected: FAIL

- [ ] **Step 3: Implement `backend/services/auth_service.py`**
Password hashing with `werkzeug.security.generate_password_hash`, cryptographically secure session tokens, session verification with expiration.

- [ ] **Step 4: Implement `backend/routes/auth.py` and `@require_auth` decorator**
Provide register, login, logout, and me endpoints. Decorator populates `flask.g.current_user` and enforces authentication (with configurable bypass for local dev if desired).

- [ ] **Step 5: Protect API routes and associate records with `current_user.id`**
Ensure file uploads, analytics queries, reconciliations, exports, and chats only access records owned by the authenticated user.

- [ ] **Step 6: Run auth tests to verify they pass**
Run: `venv\Scripts\python.exe -m pytest backend/tests/test_auth.py`
Expected: PASS

---

### Task 4: Durable File Storage & Magic-Byte Validation

**Files:**
- Create: `backend/services/storage_service.py`
- Modify: `backend/routes/upload.py`
- Modify: `backend/routes/export.py`
- Test: `backend/tests/test_file_storage.py`

**Interfaces:**
- Consumes: `Config.UPLOAD_DIR`, `Config.OUTPUT_DIR`
- Produces: `save_uploaded_file()`, `get_file_path()`, `validate_file_content()`.

- [ ] **Step 1: Write failing storage and validation tests**
Test valid PDF magic bytes (`%PDF-`), valid Excel signature (`PK\x03\x04`), rejection of renamed binaries, and path traversal prevention.

- [ ] **Step 2: Run tests to verify they fail**
Run: `venv\Scripts\python.exe -m pytest backend/tests/test_file_storage.py`
Expected: FAIL

- [ ] **Step 3: Implement `backend/services/storage_service.py`**
Validate headers, generate UUID-based storage filenames, and manage persistent storage folders safely.

- [ ] **Step 4: Integrate storage service into `upload.py` and `export.py`**
Replace hardcoded `"uploads"` and `"output"` directories with the validated storage service.

- [ ] **Step 5: Run storage tests to verify they pass**
Run: `venv\Scripts\python.exe -m pytest backend/tests/test_file_storage.py`
Expected: PASS

---

### Task 5: Dual AI Provider Abstraction (Ollama & Hosted API)

**Files:**
- Create: `backend/services/ai_provider.py`
- Modify: `backend/services/chat_service.py`
- Modify: `backend/routes/chat.py`
- Test: `backend/tests/test_ai_provider.py`

**Interfaces:**
- Consumes: `Config.AI_PROVIDER`, `Config.OLLAMA_BASE_URL`, `Config.HOSTED_AI_BASE_URL`, `Config.HOSTED_AI_API_KEY`
- Produces: `ai_provider.ask()`, `ai_provider.stream()`, `ai_provider.get_status()`, `/api/ai/status`.

- [ ] **Step 1: Write failing AI provider tests**
Test provider selection (`ollama` vs `hosted`), graceful fallback when service is offline, and preservation of direct numeric regex answers.

- [ ] **Step 2: Run tests to verify they fail**
Run: `venv\Scripts\python.exe -m pytest backend/tests/test_ai_provider.py`
Expected: FAIL

- [ ] **Step 3: Implement `backend/services/ai_provider.py`**
Unified client supporting both Ollama generate API and OpenAI-compatible Chat Completions API with timeouts and streaming.

- [ ] **Step 4: Update `chat_service.py` and `routes/chat.py`**
Route explanations through `ai_provider` while preserving the deterministic numeric calculation engine. Add `/api/ai/status` route.

- [ ] **Step 5: Run AI provider tests to verify they pass**
Run: `venv\Scripts\python.exe -m pytest backend/tests/test_ai_provider.py`
Expected: PASS

---

### Task 6: Production WSGI Server, Readiness Probes & Health Checks

**Files:**
- Create: `backend/wsgi.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_health_and_probes.py`

**Interfaces:**
- Consumes: `main.app`, `Config`
- Produces: WSGI entrypoint for Gunicorn/Waitress, `/api/health`, `/api/ready`.

- [ ] **Step 1: Write failing health and readiness tests**
Verify `/api/health` returns ok, and `/api/ready` checks database connectivity and storage directory writability.

- [ ] **Step 2: Run tests to verify they fail**
Run: `venv\Scripts\python.exe -m pytest backend/tests/test_health_and_probes.py`
Expected: FAIL

- [ ] **Step 3: Implement `backend/wsgi.py` and update `main.py`**
Configure CORS with `ALLOWED_ORIGINS`, disable Flask debug in production, implement structured logging, and wire up `/api/ready`.

- [ ] **Step 4: Run health tests to verify they pass**
Run: `venv\Scripts\python.exe -m pytest backend/tests/test_health_and_probes.py`
Expected: PASS

---

### Task 7: Frontend Authentication UI & API Client Updates

**Files:**
- Create: `frontend/src/context/AuthContext.jsx`
- Create: `frontend/src/components/AuthModal.jsx`
- Modify: `frontend/src/api/client.js`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/LeftPanel.jsx`

**Interfaces:**
- Consumes: `/api/auth/*`
- Produces: Token-bearing HTTP client, login/register UI, user profile display, logout capability.

- [ ] **Step 1: Update `frontend/src/api/client.js`**
Add Bearer token interceptor to Axios, and update `streamChat` to include `Authorization` header.

- [ ] **Step 2: Implement `AuthContext.jsx`**
Manage user state, token storage in `localStorage`, login, register, and logout actions.

- [ ] **Step 3: Implement `AuthModal.jsx`**
Sleek modal for Sign In and Register with error messaging and validation.

- [ ] **Step 4: Integrate Auth into `App.jsx` and `LeftPanel.jsx`**
Provide auth state and user badge in the UI.

- [ ] **Step 5: Test frontend build**
Run: `npm run build` in `frontend`
Expected: PASS with 0 build errors.

---

### Task 8: Docker Containerization & Reverse Proxy

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `docker/nginx.conf`
- Create: `docker-compose.yml`
- Create: `.dockerignore`

**Interfaces:**
- Consumes: Source code, Docker daemon
- Produces: Production containers, unified compose stack with persistent `/data` volume.

- [ ] **Step 1: Create `backend/Dockerfile`**
Python 3.12/3.14 slim image, non-root user, dependencies installed, Gunicorn WSGI startup, volume `/app/data`.

- [ ] **Step 2: Create `docker/nginx.conf`**
Configured with 50M client body size, gzip compression, SPA fallback `try_files $uri $uri/ /index.html`, and proxy `/api` to backend.

- [ ] **Step 3: Create `frontend/Dockerfile`**
Multi-stage build: Stage 1 Node 20 build -> Stage 2 Nginx alpine serving static assets.

- [ ] **Step 4: Create `docker-compose.yml`**
Services for `backend` and `frontend`, network bridge, persistent volume `gst_data:/app/data`.

---

### Task 9: CI/CD Pipeline & Automated Release Verification

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: Git push/PR to main
- Produces: Automated test execution, frontend build check, Python syntax validation.

- [ ] **Step 1: Create `.github/workflows/ci.yml`**
Configure workflow running Python backend tests, frontend build, and Dockerfile syntax validation.

---

### Task 10: Documentation & Deployment Runbook

**Files:**
- Create: `DEPLOYMENT.md`
- Create: `BACKUP_RECOVERY.md`
- Create: `README.md`

**Interfaces:**
- Consumes: Architecture and implementation details
- Produces: Complete operational guides for hosting providers, backup restoration, environment setup, and release procedures.

- [ ] **Step 1: Write `DEPLOYMENT.md`**
Provider evaluation (Render, Fly.io, DigitalOcean VPS), cost estimates, step-by-step launch commands.

- [ ] **Step 2: Write `BACKUP_RECOVERY.md`**
Tested SQLite backup and restore runbook, verification procedures.

- [ ] **Step 3: Write comprehensive `README.md`**
Overview, quickstart, architecture, configuration options, production deployment.

---

### Task 11: End-to-End Verification & Baseline Check

**Files:**
- Test all components locally
- Verify baseline test: `venv\Scripts\python.exe -m tests.test_ratio_sources`
- Verify database restart retention
- Verify backup restore cycle

- [ ] **Step 1: Run complete backend test suite**
Run: `venv\Scripts\python.exe -m pytest backend/tests/`
Expected: 100% PASS

- [ ] **Step 2: Run frontend production build**
Run: `npm run build` in `frontend`
Expected: PASS

- [ ] **Step 3: Verify end-to-end integration with running services**
Verify health check, auth, file upload, risk engine, and workbook export.
