from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, text, func
from typing import List, Optional
import os

from backend.config import settings
from backend.database import get_db, init_db
from backend.models import Target, ScanResult, Leak, Keyword, Alert
from backend.schemas import (
    TargetCreate, TargetResponse, ScanResultResponse,
    TaskStatusResponse, LeakResponse, KeywordCreate,
    KeywordResponse, AlertResponse
)
from backend.celery_app import celery_app

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    # Trigger streaming ingestion in background worker
    task = celery_app.send_task("workers.tasks.ingest_leak_file", args=[file_path, source, leak_date])
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
