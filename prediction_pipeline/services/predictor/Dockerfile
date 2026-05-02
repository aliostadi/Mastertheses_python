FROM python:3.9-slim

WORKDIR /app

# Copy hybrid requirements first (for Docker layer caching)
COPY requirements-hybrid.txt requirements.txt

# Install Python dependencies including TensorFlow and XGBoost
RUN pip install --no-cache-dir -r requirements.txt

# Copy predictor code
COPY parking_predictor.py .
COPY parking_predictor_hybrid.py .
COPY prediction_scheduler.py .

# Copy models (prepared by prepare_models.sh/bat)
COPY models/ /app/models/

# Set environment variable for model directory
ENV MODEL_DIR=/app/models

# Create output directory
RUN mkdir -p /app/prediction_results

# Run scheduler that executes predictions at :10 past each hour
CMD ["python", "prediction_scheduler.py"]
