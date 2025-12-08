-- Create indexes for faster aggregation on the minute-level table
CREATE INDEX IF NOT EXISTS idx_parking_availability_minute_timestamp 
ON ali_parking_availability_minute_lot38 (minute_timestamp);

-- Note: Cannot create index on date_trunc function directly due to immutability
-- The minute_timestamp index will still help with aggregation queries

-- Create hourly average free spaces table
CREATE TABLE ali_parking_availability_hourly_lot38 AS
WITH hourly_aggregation AS (
    SELECT 
        date_trunc('hour', minute_timestamp) AS hour_timestamp,
        parking_lot_id,
        AVG(free_spaces) AS avg_free_spaces,
        MIN(free_spaces) AS min_free_spaces,
        MAX(free_spaces) AS max_free_spaces       
     
    FROM ali_parking_availability_minute_lot38
    WHERE parking_lot_id = 38
    GROUP BY date_trunc('hour', minute_timestamp), parking_lot_id
)
SELECT 
    hour_timestamp,
    parking_lot_id,
    ROUND(avg_free_spaces, 2) AS avg_free_spaces,
    min_free_spaces,
    max_free_spaces,
    -- Additional calculated fields
    ROUND(max_free_spaces - min_free_spaces, 2) AS free_spaces_range,
    EXTRACT(HOUR FROM hour_timestamp) AS hour_of_day,
    EXTRACT(DOW FROM hour_timestamp) AS day_of_week,  -- 0=Sunday, 6=Saturday
    TO_CHAR(hour_timestamp, 'Day') AS weekday_name,   -- 'Sunday   ', 'Monday   ', etc.
    EXTRACT(DAY FROM hour_timestamp) AS day_of_month,  -- 1, 2, 3, ..., 31
    EXTRACT(WEEK FROM hour_timestamp) AS calendar_week,  -- 1-53 (ISO week)
    EXTRACT(MONTH FROM hour_timestamp) AS month_number,  -- 1-12
    TO_CHAR(hour_timestamp, 'Month') AS month_name      -- 'January  ', 'February ', etc.
FROM hourly_aggregation
ORDER BY hour_timestamp;

-- Create indexes on the new hourly table for fast querying
CREATE INDEX idx_parking_hourly_timestamp 
ON ali_parking_availability_hourly_lot38 (hour_timestamp);

CREATE INDEX idx_parking_hourly_hour_of_day 
ON ali_parking_availability_hourly_lot38 (hour_of_day);

CREATE INDEX idx_parking_hourly_day_of_week 
ON ali_parking_availability_hourly_lot38 (day_of_week);

CREATE INDEX idx_parking_hourly_avg_free_spaces 
ON ali_parking_availability_hourly_lot38 (avg_free_spaces);

CREATE INDEX idx_parking_hourly_day_of_month 
ON ali_parking_availability_hourly_lot38 (day_of_month);

CREATE INDEX idx_parking_hourly_calendar_week 
ON ali_parking_availability_hourly_lot38 (calendar_week);

CREATE INDEX idx_parking_hourly_month_number 
ON ali_parking_availability_hourly_lot38 (month_number);
