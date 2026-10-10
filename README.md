# GST Intelligence

> **Automated GST Compliance, Risk Ratio Analysis, Multi-Period Reconciliation, and Audit-Linked Workbook Generation for Indian Tax Filings.**

GST Intelligence is a comprehensive tax intelligence and compliance platform engineered for Chartered Accountants, corporate tax teams, and audit professionals. It parses complex Indian GST portal returns (GSTR-1, GSTR-3B, GSTR-2A, GSTR-2B, GSTR-9), detects compliance risks, performs multi-period reconciliations, generates connected Excel workbooks, and provides audit-safe AI explanations.

---

## Key Features

- **Document Ingestion**: Extracts financial and tax figures from official GST portal PDF downloads using high-accuracy PDF parsing (`pdfplumber`).
- **DGARM Risk Ratios**: Computes comprehensive departmental risk ratios including turnover mismatch, RCM exclusion, ISD credits, and CDNR/CDNUR classifications.
- **Audit-Linked Workbooks**: Dynamically compiles linked, formula-driven Excel workbooks (`openpyxl`) ready for scrutiny proceedings.
- **Multi-Period Reconciliation**: Automatically matches GSTR-1 outward liabilities against GSTR-3B tax returns with period grouping.
- **Dual AI Assistant**: Pairs deterministic regex-based arithmetic calculation (zero hallucination guarantee) with qualitative explanations powered by either local Ollama (`llama3:8b`) or hosted OpenAI-compatible LLMs.
- **Durable Persistence**: Backed by a SQLite database in Write-Ahead Logging (WAL) mode with foreign keys, session tokens, and tenant isolation.
- **Production Containerization**: Multi-stage Dockerfiles for backend (Gunicorn/Waitress) and frontend (Nginx reverse proxy with SPA routing).

---

## Quickstart (Local Development)

### Windows One-Click Launcher
Run the root batch file:
```cmd
start_gst.bat
```
This launches the backend on `http://localhost:8000` and the Vite dev server on `http://localhost:3000`.

### Manual Startup

1. **Backend**:
   ```bash
   cd backend
   python -m venv venv
   # On Windows: venv\Scripts\activate
   # On Linux/macOS: source venv/bin/activate
   pip install -r requirements.txt
   python wsgi.py
   ```

2. **Frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Open `http://localhost:3000` in your browser.

---

## Production Deployment

### Option 1: Docker Compose (Recommended)
```bash
cp .env.example .env
# Edit .env with your secrets and allowed domains
docker compose up -d --build
```
Your app will be available on `http://localhost:3000` with the API proxied to the backend.

For detailed hosting guides (Render, Fly.io, Linux VPS), see [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Configuration

Configuration is managed via environment variables (see `.env.example`):

| Variable | Description | Default |
|---|---|---|
| `APP_ENV` | Environment (`development` or `production`) | `development` |
| `SECRET_KEY` | Secret key for sessions and tokens | (auto-generated in prod) |
| `DATABASE_PATH` | Path to persistent SQLite database | `data/gst_intelligence.db` |
| `UPLOAD_DIR` | Directory for uploaded GST returns | `data/uploads` |
| `OUTPUT_DIR` | Directory for generated Excel/PDF workbooks | `data/output` |
| `AI_PROVIDER` | AI provider (`ollama` or `hosted`) | `ollama` |
| `OLLAMA_BASE_URL` | Ollama service URL | `http://localhost:11434` |
| `HOSTED_AI_API_KEY` | Private API key for hosted LLM | - |
| `AUTH_REQUIRED` | Enforce user authentication | `true` |

---

## Running Automated Tests

Run the full backend test suite:
```bash
cd backend
venv\Scripts\pytest.exe tests/ -v
```

Run the frontend production build test:
```bash
cd frontend
npm run build
```

---

## Backup & Recovery

See [BACKUP_RECOVERY.md](BACKUP_RECOVERY.md) for automated snapshot creation, cron scheduling, and database restoration procedures.
