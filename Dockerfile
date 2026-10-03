FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run as an unprivileged user
RUN useradd --create-home appuser
USER appuser

# Cloud Run sets $PORT (8080 by default)
EXPOSE 8080

# Threads let a worker keep serving while a request waits on TMDB / OpenAI / OpenSubtitles.
# Worker count and timeout come from GUNICORN_CMD_ARGS on the Cloud Run service.
CMD exec gunicorn --bind :${PORT:-8080} --threads 8 app:app
