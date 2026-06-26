FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed for compiling package binaries (e.g. pg_config for psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install worker requirements
COPY ./workers/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy both backend (for celery configuration and models) and workers into the container
COPY ./backend ./backend
COPY ./workers ./workers

# Set Python path to find both modules
ENV PYTHONPATH=/app

# Start the Celery worker process
CMD ["celery", "-A", "backend.celery_app", "worker", "--loglevel=info"]
