from celery import Celery
from backend.config import settings

# Initialize Celery app
# Include 'workers.tasks' so workers import the task definitions on startup
celery_app = Celery(
    "hub_osint",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=["workers.tasks"]
)

# Standard configurations
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,  # 30 minutes limit per task (e.g. big ingestion)
)

# Configure Celery Beat periodic schedule for RSS scraper if running Celery Beat
celery_app.conf.beat_schedule = {
    "run-rss-monitoring-every-hour": {
        "task": "workers.tasks.check_rss_feeds",
        "schedule": settings.RSS_REFRESH_INTERVAL_SECONDS,
    }
}
