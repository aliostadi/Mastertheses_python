"""
Data Transformation Service - Step 1: Hourly Aggregation
Aggregates minute-level parking data to hourly averages
Runs every hour to process the last hour of minute data
"""

import os
import sys
import logging
import psycopg2

# Fix Windows encoding issues
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
from datetime import datetime, timedelta

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
        logging.FileHandler('hourly_aggregator.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class HourlyAggregator:
    """Aggregates minute-level parking data to hourly format"""
    
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
        logger.info(f"Hourly Aggregator initialized for DB: {self.db_config['database']}")
    
    def get_connection(self):
        """Create and return database connection"""
        try:
            conn = psycopg2.connect(**self.db_config)
            return conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
    
    def aggregate_last_hour(self):
        """
        Aggregate the last complete hour of minute data
        Computes avg, min, max and time features
        """
        conn = None
        cursor = None
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Get the last complete hour
            # If now is 15:45, we process hour 14:00-14:59
            now = datetime.now()
            last_complete_hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
            hour_start = last_complete_hour
            hour_end = last_complete_hour + timedelta(hours=1)
            
            logger.info(f"Aggregating data for hour: {hour_start.strftime('%Y-%m-%d %H:%M')} to {hour_end.strftime('%Y-%m-%d %H:%M')}")
            
            # SQL to aggregate minute data to hourly
            aggregation_query = """
                INSERT INTO parking_availability_hourly (
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
                    month_number
                )
                SELECT 
                    date_trunc('hour', minute_timestamp) AS hour_timestamp,
                    parking_lot_id,
                    AVG(free_spaces) AS avg_free_spaces,
                    MIN(free_spaces) AS min_free_spaces,
                    MAX(free_spaces) AS max_free_spaces,
                    (MAX(free_spaces) - MIN(free_spaces)) AS free_spaces_range,
                    EXTRACT(HOUR FROM date_trunc('hour', minute_timestamp)) AS hour_of_day,
                    EXTRACT(DOW FROM date_trunc('hour', minute_timestamp)) AS day_of_week,
                    EXTRACT(DAY FROM date_trunc('hour', minute_timestamp)) AS day_of_month,
                    EXTRACT(WEEK FROM date_trunc('hour', minute_timestamp)) AS calendar_week,
                    EXTRACT(MONTH FROM date_trunc('hour', minute_timestamp)) AS month_number
                FROM parking_availability_minute
                WHERE minute_timestamp >= %s 
                  AND minute_timestamp < %s
                  AND free_spaces IS NOT NULL
                GROUP BY date_trunc('hour', minute_timestamp), parking_lot_id
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
                    created_at = NOW()
                RETURNING parking_lot_id, hour_timestamp, avg_free_spaces
            """
            
            cursor.execute(aggregation_query, (hour_start, hour_end))
            results = cursor.fetchall()
            conn.commit()
            
            if results:
                logger.info(f"✅ Aggregated {len(results)} parking lot records for hour {hour_start.strftime('%Y-%m-%d %H:00')}")
                for parking_lot_id, hour_ts, avg_free in results[:3]:  # Log first 3
                    logger.info(f"   Lot {parking_lot_id}: {hour_ts.strftime('%Y-%m-%d %H:00')} - Avg Free: {float(avg_free):.2f}")
            else:
                logger.warning(f"No data found for hour {hour_start.strftime('%Y-%m-%d %H:00')}")
            
            return len(results)
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error in hourly aggregation: {e}")
            return 0
            
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def check_minute_data_availability(self):
        """Check if minute data exists for the last hour"""
        conn = None
        cursor = None
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            now = datetime.now()
            last_hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
            
            cursor.execute("""
                SELECT COUNT(*) 
                FROM parking_availability_minute 
                WHERE minute_timestamp >= %s AND minute_timestamp < %s
            """, (last_hour, last_hour + timedelta(hours=1)))
            
            count = cursor.fetchone()[0]
            logger.info(f"Found {count} minute records for last complete hour")
            
            return count > 0
            
        except Exception as e:
            logger.error(f"Error checking minute data: {e}")
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
    ║       Hourly Aggregation Service                         ║
    ║       Transform Minute → Hourly Data                     ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    logger.info("=" * 60)
    logger.info("Starting hourly aggregation process")
    logger.info("=" * 60)
    
    try:
        aggregator = HourlyAggregator()
        
        # Check if data is available
        if not aggregator.check_minute_data_availability():
            logger.warning("⚠️  No minute data available for last hour. Skipping aggregation.")
            return
        
        # Perform aggregation
        record_count = aggregator.aggregate_last_hour()
        
        if record_count > 0:
            logger.info(f"✅ Hourly aggregation completed successfully: {record_count} records")
        else:
            logger.warning("⚠️  No records aggregated")
        
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        sys.exit(1)
    
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
