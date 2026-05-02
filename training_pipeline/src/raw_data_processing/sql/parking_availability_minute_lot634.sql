-- Create indexes for optimal performance
CREATE INDEX IF NOT EXISTS idx_parking_lot_arrival_departure
ON public.ali_parking_operations_2025_11_29 
(parking_lot_id, arrival_unix_seconds_humanreadable, departure_unix_seconds_humanreadable);

CREATE INDEX IF NOT EXISTS idx_arrival_departure_timestamps
ON public.ali_parking_operations_2025_11_29 
(arrival_unix_seconds_humanreadable, departure_unix_seconds_humanreadable);

-- Create table for parking availability per minute for lot 634
DROP TABLE IF EXISTS parking_availability_minute_lot634;

CREATE TABLE ali_parking_availability_minute_lot634 AS
WITH minute_series AS (
  SELECT generate_series(
    date_trunc('day', MIN(arrival_unix_seconds_humanreadable)),
    date_trunc('day', MAX(departure_unix_seconds_humanreadable)) + interval '1 day',
    interval '1 minute'
  ) AS minute_timestamp
  FROM public.ali_parking_operations_2025_11_29 
  WHERE parking_lot_id = 634
),

occupancy_per_minute AS (
  SELECT 
    ms.minute_timestamp,
    COUNT(po.parking_space_id) as occupied_spaces
  FROM minute_series ms
  LEFT JOIN public.ali_parking_operations_2025_11_29 po ON
    po.parking_lot_id = 634 AND
    ms.minute_timestamp >= po.arrival_unix_seconds_humanreadable AND
    ms.minute_timestamp < po.departure_unix_seconds_humanreadable
  GROUP BY ms.minute_timestamp
)

SELECT 
  minute_timestamp,
  634 as parking_lot_id,
  64 - occupied_spaces as free_spaces,
  occupied_spaces
  
FROM occupancy_per_minute
ORDER BY minute_timestamp;

-- Create index on result table for fast querying
CREATE INDEX if NOT EXISTS idx_availability_timestamp634 ON ali_parking_availability_minute_lot634 (minute_timestamp);
CREATE INDEX if NOT EXISTS   idx_availability_lot_timestamp634 ON ali_parking_availability_minute_lot634 (parking_lot_id, minute_timestamp);