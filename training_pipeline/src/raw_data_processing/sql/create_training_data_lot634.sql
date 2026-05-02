-- Create training data table by joining parking availability with weather data
CREATE TABLE if NOT EXISTS ali_training_data_hourly_availability_hourly_lot634 AS
SELECT 
    p.hour_timestamp,
    p.parking_lot_id,
    p.avg_free_spaces,
    p.min_free_spaces,
    p.max_free_spaces,
    p.free_spaces_range,
    p.hour_of_day,
    p.day_of_week,
    p.weekday_name,
    p.day_of_month,
    p.calendar_week,
    p.month_number,
    p.month_name,
    -- Weather data
    w.temperature_2m,
    w.relative_humidity_2m,
    w.precipitation,
    -- Additional derived features
    CASE 
        WHEN p.day_of_week IN (0, 6) THEN 'Weekend'
        ELSE 'Weekday'
    END AS day_type,
    CASE 
        WHEN p.hour_of_day BETWEEN 6 AND 9 THEN 'Morning Rush'
        WHEN p.hour_of_day BETWEEN 10 AND 16 THEN 'Daytime'
        WHEN p.hour_of_day BETWEEN 17 AND 19 THEN 'Evening Rush'
        WHEN p.hour_of_day BETWEEN 20 AND 23 THEN 'Evening'
        ELSE 'Night'
    END AS time_period,
    CASE 
        WHEN w.temperature_2m < 0 THEN 'Freezing'
        WHEN w.temperature_2m BETWEEN 0 AND 10 THEN 'Cold'
        WHEN w.temperature_2m BETWEEN 11 AND 20 THEN 'Mild'
        WHEN w.temperature_2m BETWEEN 21 AND 30 THEN 'Warm'
        ELSE 'Hot'
    END AS temperature_category,
    CASE 
        WHEN w.precipitation = 0 THEN 'No Rain'
        WHEN w.precipitation <= 2.5 THEN 'Light Rain'
        WHEN w.precipitation <= 10 THEN 'Moderate Rain'
        ELSE 'Heavy Rain'
    END AS precipitation_category
FROM ali_parking_availability_hourly_lot634 p
INNER JOIN ali_weather_bamberg_hourly w 
    ON p.hour_timestamp = w.timestamp
ORDER BY p.hour_timestamp;

-- Create indexes for fast querying on the training data table
CREATE INDEX if NOT EXISTS idx_training_data_timestamp 
ON ali_training_data_hourly_availability_hourly_lot634 (hour_timestamp);

CREATE INDEX if NOT EXISTS idx_training_data_hour_of_day 
ON ali_training_data_hourly_availability_hourly_lot634 (hour_of_day);

CREATE INDEX if NOT EXISTS idx_training_data_day_type 
ON ali_training_data_hourly_availability_hourly_lot634 (day_type);

CREATE INDEX if NOT EXISTS idx_training_data_time_period 
ON ali_training_data_hourly_availability_hourly_lot634 (time_period);

CREATE INDEX if NOT EXISTS idx_training_data_temperature 
ON ali_training_data_hourly_availability_hourly_lot634 (temperature_2m);

CREATE INDEX if NOT EXISTS idx_training_data_precipitation 
ON ali_training_data_hourly_availability_hourly_lot634 (precipitation);

CREATE INDEX if NOT EXISTS idx_training_data_avg_free_spaces 
ON ali_training_data_hourly_availability_hourly_lot634 (avg_free_spaces);
