FROM python:3.9-slim

WORKDIR /app

# Install PostgreSQL client
RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy transformation scripts
COPY hourly_aggregator.py .
COPY feature_engineer.py .
COPY transformer_scheduler.py .

# Run scheduler that executes transformations at :05 past each hour
CMD ["python", "transformer_scheduler.py"]
