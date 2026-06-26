FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed for compiling package binaries (e.g. pg_config for psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend files. 
# We maintain the package structure so that imports like `from backend.config import settings` work properly.
COPY . ./backend

# Expose port 8000
EXPOSE 8000

# Set Python path to find backend modules
ENV PYTHONPATH=/app

# Start FastAPI via uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
