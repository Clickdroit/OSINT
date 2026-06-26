from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.config import settings

# Create engine (using pool parameters suitable for multi-worker backend)
engine = create_engine(
    settings.db_url,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get db session in FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    # Import models here to register them with Base
    import backend.models
    # 1. Enable pg_trgm extension for GIN trigram indexes (committed immediately)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        
    # 2. Try to add details column if not exists (in its own transaction to prevent rollback of extension)
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE scan_results ADD COLUMN IF NOT EXISTS details TEXT;"))
    except Exception as e:
        print(f"[DB init] details column check/add skipped: {str(e)}")
        
    # 3. Create all tables
    Base.metadata.create_all(bind=engine)
