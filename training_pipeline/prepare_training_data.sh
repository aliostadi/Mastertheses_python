#!/bin/bash
# ============================================================================
# prepare_training_data.sh - Master script for data preparation pipeline
# ============================================================================
# Correct order:
# 1. Ingest parking data from API (once)
# 2. Ingest weather data from API (once)
# 3. For each lot: minute -> hourly -> training data
# ============================================================================

set -e  # Exit on error

echo ""
echo "============================================================================"
echo "  Training Data Preparation Pipeline"
echo "============================================================================"
echo ""

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python -m venv venv
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create virtual environment"
        echo "Make sure Python 3.9+ is installed"
        exit 1
    fi
    echo "Virtual environment created!"
fi

# Activate virtual environment
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "Error: Failed to activate virtual environment"
    exit 1
fi

# Install/upgrade requirements if needed
echo ""
echo "Checking Python dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error: Failed to install requirements"
    exit 1
fi
echo "Dependencies ready!"

# ============================================================================
# PHASE 1: INGEST RAW DATA FROM APIs
# ============================================================================

echo "Phase 1: Ingesting data from APIs..."
echo ""

# Step 1: Ingest parking data
echo "Step 1/8: Fetching parking data from API..."
python -m src.raw_data_processing.ingest_parking_data
echo "OK"
echo ""

# Step 2: Ingest weather data
echo "Step 2/8: Fetching weather data from API..."
python -m src.raw_data_processing.ingest_weather_data
echo "OK"
echo ""

# ============================================================================
# PHASE 2: PROCESS LOT 38
# ============================================================================

echo "Phase 2: Processing Lot 38..."
echo ""

# Step 3: Parking minute-level data (Lot 38)
echo "Step 3/8: Creating minute-level data for Lot 38..."
python -m src.raw_data_processing.parking_availability_minute_lot38
echo "OK"
echo ""

# Step 4: Parking hourly aggregation (Lot 38)
echo "Step 4/8: Aggregating to hourly for Lot 38..."
python -m src.raw_data_processing.parking_availability_hourly_lot38
echo "OK"
echo ""

# Step 5: Training data (Lot 38)
echo "Step 5/8: Creating training data for Lot 38..."
python -m src.raw_data_processing.create_training_data_lot38
echo "OK"
echo ""

# ============================================================================
# PHASE 3: PROCESS LOT 634
# ============================================================================

echo "Phase 3: Processing Lot 634..."
echo ""

# Step 6: Parking minute-level data (Lot 634)
echo "Step 6/8: Creating minute-level data for Lot 634..."
python -m src.raw_data_processing.parking_availability_minute_lot634
echo "OK"
echo ""

# Step 7: Parking hourly aggregation (Lot 634)
echo "Step 7/8: Aggregating to hourly for Lot 634..."
python -m src.raw_data_processing.parking_availability_hourly_lot634
echo "OK"
echo ""

# Step 8: Training data (Lot 634)
echo "Step 8/8: Creating training data for Lot 634..."
python -m src.raw_data_processing.create_training_data_lot634
echo "OK"
echo ""

echo "============================================================================"
echo "  SUCCESS! All data preparation steps completed"
echo "============================================================================"
echo ""
echo "Training tables created:"
echo "  - ali_training_data_hourly_availability_hourly_lot38"
echo "  - ali_training_data_hourly_availability_hourly_lot634"
echo ""
echo "Next step: Train ML models"
echo "  Run: bash train_models.sh"
echo ""
