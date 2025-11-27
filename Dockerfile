FROM python:3.11-slim

# Install system dependencies (Postgres client)
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the port
EXPOSE 8080

# Default command to run the web server
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]