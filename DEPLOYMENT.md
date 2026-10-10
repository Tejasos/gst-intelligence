# GST Intelligence — Production Deployment Runbook

## 1. Hosting Provider Evaluation & Architecture Decision

To ensure that the SQLite database (`gst_intelligence.db`), uploaded tax returns, and generated Excel workbooks survive restarts, deployments, and container recreation, the hosting environment **must support a persistent mounted block volume**.

### Provider Comparison

| Provider | Persistent Disk Support | SQLite Concurrency Safety | Operational Overhead | Estimated Monthly Cost | Recommendation |
|---|---|---|---|---|---|
| **Render** | Yes (Render Persistent Disks attached to Web Service) | Excellent for single-instance with WAL mode | Minimal (Managed Git-deploy) | **$7/mo** (Starter) + **$1/mo** (10GB Disk) = **~$8/mo** | **Top Pick (Managed)** |
| **Fly.io** | Yes (`fly volumes create` mounted to VM) | Excellent (runs directly on NVMe persistent volume) | Low | **$5 - $8/mo** | Strong Alternative |
| **Linux VPS (Hetzner / DigitalOcean)** | Yes (Native durable root/block storage) | High performance with Docker Compose | Moderate (requires OS updates, SSL setup) | **$4 - $6/mo** | **Top Pick (Self-Hosted/VPS)** |
| **AWS EC2 / Lightsail** | Yes (EBS / Lightsail SSD) | Full control | Moderate | **$5 - $10/mo** | Enterprise Choice |

### SQLite Persistence Rules
1. **Never store SQLite in ephemeral storage**: Ensure `DATABASE_PATH` points to the mounted volume path (e.g. `/app/data/gst_intelligence.db`).
2. **Single Application Instance**: Run a single production container instance with multi-threaded Gunicorn (`-w 2 --threads 4`). Multiple distinct containers mounted to the same network file share (like NFS) can experience lock issues with SQLite.
3. **WAL Mode Active**: SQLite WAL mode (`PRAGMA journal_mode = WAL`) is automatically initialized by the application, permitting non-blocking concurrent reads during writes.

---

## 2. Production Environment Configuration

Create a production `.env` file on your server (or configure these environment variables in your hosting provider's dashboard):

```bash
# Server Settings
APP_ENV=production
SECRET_KEY=generate-a-64-character-random-hex-string
PORT=8000
ALLOWED_ORIGINS=https://your-domain.com,http://localhost:3000

# Durable Storage Paths (Mounted on persistent volume)
DATA_DIR=/app/data
DATABASE_PATH=/app/data/gst_intelligence.db
UPLOAD_DIR=/app/data/uploads
OUTPUT_DIR=/app/data/output
BACKUP_DIR=/app/data/backups

# Security
AUTH_REQUIRED=true
SESSION_EXPIRY_HOURS=72
MAX_UPLOAD_MB=50

# AI Inference Mode ('ollama' or 'hosted')
AI_PROVIDER=hosted

# Hosted AI Provider (OpenAI, Groq, Together, OpenRouter)
HOSTED_AI_BASE_URL=https://api.openai.com/v1
HOSTED_AI_API_KEY=sk-your-private-api-key
HOSTED_AI_MODEL=gpt-4o-mini
HOSTED_AI_TIMEOUT=60

# Ollama Settings (used if AI_PROVIDER=ollama)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3:8b
```

To generate a secure secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 3. Deployment Option A: Docker Compose (Linux VPS)

### Prerequisites
- Docker Engine 24+ & Docker Compose v2+
- Git

### Deployment Steps
1. Clone the repository on your server:
   ```bash
   git clone https://github.com/tejasairspa-ctrl/gst-intelligence.git
   cd gst-intelligence
   ```
2. Create your `.env` configuration file:
   ```bash
   cp .env.example .env
   # Edit with your secrets and URLs
   nano .env
   ```
3. Build and launch the container stack in detached mode:
   ```bash
   docker compose up -d --build
   ```
4. Verify container status:
   ```bash
   docker compose ps
   ```
5. Check backend health and readiness:
   ```bash
   curl http://localhost:8000/api/health
   curl http://localhost:8000/api/ready
   ```
6. Access the application at `http://your-server-ip:3000` (or configure domain reverse proxy with Certbot SSL).

---

## 4. Deployment Option B: Render (Managed Cloud)

1. Connect your GitHub repository to [Render.com](https://render.com).
2. Create a new **Web Service**:
   - **Environment**: Docker
   - **Dockerfile Path**: `backend/Dockerfile`
   - **Instance Type**: Starter ($7/month)
3. Attach a **Persistent Disk**:
   - **Mount Path**: `/app/data`
   - **Size**: 10 GB ($1/month)
4. Add the Environment Variables from the configuration section above.
5. Deploy the Static Frontend as a Render Static Site:
   - **Build Command**: `npm ci && npm run build`
   - **Publish Directory**: `dist`
   - **Rewrite Rules**: Source: `/*` -> Destination: `/index.html` (for SPA routing).
   - **Environment Variable**: `VITE_API_URL=https://your-backend-service.onrender.com/api`

---

## 5. Deployment Option C: Railway (Managed Cloud)

Railway uses the root `Dockerfile` and `railway.json` automatically:

1. **Create / Connect Project on Railway**:
   - In Railway Dashboard, click **New Project** -> **Deploy from GitHub repo** -> Select `Tejasos/gst-intelligence`.
2. **Backend Service Settings**:
   - **Builder**: Automatically set to `Dockerfile` via `railway.json` (or set **Settings > Build > Builder** to **Dockerfile**).
   - **Root Directory**: Leave as `/` (root) or `/backend`. Both work seamlessly.
3. **Attach Persistent Volume**:
   - In your backend service dashboard on Railway, click **Volumes** -> **Add Volume**.
   - **Mount Path**: `/app/data` (ensures SQLite database and uploads survive deployments).
4. **Environment Variables**:
   - Add variables: `APP_ENV=production`, `SECRET_KEY=...`, `AUTH_REQUIRED=true`, `ALLOWED_ORIGINS=*` (or your frontend URL).
   - *(Note: Railway automatically provides and binds to dynamic `$PORT`)*.
5. **Generate Domain**:
   - Go to **Settings > Networking > Public Networking** and click **Generate Domain** to get your public HTTPS URL.


---

## 5. Health Checks and Monitoring

The backend exposes two dedicated monitoring endpoints:
- `GET /api/health`: Returns application status and version.
  ```json
  {"service": "GST Intelligence API", "status": "ok", "version": "2.0.0"}
  ```
- `GET /api/ready`: Readiness probe verifying active database writeability and storage directory integrity.
  ```json
  {"status": "ready", "database": "ok", "storage": "ok"}
  ```
- `GET /api/ai/status`: Reports configured AI provider connectivity without sending prompts.
