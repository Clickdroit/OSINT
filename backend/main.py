from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, text, func
from typing import List, Optional
import os
import csv
import io
import json

from backend.config import settings
from backend.database import get_db, init_db
from backend.models import Target, ScanResult, Leak, Keyword, Alert, Feed
from backend.schemas import (
    TargetCreate, TargetResponse, TargetUpdateNotes, ScanResultResponse,
    TaskStatusResponse, LeakResponse, KeywordCreate,
    KeywordResponse, AlertResponse, AIChatRequest, AIChatResponse,
    RemediationRequest, RemediationResponse,
    FeedCreate, FeedResponse, FeedUpdate, SystemStatsResponse
)
from backend.celery_app import celery_app
import google.generativeai as genai

# Configure Google Gemini
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB and pg_trgm extension on startup
    print("[API] Initializing database and extensions...")
    init_db()
    yield
    print("[API] Shutting down application context...")

app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API for Social Media Mapping, Leak Check Ingestion, and Cyber RSS Watcher",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend integration
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the static directory for CSS, JS, etc.
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

@app.get("/", response_class=HTMLResponse)
def read_root():
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="Index HTML not found")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# --- TARGETS ENDPOINTS ---

@app.post("/api/v1/targets", response_model=TargetResponse, status_code=201)
def create_target(target_in: TargetCreate, db: Session = Depends(get_db)):
    if target_in.type not in ["username", "email", "domain"]:
        raise HTTPException(status_code=400, detail="Target type must be 'username', 'email', or 'domain'")
    
    target = Target(value=target_in.value.strip(), type=target_in.type)
    db.add(target)
    db.commit()
    db.refresh(target)
    return target

@app.get("/api/v1/targets", response_model=List[TargetResponse])
def list_targets(db: Session = Depends(get_db)):
    return db.scalars(select(Target)).all()

@app.delete("/api/v1/targets/{target_id}", status_code=204)
def delete_target(target_id: int, db: Session = Depends(get_db)):
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    db.delete(target)
    db.commit()
    return None

@app.patch("/api/v1/targets/{target_id}/notes", response_model=TargetResponse)
def update_target_notes(target_id: int, notes_in: TargetUpdateNotes, db: Session = Depends(get_db)):
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    target.notes = notes_in.notes
    db.commit()
    db.refresh(target)
    return target

@app.post("/api/v1/targets/import-csv", status_code=201)
async def import_targets_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    text_content = content.decode("utf-8")
    csv_file = io.StringIO(text_content)
    
    reader = csv.reader(csv_file)
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="Le fichier CSV est vide.")
        
    created_count = 0
    errors = []
    
    # Try parsing as header-based first.
    has_header = False
    header = [col.strip().lower() for col in rows[0]]
    if "value" in header and "type" in header:
        has_header = True
        value_idx = header.index("value")
        type_idx = header.index("type")
        notes_idx = header.index("notes") if "notes" in header else None
    else:
        # Fallback to column index ordering
        value_idx = 0
        type_idx = 1
        notes_idx = 2
        
    start_row = 1 if has_header else 0
    
    for i in range(start_row, len(rows)):
        row = rows[i]
        if not row or len(row) <= max(value_idx, type_idx):
            continue
        val = row[value_idx].strip()
        typ = row[type_idx].strip().lower()
        notes_val = row[notes_idx].strip() if notes_idx is not None and len(row) > notes_idx else None
        
        if not val or not typ:
            continue
            
        if typ not in ["username", "email", "domain"]:
            errors.append(f"Ligne {i+1}: Type '{typ}' invalide. Doit être 'username', 'email' ou 'domain'.")
            continue
            
        # Check if duplicate
        existing = db.scalar(select(Target).where(Target.value == val, Target.type == typ))
        if existing:
            continue
            
        target = Target(value=val, type=typ, notes=notes_val)
        db.add(target)
        created_count += 1
        
    if created_count > 0:
        db.commit()
        
    return {"created": created_count, "errors": errors}



# --- OSINT USERNAME SCAN ENDPOINTS ---

@app.post("/api/v1/scans/pseudo", response_model=TaskStatusResponse, status_code=202)
def trigger_pseudo_scan(target_id: int, db: Session = Depends(get_db)):
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    if target.type != "username":
        raise HTTPException(status_code=400, detail="Target must be of type 'username' to run social media scan")

    # Clear previous results for this target to keep it clean
    db.execute(text("DELETE FROM scan_results WHERE target_id = :tid").bindparams(tid=target_id))
    db.commit()

    # Trigger async Celery task
    task = celery_app.send_task("workers.tasks.scan_username", args=[target_id])
    return {"task_id": task.id, "status": "PENDING"}

@app.post("/api/v1/scans/domain", response_model=TaskStatusResponse, status_code=202)
def trigger_domain_scan(target_id: int, db: Session = Depends(get_db)):
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    if target.type != "domain":
        raise HTTPException(status_code=400, detail="Target must be of type 'domain' to run domain security scan")

    # Clear previous results for this target to keep it clean
    db.execute(text("DELETE FROM scan_results WHERE target_id = :tid").bindparams(tid=target_id))
    db.commit()

    # Trigger async Celery task
    task = celery_app.send_task("workers.tasks.scan_domain", args=[target_id])
    return {"task_id": task.id, "status": "PENDING"}

@app.post("/api/v1/scans/email", response_model=TaskStatusResponse, status_code=202)
def trigger_email_scan(target_id: int, db: Session = Depends(get_db)):
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    if target.type != "email":
        raise HTTPException(status_code=400, detail="Target must be of type 'email' to run email scan")

    # Clear previous results for this target to keep it clean
    db.execute(text("DELETE FROM scan_results WHERE target_id = :tid").bindparams(tid=target_id))
    db.commit()

    # Trigger async Celery task
    task = celery_app.send_task("workers.tasks.scan_email", args=[target_id])
    return {"task_id": task.id, "status": "PENDING"}

@app.get("/api/v1/scans/{task_id}", response_model=TaskStatusResponse)
def get_scan_status(task_id: str):
    res = celery_app.AsyncResult(task_id)
    result_data = None
    if res.ready():
        result_data = res.result
    return {
        "task_id": task_id,
        "status": res.status,
        "result": result_data
    }

@app.get("/api/v1/targets/{target_id}/results", response_model=List[ScanResultResponse])
def get_target_scan_results(target_id: int, db: Session = Depends(get_db)):
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    return db.scalars(select(ScanResult).where(ScanResult.target_id == target_id)).all()


# --- LEAK & BREACH ENDPOINTS ---

@app.post("/api/v1/leaks/ingest", response_model=TaskStatusResponse, status_code=202)
def trigger_leak_ingest(
    file_path: str = Query(..., description="Absolute path to leak file on droplet or host"),
    source: str = Query(..., description="Name of the leak / breach (e.g. LinkedIn-2016)"),
    leak_date: Optional[str] = Query(None, description="Date of the breach (e.g. 2016-05-18)")
):
    # Resolve absolute path and verify it is inside /app/data or local data dir (Path Traversal protection)
    abs_path = os.path.abspath(file_path)
    allowed_dirs = [
        "/app/data",
        os.path.abspath(os.path.join(os.getcwd(), "data"))
    ]
    
    is_allowed = False
    for allowed_dir in allowed_dirs:
        try:
            # Check if abs_path is a subpath of allowed_dir
            if os.path.commonpath([abs_path, allowed_dir]) == allowed_dir:
                is_allowed = True
                break
        except ValueError:
            # Raised if paths are on different drives on Windows
            continue
            
    if not is_allowed:
        raise HTTPException(
            status_code=400,
            detail="Le chemin du fichier de fuites doit être situé dans le répertoire de données autorisé (/app/data/ ou ./data/)."
        )

    # Trigger streaming ingestion in background worker
    task = celery_app.send_task("workers.tasks.ingest_leak_file", args=[abs_path, source, leak_date])
    return {"task_id": task.id, "status": "PENDING"}

@app.get("/api/v1/leaks/search", response_model=List[LeakResponse])
def search_leaks(
    q: str = Query(..., min_length=3, description="Search term (username, email, or substring)"),
    fuzzy: bool = Query(False, description="Enable fuzzy / similarity search (uses GIN index)"),
    limit: int = Query(50, le=100)
, db: Session = Depends(get_db)):
    
    q_clean = q.strip()
    if fuzzy:
        # PostgreSQL Trigram similarity match using pg_trgm.
        # Operates over GIN index. Sub-10ms performance due to trigram indexing.
        query = (
            select(Leak)
            .where(
                or_(
                    text("leaks.email % :q"),
                    text("leaks.username % :q")
                )
            )
            .params(q=q_clean)
            .limit(limit)
        )
    else:
        # Exact/Prefix match using B-Tree index (instant lookup)
        query = (
            select(Leak)
            .where(
                or_(
                    Leak.email == q_clean,
                    Leak.username == q_clean,
                    Leak.email.like(f"{q_clean}%"),
                    Leak.username.like(f"{q_clean}%")
                )
            )
            .limit(limit)
        )
    
    return db.scalars(query).all()


# --- WATCHED KEYWORDS ENDPOINTS ---

@app.post("/api/v1/keywords", response_model=KeywordResponse, status_code=201)
def create_keyword(keyword_in: KeywordCreate, db: Session = Depends(get_db)):
    # Check if keyword already exists
    existing = db.scalar(select(Keyword).where(Keyword.value == keyword_in.value.strip()))
    if existing:
        return existing
        
    keyword = Keyword(value=keyword_in.value.strip())
    db.add(keyword)
    db.commit()
    db.refresh(keyword)
    return keyword

@app.get("/api/v1/keywords", response_model=List[KeywordResponse])
def list_keywords(db: Session = Depends(get_db)):
    return db.scalars(select(Keyword)).all()

@app.delete("/api/v1/keywords/{keyword_id}", status_code=204)
def delete_keyword(keyword_id: int, db: Session = Depends(get_db)):
    keyword = db.get(Keyword, keyword_id)
    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")
    db.delete(keyword)
    db.commit()
    return None


# --- CYBER ALERTS & RSS ENDPOINTS ---

@app.get("/api/v1/alerts", response_model=List[AlertResponse])
def list_alerts(db: Session = Depends(get_db)):
    # Join Keyword to return the matched keyword value directly
    query = select(Alert).order_by(Alert.found_at.desc())
    alerts = db.scalars(query).all()
    
    # Map model to output and populate keyword_value string
    results = []
    for a in alerts:
        res = AlertResponse.model_validate(a)
        res.keyword_value = a.keyword.value
        results.append(res)
        
    return results

@app.post("/api/v1/rss/trigger", response_model=TaskStatusResponse, status_code=202)
def trigger_rss_check():
    task = celery_app.send_task("workers.tasks.check_rss_feeds")
    return {"task_id": task.id, "status": "PENDING"}


# --- DYNAMIC RSS FEEDS CRUD ENDPOINTS ---

@app.post("/api/v1/feeds", response_model=FeedResponse, status_code=201)
def create_feed(feed_in: FeedCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(Feed).where(Feed.url == feed_in.url.strip()))
    if existing:
        raise HTTPException(status_code=400, detail="Ce flux RSS est déjà configuré.")
        
    feed = Feed(name=feed_in.name.strip(), url=feed_in.url.strip())
    db.add(feed)
    db.commit()
    db.refresh(feed)
    return feed

@app.get("/api/v1/feeds", response_model=List[FeedResponse])
def list_feeds(db: Session = Depends(get_db)):
    return db.scalars(select(Feed).order_by(Feed.created_at.desc())).all()

@app.put("/api/v1/feeds/{feed_id}", response_model=FeedResponse)
def update_feed(feed_id: int, feed_in: FeedUpdate, db: Session = Depends(get_db)):
    feed = db.get(Feed, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Flux RSS introuvable")
        
    if feed_in.name is not None:
        feed.name = feed_in.name.strip()
    if feed_in.url is not None:
        feed.url = feed_in.url.strip()
    if feed_in.is_active is not None:
        feed.is_active = feed_in.is_active
        
    db.commit()
    db.refresh(feed)
    return feed

@app.delete("/api/v1/feeds/{feed_id}", status_code=204)
def delete_feed(feed_id: int, db: Session = Depends(get_db)):
    feed = db.get(Feed, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Flux RSS introuvable")
    db.delete(feed)
    db.commit()
    return None


# --- SYSTEM STATS / DASHBOARD ENDPOINT ---

@app.get("/api/v1/stats", response_model=SystemStatsResponse)
def get_system_stats(db: Session = Depends(get_db)):
    total_targets = db.scalar(select(func.count(Target.id)))
    usernames = db.scalar(select(func.count(Target.id)).where(Target.type == "username"))
    emails = db.scalar(select(func.count(Target.id)).where(Target.type == "email"))
    domains = db.scalar(select(func.count(Target.id)).where(Target.type == "domain"))
    
    leaks = db.scalar(select(func.count(Leak.id)))
    alerts = db.scalar(select(func.count(Alert.id)))
    scans = db.scalar(select(func.count(ScanResult.id)))
    
    # Get recent timeline items
    recent_targets = db.scalars(
        select(Target).order_by(Target.created_at.desc()).limit(5)
    ).all()
    recent_alerts = db.scalars(
        select(Alert).order_by(Alert.found_at.desc()).limit(5)
    ).all()
    recent_found = db.scalars(
        select(ScanResult)
        .where(ScanResult.status == "FOUND", ScanResult.platform != "Rapport OSINT IA")
        .order_by(ScanResult.checked_at.desc())
        .limit(5)
    ).all()

    timeline = []
    for t in recent_targets:
        timeline.append({
            "type": "target",
            "title": f"Cible ajoutée : {t.value} ({t.type})",
            "timestamp": t.created_at.isoformat()
        })
    for a in recent_alerts:
        timeline.append({
            "type": "alert",
            "title": f"Alerte RSS : {a.title}",
            "timestamp": a.found_at.isoformat()
        })
    for r in recent_found:
        timeline.append({
            "type": "scan",
            "title": f"Profil trouvé sur {r.platform} (Cible ID {r.target_id})",
            "timestamp": r.checked_at.isoformat()
        })

    # Sort descending by timestamp
    timeline.sort(key=lambda x: x["timestamp"], reverse=True)
    timeline = timeline[:10]
    
    return {
        "targets": {
            "total": total_targets or 0,
            "usernames": usernames or 0,
            "emails": emails or 0,
            "domains": domains or 0
        },
        "leaks_count": leaks or 0,
        "alerts_count": alerts or 0,
        "scans_count": scans or 0,
        "timeline": timeline
    }


# --- GEMINI AI COPILOT ENDPOINT ---

@app.post("/api/v1/ai/chat", response_model=AIChatResponse)
async def chat_with_copilot(chat_in: AIChatRequest):
    # Define model with strict threat intelligence guidelines
    system_instruction = (
        "Tu es 'Cyber Copilot', un assistant d'analyse en cybersécurité et en renseignement (OSINT) intégré "
        "dans un hub privé de surveillance. Ton but est d'analyser les menaces et de recommander "
        "des stratégies de défense concrètes.\n\n"
        "DIRECTIVES DE RÉPONSE :\n"
        "1. Reste concentré sur la cybersécurité, les menaces, la remédiation et la protection des cibles.\n"
        "2. Si l'utilisateur pose une question sur un email ou pseudo compromis, suggère des protocoles de sécurité "
        "(changement de mot de passe, clé de sécurité U2F, alerte phishing, surveillance active).\n"
        "3. Si l'utilisateur te soumet une alerte de sécurité (ex. CVE, ransomware), explique la faille en termes "
        "clairs et propose des mesures de mitigation (pare-feu, désactivation de port, patch de version).\n"
        "4. Adopte un ton professionnel, pragmatique et technique.\n"
        "5. Réponds en français de manière structurée et concise."
    )

    response_text = ""
    errors = []

    async def try_digitalocean():
        if not settings.AI_API_KEY:
            return None, "DigitalOcean API key not configured."
        try:
            import httpx
            url = settings.AI_BASE_URL.rstrip("/")
            if not url.endswith("/chat/completions"):
                url += "/chat/completions"

            messages = [{"role": "system", "content": system_instruction}]
            if chat_in.history:
                for msg in chat_in.history:
                    role = "user" if msg.role == "user" else "assistant"
                    messages.append({"role": role, "content": msg.content})
            messages.append({"role": "user", "content": chat_in.message})

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {settings.AI_API_KEY}"
                    },
                    json={
                        "model": settings.AI_MODEL_NAME,
                        "messages": messages
                    },
                    timeout=45.0
                )
                if response.status_code != 200:
                    return None, f"HTTP {response.status_code}: {response.text}"
                res_data = response.json()
                return res_data["choices"][0]["message"]["content"], None
        except Exception as e:
            return None, str(e)

    async def try_gemini():
        if not settings.GEMINI_API_KEY:
            return None, "Gemini API key not configured."
        try:
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=system_instruction
            )
            gemini_history = []
            if chat_in.history:
                for msg in chat_in.history:
                    role = "user" if msg.role == "user" else "model"
                    gemini_history.append({"role": role, "parts": [msg.content]})

            chat = model.start_chat(history=gemini_history)
            response = chat.send_message(chat_in.message)
            return response.text, None
        except Exception as e:
            return None, str(e)

    providers = []
    if settings.AI_PROVIDER == "digitalocean":
        providers = [("digitalocean", try_digitalocean), ("gemini", try_gemini)]
    else:
        providers = [("gemini", try_gemini), ("digitalocean", try_digitalocean)]

    for name, func in providers:
        res, err = await func()
        if res:
            response_text = res
            break
        elif err:
            errors.append(f"{name}: {err}")

    if not response_text:
        if not settings.AI_API_KEY and not settings.GEMINI_API_KEY:
            return {
                "response": "Le Cyber Copilot IA n'est pas activé car aucune clé d'API (`AI_API_KEY` pour DigitalOcean ou `GEMINI_API_KEY`) n'a été configurée dans votre fichier `.env` sur le Droplet. Veuillez renseigner cette clé puis redémarrer le conteneur.",
                "suggested_actions": [
                    "Ajouter GEMINI_API_KEY ou AI_API_KEY dans le fichier .env",
                    "Redémarrer le docker compose"
                ]
            }
        detail_msg = " | ".join(errors) if errors else "Aucun fournisseur d'IA n'est disponible."
        raise HTTPException(
            status_code=500,
            detail=f"Erreur de communication avec les services d'IA. Détails: {detail_msg}"
        )

    # Supply recommendations based on context_type
    suggestions = []
    if chat_in.context_type == "leaks":
        suggestions = [
            "Activer l'authentification multifacteur (MFA)",
            "Changer immédiatement le mot de passe sur tous les services liés",
            "Vérifier les activités de connexion suspectes"
        ]
    elif chat_in.context_type == "alerts":
        suggestions = [
            "Rechercher et appliquer le correctif de sécurité officiel",
            "Restreindre les accès réseau liés au service vulnérable",
            "Scanner vos systèmes à la recherche de signatures IoC"
        ]
    else:
        suggestions = [
            "Vérifier la politique de mots de passe",
            "Sensibiliser les équipes au phishing ciblé"
        ]
        
    return {
        "response": response_text,
        "suggested_actions": suggestions
    }


@app.post("/api/v1/ai/remediate", response_model=RemediationResponse)
async def remediate_code(req: RemediationRequest):
    system_instruction = (
        "Tu es 'Cyber Copilot Code Auditor', un expert en revue de code sécurisé et en remédiation de vulnérabilités.\n"
        "Ton but est d'analyser le code vulnérable fourni par l'utilisateur, d'identifier les faiblesses de sécurité, "
        "d'expliquer le problème en français de manière didactique et concise, et de fournir le code entièrement corrigé, "
        "sécurisé et prêt à l'emploi.\n\n"
        "DIRECTIVES :\n"
        "1. Explique brièvement la faille identifiée et comment elle peut être exploitée.\n"
        "2. Fournis le code complet corrigé.\n"
        "3. Réponds UNIQUEMENT sous la forme d'un objet JSON brut valide avec les clés 'explanation' et 'fixed_code'.\n"
        "Ne mets aucun texte de présentation ou d'explication en dehors de l'objet JSON."
    )

    prompt = (
        f"Analyse le code suivant écrit en {req.language}.\n"
        f"Description de la vulnérabilité (si disponible) : {req.vulnerability_description or 'Non spécifiée'}\n\n"
        f"Code à analyser :\n```\n{req.code}\n```\n\n"
        f"Retourne ta réponse UNIQUEMENT sous la forme d'un objet JSON brut valide avec la structure suivante :\n"
        f"{{\n"
        f"  \"explanation\": \"Explication claire de la faille en français, les risques associés et comment le correctif la résout.\",\n"
        f"  \"fixed_code\": \"Le code source complet corrigé, sécurisé et prêt à être déployé.\"\n"
        f"}}\n"
        f"Ne mets pas de balises markdown ```json autour du JSON. Renvoie du texte brut contenant uniquement l'objet JSON."
    )

    response_text = ""
    errors = []

    async def try_digitalocean():
        if not settings.AI_API_KEY:
            return None, "DigitalOcean API key not configured."
        try:
            import httpx
            url = settings.AI_BASE_URL.rstrip("/")
            if not url.endswith("/chat/completions"):
                url += "/chat/completions"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {settings.AI_API_KEY}"
                    },
                    json={
                        "model": settings.AI_MODEL_NAME,
                        "messages": [
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": prompt}
                        ]
                    },
                    timeout=45.0
                )
                if response.status_code != 200:
                    return None, f"HTTP {response.status_code}: {response.text}"
                res_data = response.json()
                return res_data["choices"][0]["message"]["content"], None
        except Exception as e:
            return None, str(e)

    async def try_gemini():
        if not settings.GEMINI_API_KEY:
            return None, "Gemini API key not configured."
        try:
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=system_instruction
            )
            response = model.generate_content(prompt)
            return response.text, None
        except Exception as e:
            return None, str(e)

    providers = []
    if settings.AI_PROVIDER == "digitalocean":
        providers = [("digitalocean", try_digitalocean), ("gemini", try_gemini)]
    else:
        providers = [("gemini", try_gemini), ("digitalocean", try_digitalocean)]

    for name, func in providers:
        res, err = await func()
        if res:
            response_text = res
            break
        elif err:
            errors.append(f"{name}: {err}")

    if not response_text:
        detail_msg = " | ".join(errors) if errors else "Aucun fournisseur d'IA n'est configuré."
        raise HTTPException(
            status_code=501,
            detail=f"Le Cyber Copilot IA n'est pas configuré ou a échoué. Détails: {detail_msg}"
        )

    # Parse the response to extract explanation and fixed_code
    try:
        # Clean potential markdown wrappers
        cleaned = response_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        
        parsed = json.loads(cleaned)
        return {
            "explanation": parsed.get("explanation", "Aucune explication fournie."),
            "fixed_code": parsed.get("fixed_code", req.code)
        }
    except Exception as e:
        print(f"[JSON Parsing Error] Failed to parse AI response as JSON: {response_text}. Error: {str(e)}")
        return {
            "explanation": f"L'IA a généré une réponse non-structurée :\n\n{response_text}",
            "fixed_code": req.code
        }

