FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN useradd -m appuser

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Create data directory with proper ownership
RUN mkdir -p /app/data && chown -R appuser:appuser /app

WORKDIR /app/backend

ENV HOST=0.0.0.0
ENV PORT=8000
ENV DATA_DIR=/app/data
ENV DB_PATH=/app/data/izoldian.db

EXPOSE 8000

USER appuser

CMD uvicorn main:app --host $HOST --port $PORT