@echo off
REM ============================================================================
REM prepare_training_data.bat - Master script for data preparation pipeline
REM ============================================================================
REM Correct order:
REM 1. Ingest parking data from API (once)
REM 2. Ingest weather data from API (once)
REM 3. For each lot: minute -> hourly -> training data
REM ============================================================================

REM Change to script directory (so requirements.txt is found)
cd /d "%~dp0"
if errorlevel 1 (
    echo Error: Failed to change to script directory
    pause
    exit /b 1
)

echo.
echo ============================================================================
echo  Training Data Preparation Pipeline
echo ============================================================================
echo.

REM ============================================================================
REM SETUP: Virtual Environment and Dependencies
REM ============================================================================

REM Check if virtual environment exists, create if not
if not exist venv (
    echo Creating Python virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Error: Failed to create virtual environment
        echo Make sure Python 3.9+ is installed
        pause
        exit /b 1
    )
    echo Virtual environment created!
)

REM Activate virtual environment
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo Error: Failed to activate virtual environment
    pause
    exit /b 1
)

REM Install/upgrade requirements if needed
echo.
echo Checking Python dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo Error: Failed to install requirements
    pause
    exit /b 1
)
echo Dependencies ready!
echo.




REM ============================================================================
REM PHASE 1: INGEST RAW DATA FROM APIs
REM ============================================================================

echo Phase 1: Ingesting data from APIs...
echo.

REM Step 1: Ingest parking data
echo Step 1/8: Fetching parking data from API...
python -m src.raw_data_processing.ingest_parking_data
if errorlevel 1 (
    echo Error: Failed to ingest parking data
    pause
    exit /b 1
)
echo OK
echo.

REM Step 2: Ingest weather data
echo Step 2/8: Fetching weather data from API...
python -m src.raw_data_processing.ingest_weather_data
if errorlevel 1 (
    echo Error: Failed to ingest weather data
    pause
    exit /b 1
)
echo OK
echo.

REM ============================================================================
REM PHASE 2: PROCESS LOT 38
REM ============================================================================

echo Phase 2: Processing Lot 38...
echo.

REM Step 3: Parking minute-level data (Lot 38)
echo Step 3/8: Creating minute-level data for Lot 38...
python -m src.raw_data_processing.parking_availability_minute_lot38
if errorlevel 1 (
    echo Error: Failed to create minute data for Lot 38
    pause
    exit /b 1
)
echo OK
echo.

REM Step 4: Parking hourly aggregation (Lot 38)
echo Step 4/8: Aggregating to hourly for Lot 38...
python -m src.raw_data_processing.parking_availability_hourly_lot38
if errorlevel 1 (
    echo Error: Failed to aggregate to hourly for Lot 38
    pause
    exit /b 1
)
echo OK
echo.

REM Step 5: Training data (Lot 38)
echo Step 5/8: Creating training data for Lot 38...
python -m src.raw_data_processing.create_training_data_lot38
if errorlevel 1 (
    echo Error: Failed to create training data for Lot 38
    pause
    exit /b 1
)
echo OK
echo.

REM ============================================================================
REM PHASE 3: PROCESS LOT 634
REM ============================================================================

echo Phase 3: Processing Lot 634...
echo.

REM Step 6: Parking minute-level data (Lot 634)
echo Step 6/8: Creating minute-level data for Lot 634...
python -m src.raw_data_processing.parking_availability_minute_lot634
if errorlevel 1 (
    echo Error: Failed to create minute data for Lot 634
    pause
    exit /b 1
)
echo OK
echo.

REM Step 7: Parking hourly aggregation (Lot 634)
echo Step 7/8: Aggregating to hourly for Lot 634...
python -m src.raw_data_processing.parking_availability_hourly_lot634
if errorlevel 1 (
    echo Error: Failed to aggregate to hourly for Lot 634
    pause
    exit /b 1
)
echo OK
echo.

REM Step 8: Training data (Lot 634)
echo Step 8/8: Creating training data for Lot 634...
python -m src.raw_data_processing.create_training_data_lot634
if errorlevel 1 (
    echo Error: Failed to create training data for Lot 634
    pause
    exit /b 1
)
echo OK
echo.

echo ============================================================================
echo  SUCCESS! All data preparation steps completed
echo ============================================================================
echo.
echo Training tables created:
echo  - ali_training_data_hourly_availability_hourly_lot38
echo  - ali_training_data_hourly_availability_hourly_lot634
echo.
echo Next step: Train ML models
echo  Run: train_models.bat
echo.
pause
