# OSINT and Private Intelligence Hub

An asynchronous web intelligence tool designed to monitor threats, analyze targets, map social media aliases, and search massive database breaches.

---

## Recommended Hardware Specifications (DigitalOcean Droplet)

For optimal performance in production (handling millions of leak lines, running continuous RSS updates, and executing fast parallel queries):

| Component | Recommended Spec | Reason |
| :--- | :--- | :--- |
| **CPU** | 2 vCPUs (Intel Premium or AMD EPYC) | Async task coordination and parsing of large files. |
| **RAM** | 4 GB | Celery message brokering, FastAPI cache, and PostgreSQL buffer pools. |
| **Storage** | 50 GB+ NVMe SSD | Leak database stores millions of entries. NVMe improves bulk ingestion speeds. |
| **OS** | Ubuntu 22.04 LTS or Debian 12 | Stable Docker environments. |

---

## Architecture Overview

1. **FastAPI Backend (API)**: Services HTTP request handlers, maintains target registers, and queries database logs.
2. **Celery Worker**: Executes asynchronous workflows:
   - **Pseudo Mapping**: Concurrently queries 100+ platforms utilizing `httpx` and a semaphore limit of 25.
   - **Leak Ingestion**: Streaming parser feeding database copy channels.
   - **RSS Monitor**: Regularly parses cyber intelligence feeds (BleepingComputer, Sophos, Reddit) matching keywords.
3. **Redis**: Serves as the message broker.
4. **PostgreSQL**: Implements relational data schemas with custom B-Tree and GIN indexes enabling sub-10ms lookup speeds.

---

## Deployment Instructions

### Option A: Deployment on DigitalOcean Droplet (Docker Compose)

1. Connect to your Droplet via SSH:
   ```bash
   ssh root@your_droplet_ip
   ```
2. Git clone the repository and enter the directory.
3. Ensure Docker and Docker Compose are installed:
   ```bash
   apt update && apt install -y docker.io docker-compose
   ```
4. Build and boot the stack:
   ```bash
   docker-compose up -d --build
   ```
5. Check service logs:
   ```bash
   docker-compose logs -f
   ```
6. Open Swagger API documentation at: `http://<your_droplet_ip>:8000/docs`

---

### Option B: Local Development Setup (Native Run)

Requires Python 3.10+, PostgreSQL, and Redis installed locally.

1. **Database Setup**:
   Create a PostgreSQL database named `hub_osint`.
2. **Configure Environment**:
   Copy `.env.example` to `.env` and fill in your local Postgres/Redis details:
   ```bash
   cp .env.example .env
   ```
3. **Install Dependencies**:
   ```bash
   pip install -r backend/requirements.txt
   ```
4. **Run FastAPI Server**:
   ```bash
   uvicorn backend.main:app --reload --port 8000
   ```
5. **Run Celery Worker** (in a separate terminal):
   On Linux/macOS:
   ```bash
   PYTHONPATH=. celery -A backend.celery_app worker --loglevel=info
   ```
   On Windows:
   ```powershell
   $env:PYTHONPATH="."
   celery -A backend.celery_app worker --loglevel=info -P solo
   ```
6. **Run Celery Beat** (scheduler for RSS feed checks - optional):
   ```bash
   celery -A backend.celery_app beat --loglevel=info
   ```

---

## Key API Endpoints & Usage

### 1. Pseudo Search (Username Mapping)
- **Register Target**: `POST /api/v1/targets`
  ```json
  {
    "value": "johndoe",
    "type": "username"
  }
  ```
- **Trigger Scan**: `POST /api/v1/scans/pseudo?target_id=1`
- **Check Task Status**: `GET /api/v1/scans/{task_id}`
- **Retrieve Results**: `GET /api/v1/targets/1/results`

### 2. Breach Check (Leak Ingest & Search)
- **Ingest Leak File**: `POST /api/v1/leaks/ingest?file_path=/absolute/path/to/leak.txt&source=LinkedIn-Leak`
- **Query Leak Records**: `GET /api/v1/leaks/search?q=johndoe`
  - Set `fuzzy=true` to perform trigram GIN-indexed matches.

### 3. RSS Cyber Alert Scraper
- **Add Watched Keyword**: `POST /api/v1/keywords`
  ```json
  {
    "value": "Zero-Day"
  }
  ```
- **List Alert Alarms**: `GET /api/v1/alerts`
- **Force Instant Feed Check**: `POST /api/v1/rss/trigger`
