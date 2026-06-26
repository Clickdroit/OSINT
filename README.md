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

---

## Cyber Copilot AI (Analyste Cyber IA)

L'application intègre un **Assistant d'Analyse Cyber / Copilot** qui aide à interpréter les menaces et à élaborer des stratégies de défense.

### Ce que fait l'IA
1. **Explication de Filles de Sécurité (CVE)** : À partir de l'onglet de Veille RSS, si une vulnérabilité (ex. Zero-Day, Ransomware) apparaît, l'IA explique le fonctionnement technique de la faille en français simple et vulgarisé.
2. **Recommandations de Remédiation** : Si vous recherchez un mail compromis dans la base de fuites, l'IA suggère des protocoles de sécurité immédiats (changement de mots de passe, mise en place de clés de sécurité matérielles U2F, détection d'emails de phishing ciblés).
3. **Suggestions Dynamiques** : Après chaque réponse, l'IA formule des "actions suggérées" sous forme de boutons cliquables. Cliquer sur l'un d'eux interroge l'IA pour obtenir la procédure technique pas à pas (ex. *"Comment activer la MFA ?"*).

### Comment ça marche (Architecture)
- **API Unifiée** : Le backend FastAPI expose une route asynchrone `POST /api/v1/ai/chat` qui prend en charge l'historique et le type de contexte (leaks, alerts, général).
- **Double Compatibilité** : 
  - **Option A (DigitalOcean AI Router)** : Utilise l'API d'inférence de DigitalOcean pour interroger le modèle **Llama 3.3 70B Instruct** avec des requêtes HTTP asynchrones non-bloquantes via `httpx`.
  - **Option B (Google Gemini)** : Utilise le SDK officiel `google-generativeai` pour interroger **Gemini 1.5 Flash**.
- **Instructions Système** : L'IA est guidée par un prompt système strict pour conserver un profil d'analyste défensif technique, concis et professionnel.

### Configuration dans le `.env`
Pour activer l'IA sur le Droplet, modifiez le fichier `.env` :

```text
# Pour utiliser le routeur d'IA DigitalOcean (Recommandé) :
AI_PROVIDER=digitalocean
AI_API_KEY=vdoo_v1_...votre_cle_digitalocean...
AI_BASE_URL=https://inference.do-ai.run/v1
AI_MODEL_NAME=router:osint

# OU pour utiliser Google Gemini (Alternative) :
GEMINI_API_KEY=AIzaSy...votre_cle_gemini...
```

