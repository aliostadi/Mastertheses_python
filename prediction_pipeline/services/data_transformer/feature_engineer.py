"""
Data Transformation Service - Step 2: Feature Engineering
Combines hourly parking data with weather data and creates engineered features
Creates final inference-ready data matching the training data format
"""

import os
import sys
import logging
import psycopg2
from datetime import datetime, timedelta

# Fix Windows encoding issues
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Try to load .env if running locally (optional for container)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('feature_engineer.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class FeatureEngineer:
    """Combines parking + weather data and creates engineered features"""
    
    def __init__(self):
        """Initialize database connection parameters"""
        # Validate required database credentials
        db_password = os.getenv('DB_PASSWORD')
        if not db_password:
            raise ValueError("DB_PASSWORD must be set in environment variables")
        
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', '5432')),
            'database': os.getenv('DB_NAME', 'parking_predictions'),
            'user': os.getenv('DB_USER', 'parking_user'),
            'password': db_password
        }
        logger.info(f"Feature Engineer initialized for DB: {self.db_config['database']}")
    
    def get_connection(self):
        """Create and return database connection"""
        try:
            conn = psycopg2.connect(**self.db_config)
            return conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
    
    def create_training_data_last_hour(self):
        """
        Create training data for the last complete hour
        Joins parking_availability_hourly with weather_hourly
        Adds categorical features and rolling/diff features
        """
        conn = None
        cursor = None
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Get the last complete hour
            now = datetime.now()
            last_complete_hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
            
            logger.info(f"Creating training data for hour: {last_complete_hour.strftime('%Y-%m-%d %H:%M')}")
            
            # SQL to join parking + weather and create features
            feature_engineering_query = """
                WITH hourly_with_weather AS (
                    SELECT 
                        p.hour_timestamp,
                        p.parking_lot_id,
                        p.avg_free_spaces,
                        p.min_free_spaces,
                        p.max_free_spaces,
                        p.free_spaces_range,
                        p.hour_of_day,
                        p.day_of_week,
                        p.day_of_month,
                        p.calendar_week,
                        p.month_number,
                        w.temperature_2m,
                        w.relative_humidity_2m,
                        w.precipitation
                    FROM parking_availability_hourly p
                    LEFT JOIN weather_hourly w 
                        ON date_trunc('hour', p.hour_timestamp) = date_trunc('hour', w.hour_timestamp)
                    WHERE p.hour_timestamp = %s
                ),
                with_categorical AS (
                    SELECT 
                        *,
                        -- Day type
                        CASE 
                            WHEN day_of_week IN (0, 6) THEN 'weekend'
                            ELSE 'weekday'
                        END AS day_type,
                        
                        -- Time period
                        CASE 
                            WHEN hour_of_day BETWEEN 6 AND 11 THEN 'morning'
                            WHEN hour_of_day BETWEEN 12 AND 17 THEN 'afternoon'
                            WHEN hour_of_day BETWEEN 18 AND 22 THEN 'evening'
                            ELSE 'night'
                        END AS time_period,
                        
                        -- Temperature category
                        CASE 
                            WHEN temperature_2m < 0 THEN 'freezing'
                            WHEN temperature_2m BETWEEN 0 AND 10 THEN 'cold'
                            WHEN temperature_2m BETWEEN 10 AND 20 THEN 'mild'
                            ELSE 'warm'
                        END AS temperature_category,
                        
                        -- Precipitation category
                        CASE 
                            WHEN precipitation = 0 THEN 'none'
                            WHEN precipitation < 2.5 THEN 'light'
                            WHEN precipitation < 10 THEN 'moderate'
                            ELSE 'heavy'
                        END AS precipitation_category
                    FROM hourly_with_weather
                ),
                with_rolling_features AS (
                    SELECT 
                        c.*,
                        -- Rolling 24h average (need historical data)
                        (
                            SELECT AVG(p2.avg_free_spaces)
                            FROM parking_availability_hourly p2
                            WHERE p2.parking_lot_id = c.parking_lot_id
                              AND p2.hour_timestamp > (c.hour_timestamp - INTERVAL '24 hours')
                              AND p2.hour_timestamp <= c.hour_timestamp
                        ) AS avg_free_spaces_rolling_24h,
                        
                        -- Rolling 24h std (need historical data)
                        (
                            SELECT STDDEV(p2.avg_free_spaces)
                            FROM parking_availability_hourly p2
                            WHERE p2.parking_lot_id = c.parking_lot_id
                              AND p2.hour_timestamp > (c.hour_timestamp - INTERVAL '24 hours')
                              AND p2.hour_timestamp <= c.hour_timestamp
                        ) AS avg_free_spaces_std_24h,
                        
                        -- 1-hour difference
                        (
                            c.avg_free_spaces - 
                            (
                                SELECT p3.avg_free_spaces
                                FROM parking_availability_hourly p3
                                WHERE p3.parking_lot_id = c.parking_lot_id
                                  AND p3.hour_timestamp = (c.hour_timestamp - INTERVAL '1 hour')
                                LIMIT 1
                            )
                        ) AS avg_free_spaces_diff_1h,
                        
                        -- Temperature 1-hour difference
                        (
                            c.temperature_2m - 
                            (
                                SELECT w2.temperature_2m
                                FROM weather_hourly w2
                                WHERE w2.hour_timestamp = (c.hour_timestamp - INTERVAL '1 hour')
                                LIMIT 1
                            )
                        ) AS temperature_diff_1h
                    FROM with_categorical c
                )
                INSERT INTO training_data_hourly (
                    hour_timestamp,
                    parking_lot_id,
                    avg_free_spaces,
                    min_free_spaces,
                    max_free_spaces,
                    free_spaces_range,
                    hour_of_day,
                    day_of_week,
                    day_of_month,
                    calendar_week,
                    month_number,
                    temperature_2m,
                    relative_humidity_2m,
                    precipitation,
                    day_type,
                    time_period,
                    temperature_category,
                    precipitation_category,
                    avg_free_spaces_rolling_24h,
                    avg_free_spaces_std_24h,
                    avg_free_spaces_diff_1h,
                    temperature_diff_1h
                )
                SELECT 
                    hour_timestamp,
                    parking_lot_id,
                    avg_free_spaces,
                    min_free_spaces,
                    max_free_spaces,
                    free_spaces_range,
                    hour_of_day,
                    day_of_week,
                    day_of_month,
                    calendar_week,
                    month_number,
                    temperature_2m,
                    relative_humidity_2m,
                    precipitation,
                    day_type,
                    time_period,
                    temperature_category,
                    precipitation_category,
                    avg_free_spaces_rolling_24h,
                    avg_free_spaces_std_24h,
                    avg_free_spaces_diff_1h,
                    temperature_diff_1h
                FROM with_rolling_features
                ON CONFLICT (parking_lot_id, hour_timestamp) 
                DO UPDATE SET
                    avg_free_spaces = EXCLUDED.avg_free_spaces,
                    min_free_spaces = EXCLUDED.min_free_spaces,
                    max_free_spaces = EXCLUDED.max_free_spaces,
                    free_spaces_range = EXCLUDED.free_spaces_range,
                    hour_of_day = EXCLUDED.hour_of_day,
                    day_of_week = EXCLUDED.day_of_week,
                    day_of_month = EXCLUDED.day_of_month,
                    calendar_week = EXCLUDED.calendar_week,
                    month_number = EXCLUDED.month_number,
                    temperature_2m = EXCLUDED.temperature_2m,
                    relative_humidity_2m = EXCLUDED.relative_humidity_2m,
                    precipitation = EXCLUDED.precipitation,
                    day_type = EXCLUDED.day_type,
                    time_period = EXCLUDED.time_period,
                    temperature_category = EXCLUDED.temperature_category,
                    precipitation_category = EXCLUDED.precipitation_category,
                    avg_free_spaces_rolling_24h = EXCLUDED.avg_free_spaces_rolling_24h,
                    avg_free_spaces_std_24h = EXCLUDED.avg_free_spaces_std_24h,
                    avg_free_spaces_diff_1h = EXCLUDED.avg_free_spaces_diff_1h,
                    temperature_diff_1h = EXCLUDED.temperature_diff_1h,
                    created_at = NOW()
                RETURNING parking_lot_id, hour_timestamp, avg_free_spaces, temperature_2m
            """
            
            cursor.execute(feature_engineering_query, (last_complete_hour,))
            results = cursor.fetchall()
            conn.commit()
            
            if results:
                logger.info(f"✅ Created training data for {len(results)} parking lots at hour {last_complete_hour.strftime('%Y-%m-%d %H:00')}")
                for parking_lot_id, hour_ts, avg_free, temp in results[:3]:  # Log first 3
                    logger.info(f"   Lot {parking_lot_id}: {hour_ts.strftime('%Y-%m-%d %H:00')} - Free: {float(avg_free):.2f}, Temp: {float(temp) if temp else 'N/A'}°C")
            else:
                logger.warning(f"No training data created for hour {last_complete_hour.strftime('%Y-%m-%d %H:00')}")
            
            return len(results)
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error in feature engineering: {e}")
            return 0
            
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def check_hourly_data_availability(self):
        """Check if hourly parking and weather data exist for the last hour"""
        conn = None
        cursor = None
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            now = datetime.now()
            last_hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
            
            # Check parking data
            cursor.execute("""
                SELECT COUNT(*) 
                FROM parking_availability_hourly 
                WHERE hour_timestamp = %s
            """, (last_hour,))
            parking_count = cursor.fetchone()[0]
            
            # Check weather data
            cursor.execute("""
                SELECT COUNT(*) 
                FROM weather_hourly 
                WHERE hour_timestamp = %s
            """, (last_hour,))
            weather_count = cursor.fetchone()[0]
            
            logger.info(f"Found {parking_count} parking records and {weather_count} weather records for last hour")
            
            return parking_count > 0 and weather_count > 0
            
        except Exception as e:
            logger.error(f"Error checking data availability: {e}")
            return False
            
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()


def main():
    """Main entry point"""
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║       Feature Engineering Service                        ║
    ║       Parking + Weather → Training Data                  ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    logger.info("=" * 60)
    logger.info("Starting feature engineering process")
    logger.info("=" * 60)
    
    try:
        engineer = FeatureEngineer()
        
        # Check if data is available
        if not engineer.check_hourly_data_availability():
            logger.warning("⚠️  Required hourly data not available. Make sure hourly aggregation ran first.")
            return
        
        # Create training data
        record_count = engineer.create_training_data_last_hour()
        
        if record_count > 0:
            logger.info(f"✅ Feature engineering completed successfully: {record_count} records")
        else:
            logger.warning("⚠️  No training data created")
        
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        sys.exit(1)
    
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
