FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# default values (can be overridden by docker-compose)
ENV HOST=0.0.0.0
ENV PORT=8000
ENV DATA_DIR=/app/data
ENV DB_PATH=/app/data/izoldian.db

# create non-root user
RUN useradd -u 1000 -m appuser

# install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy source
COPY --chown=appuser:appuser backend/ ./backend/
COPY --chown=appuser:appuser frontend/ ./frontend/

# create data directory
RUN mkdir -p /app/data && chown appuser:appuser /app/data

WORKDIR /app/backend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]