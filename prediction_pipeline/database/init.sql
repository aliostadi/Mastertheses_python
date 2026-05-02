-- ========================================
-- Parking Prediction Database Schema
-- ========================================

-- Enable UUID extension for unique IDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ========================================
-- 1. Raw Minute-Level Data Table
--    Stores data collected every minute from API
-- ========================================
CREATE TABLE IF NOT EXISTS parking_availability_minute (
    id SERIAL PRIMARY KEY,
    minute_timestamp TIMESTAMPTZ NOT NULL,
    parking_lot_id INTEGER NOT NULL,
    free_spaces BIGINT,
    occupied_spaces BIGINT,
    total_spaces BIGINT,
    occupancy_rate NUMERIC(5,2),
    
    -- Additional metadata
    parking_lot_name VARCHAR(255),
    address VARCHAR(500),
    city VARCHAR(100),
    country VARCHAR(100),
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),
    
    -- Parking type details
    family_occupied INTEGER DEFAULT 0,
    family_total INTEGER DEFAULT 0,
    disabled_occupied INTEGER DEFAULT 0,
    disabled_total INTEGER DEFAULT 0,
    electrocharger_occupied INTEGER DEFAULT 0,
    electrocharger_total INTEGER DEFAULT 0,
    
    -- Data quality flag
    invalid BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint: one record per lot per minute
    UNIQUE(parking_lot_id, minute_timestamp)
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_parking_minute_timestamp 
    ON parking_availability_minute(minute_timestamp);

CREATE INDEX IF NOT EXISTS idx_parking_minute_lot_id 
    ON parking_availability_minute(parking_lot_id);

CREATE INDEX IF NOT EXISTS idx_parking_minute_lot_timestamp 
    ON parking_availability_minute(parking_lot_id, minute_timestamp DESC);


-- ========================================
-- 2. Hourly Aggregated Data Table
--    Transformed hourly data for training
-- ========================================
CREATE TABLE IF NOT EXISTS parking_availability_hourly (
    id SERIAL PRIMARY KEY,
    hour_timestamp TIMESTAMPTZ NOT NULL,
    parking_lot_id INTEGER NOT NULL,
    
    -- Aggregated availability metrics
    avg_free_spaces NUMERIC(10,2),
    min_free_spaces INTEGER,
    max_free_spaces INTEGER,
    free_spaces_range INTEGER,
    
    -- Time features
    hour_of_day INTEGER,
    day_of_week INTEGER,
    day_of_month INTEGER,
    calendar_week INTEGER,
    month_number INTEGER,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint
    UNIQUE(parking_lot_id, hour_timestamp)
);

CREATE INDEX IF NOT EXISTS idx_parking_hourly_timestamp 
    ON parking_availability_hourly(hour_timestamp);

CREATE INDEX IF NOT EXISTS idx_parking_hourly_lot_id 
    ON parking_availability_hourly(parking_lot_id);


-- ========================================
-- 3. Training Data with Features Table
--    Final processed data for ML predictions
-- ========================================
CREATE TABLE IF NOT EXISTS training_data_hourly (
    id SERIAL PRIMARY KEY,
    hour_timestamp TIMESTAMPTZ NOT NULL,
    parking_lot_id INTEGER NOT NULL,
    
    -- Parking availability features
    avg_free_spaces NUMERIC(10,2),
    min_free_spaces INTEGER,
    max_free_spaces INTEGER,
    free_spaces_range INTEGER,
    
    -- Time features
    hour_of_day INTEGER,
    day_of_week INTEGER,
    day_of_month INTEGER,
    calendar_week INTEGER,
    month_number INTEGER,
    
    -- Weather features
    temperature_2m NUMERIC(5,2),
    relative_humidity_2m NUMERIC(5,2),
    precipitation NUMERIC(7,2),
    
    -- Categorical features
    day_type VARCHAR(20),
    time_period VARCHAR(20),
    temperature_category VARCHAR(20),
    precipitation_category VARCHAR(20),
    
    -- Engineered features (will be added by transformer)
    avg_free_spaces_rolling_24h NUMERIC(10,2),
    avg_free_spaces_std_24h NUMERIC(10,2),
    avg_free_spaces_diff_1h NUMERIC(10,2),
    temperature_diff_1h NUMERIC(5,2),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint
    UNIQUE(parking_lot_id, hour_timestamp)
);

CREATE INDEX IF NOT EXISTS idx_training_data_timestamp 
    ON training_data_hourly(hour_timestamp);

CREATE INDEX IF NOT EXISTS idx_training_data_lot_id 
    ON training_data_hourly(parking_lot_id);


-- ========================================
-- 4. Predictions Table
--    Stores 24-hour ahead predictions
-- ========================================
CREATE TABLE IF NOT EXISTS predictions_24h (
    id SERIAL PRIMARY KEY,
    prediction_timestamp TIMESTAMPTZ NOT NULL,  -- When prediction was made
    parking_lot_id INTEGER NOT NULL,
    model_name VARCHAR(100),
    
    -- Predicted values for next 24 hours (array)
    predicted_free_spaces INTEGER[],
    
    -- Individual hour predictions (for easier querying)
    hour_1 INTEGER,
    hour_2 INTEGER,
    hour_3 INTEGER,
    hour_4 INTEGER,
    hour_5 INTEGER,
    hour_6 INTEGER,
    hour_7 INTEGER,
    hour_8 INTEGER,
    hour_9 INTEGER,
    hour_10 INTEGER,
    hour_11 INTEGER,
    hour_12 INTEGER,
    hour_13 INTEGER,
    hour_14 INTEGER,
    hour_15 INTEGER,
    hour_16 INTEGER,
    hour_17 INTEGER,
    hour_18 INTEGER,
    hour_19 INTEGER,
    hour_20 INTEGER,
    hour_21 INTEGER,
    hour_22 INTEGER,
    hour_23 INTEGER,
    hour_24 INTEGER,
    
    -- Model confidence/metadata
    confidence_score NUMERIC(5,4),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint: one prediction per lot per timestamp per model
    UNIQUE(parking_lot_id, prediction_timestamp, model_name)
);

CREATE INDEX IF NOT EXISTS idx_predictions_timestamp 
    ON predictions_24h(prediction_timestamp);

CREATE INDEX IF NOT EXISTS idx_predictions_lot_id 
    ON predictions_24h(parking_lot_id);

CREATE INDEX IF NOT EXISTS idx_predictions_created 
    ON predictions_24h(created_at DESC);


-- ========================================
-- 5a. Hourly Predictions Table (For ML Monitoring)
--     Each row = one hour prediction for easy comparison with actuals
-- ========================================
CREATE TABLE IF NOT EXISTS predictions_hourly (
    id SERIAL PRIMARY KEY,
    prediction_made_at TIMESTAMPTZ NOT NULL,    -- When prediction was generated
    target_hour TIMESTAMPTZ NOT NULL,            -- The hour being predicted
    parking_lot_id INTEGER NOT NULL,
    model_name VARCHAR(100),
    
    -- Prediction details
    hours_ahead INTEGER NOT NULL,                -- 1-24 (how many hours ahead)
    predicted_free_spaces INTEGER NOT NULL,
    
    -- For ML monitoring - will be filled later when actual data arrives
    actual_free_spaces INTEGER,                  -- Actual value (filled later)
    prediction_error NUMERIC(10,2),              -- predicted - actual
    absolute_error NUMERIC(10,2),                -- |predicted - actual|
    percentage_error NUMERIC(6,2),               -- |error| / actual * 100
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    evaluated_at TIMESTAMPTZ,                    -- When actual was filled in
    
    -- Unique constraint: one prediction per lot per target hour per model per prediction time
    UNIQUE(parking_lot_id, target_hour, model_name, prediction_made_at)
);

CREATE INDEX IF NOT EXISTS idx_predictions_hourly_target 
    ON predictions_hourly(target_hour);

CREATE INDEX IF NOT EXISTS idx_predictions_hourly_lot 
    ON predictions_hourly(parking_lot_id);

CREATE INDEX IF NOT EXISTS idx_predictions_hourly_made_at 
    ON predictions_hourly(prediction_made_at DESC);

CREATE INDEX IF NOT EXISTS idx_predictions_hourly_evaluation 
    ON predictions_hourly(target_hour, actual_free_spaces) 
    WHERE actual_free_spaces IS NULL;


-- ========================================
-- 6. Weather Data Hourly Table
--    Stores hourly weather data from Open-Meteo API
-- ========================================
CREATE TABLE IF NOT EXISTS weather_hourly (
    id SERIAL PRIMARY KEY,
    hour_timestamp TIMESTAMPTZ NOT NULL,
    
    -- Weather metrics
    temperature_2m NUMERIC(5,2),          -- Temperature at 2m height (°C)
    relative_humidity_2m NUMERIC(5,2),    -- Relative humidity at 2m (%)
    precipitation NUMERIC(7,2),           -- Precipitation (mm)
    
    -- Optional: Additional weather features
    wind_speed_10m NUMERIC(6,2),          -- Wind speed at 10m (km/h)
    weather_code INTEGER,                  -- WMO weather code
    
    -- Location
    latitude NUMERIC(10,7) DEFAULT 49.891,
    longitude NUMERIC(10,7) DEFAULT 10.887,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint: one record per hour
    UNIQUE(hour_timestamp)
);

CREATE INDEX IF NOT EXISTS idx_weather_hourly_timestamp 
    ON weather_hourly(hour_timestamp DESC);


-- ========================================
-- 6. Parking Lots Master Table (Optional)
--    Store parking lot metadata
-- ========================================
CREATE TABLE IF NOT EXISTS parking_lots (
    parking_lot_id INTEGER PRIMARY KEY,
    name VARCHAR(255),
    address VARCHAR(500),
    city VARCHAR(100),
    country VARCHAR(100),
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),
    total_spaces INTEGER,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_updated TIMESTAMPTZ DEFAULT NOW()
);


-- ========================================
-- Grant Permissions
-- ========================================
-- Grant all privileges to parking_user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO parking_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO parking_user;


-- ========================================
-- Sample View for Dashboard
-- ========================================
CREATE OR REPLACE VIEW latest_predictions AS
SELECT 
    p.parking_lot_id,
    pl.name AS parking_lot_name,
    p.prediction_timestamp,
    p.model_name,
    p.hour_1, p.hour_2, p.hour_3, p.hour_4, p.hour_5, p.hour_6,
    p.hour_7, p.hour_8, p.hour_9, p.hour_10, p.hour_11, p.hour_12,
    p.hour_13, p.hour_14, p.hour_15, p.hour_16, p.hour_17, p.hour_18,
    p.hour_19, p.hour_20, p.hour_21, p.hour_22, p.hour_23, p.hour_24,
    p.created_at
FROM predictions_24h p
LEFT JOIN parking_lots pl ON p.parking_lot_id = pl.parking_lot_id
WHERE p.created_at = (
    SELECT MAX(created_at) 
    FROM predictions_24h 
    WHERE parking_lot_id = p.parking_lot_id
);


-- ========================================
-- Success Message
-- ========================================
DO $$
BEGIN
    RAISE NOTICE '✅ Database schema created successfully!';
    RAISE NOTICE '📊 Tables created:';
    RAISE NOTICE '   - parking_availability_minute (raw data)';
    RAISE NOTICE '   - parking_availability_hourly (aggregated)';
    RAISE NOTICE '   - training_data_hourly (with features)';
    RAISE NOTICE '   - predictions_24h (model predictions)';
    RAISE NOTICE '   - weather_hourly (weather data)';
    RAISE NOTICE '   - parking_lots (metadata)';
END $$;
