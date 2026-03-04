FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY backend/ ./backend/
COPY frontend/ ./frontend/

WORKDIR /app/backend

# Create data directory
RUN mkdir -p /app/data

ENV DATA_DIR=/app/data
ENV DB_PATH=/app/data/izoldian.db

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
