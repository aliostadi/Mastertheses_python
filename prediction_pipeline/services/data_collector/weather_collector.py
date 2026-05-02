"""
Weather Data Collector Service
Fetches hourly weather data from Open-Meteo API and stores in PostgreSQL
Runs every hour to collect current and forecast weather data
"""

import os
import sys
import logging
import requests
import psycopg2
from datetime import datetime, timedelta
import schedule
import time

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
        logging.FileHandler('weather_collector.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class WeatherAPIClient:
    """Client for Open-Meteo Weather API"""
    
    def __init__(self, latitude=49.891, longitude=10.887):
        """
        Initialize Weather API Client
        
        Args:
            latitude: Latitude coordinate (default: Bamberg)
            longitude: Longitude coordinate (default: Bamberg)
        """
        self.latitude = latitude
        self.longitude = longitude
        # Use forecast API for current and future weather
        self.base_url = "https://api.open-meteo.com/v1/forecast"
        logger.info(f"Weather API Client initialized for coordinates: {latitude}, {longitude}")
    
    def fetch_weather_data(self, hours_ahead=0):
        """
        Fetch current hour weather data only
        
        Args:
            hours_ahead: Number of hours to fetch ahead (default: 0 = current hour only)
            
        Returns:
            list: Weather data records with timestamp and metrics
        """
        try:
            # Get current time rounded to hour
            now = datetime.now()
            current_hour = now.replace(minute=0, second=0, microsecond=0)
            
            # Calculate end time
            if hours_ahead > 0:
                end_hour = current_hour + timedelta(hours=hours_ahead)
            else:
                end_hour = current_hour  # Only current hour
            
            # Format dates and times for API
            start_date = current_hour.strftime('%Y-%m-%d')
            end_date = end_hour.strftime('%Y-%m-%d')
            
            # API parameters
            params = {
                'latitude': self.latitude,
                'longitude': self.longitude,
                'hourly': [
                    'temperature_2m',
                    'relative_humidity_2m', 
                    'precipitation',
                    'wind_speed_10m',
                    'weather_code'
                ],
                'start_date': start_date,
                'end_date': end_date,
                'timezone': 'auto'
            }
            
            logger.info(f"Fetching weather data for: {current_hour.strftime('%Y-%m-%d %H:00')}")
            
            # Make API request
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Parse response
            weather_records = []
            hourly_data = data.get('hourly', {})
            timestamps = hourly_data.get('time', [])
            temperatures = hourly_data.get('temperature_2m', [])
            humidities = hourly_data.get('relative_humidity_2m', [])
            precipitations = hourly_data.get('precipitation', [])
            wind_speeds = hourly_data.get('wind_speed_10m', [])
            weather_codes = hourly_data.get('weather_code', [])
            
            # Create records
            for i in range(len(timestamps)):
                timestamp_str = timestamps[i]
                
                # Only include current hour (filter out other hours)
                timestamp_dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                if hours_ahead == 0:
                    # Only keep the current hour
                    if timestamp_dt.replace(tzinfo=None) != current_hour:
                        continue
                
                record = {
                    'timestamp': timestamp_str,
                    'temperature_2m': temperatures[i] if i < len(temperatures) else None,
                    'relative_humidity_2m': humidities[i] if i < len(humidities) else None,
                    'precipitation': precipitations[i] if i < len(precipitations) else None,
                    'wind_speed_10m': wind_speeds[i] if i < len(wind_speeds) else None,
                    'weather_code': weather_codes[i] if i < len(weather_codes) else None,
                    'latitude': self.latitude,
                    'longitude': self.longitude
                }
                weather_records.append(record)
            
            logger.info(f"Successfully fetched {len(weather_records)} weather records")
            return weather_records
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching weather data: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in fetch_weather_data: {e}")
            return []


class DatabaseManager:
    """Handles PostgreSQL database operations for weather data"""
    
    def __init__(self):
        """Initialize database connection parameters from environment"""
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
        logger.info(f"Database config: {self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")
    
    def get_connection(self):
        """Create and return database connection"""
        try:
            conn = psycopg2.connect(**self.db_config)
            return conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
    
    def insert_weather_data(self, weather_records):
        """
        Insert weather records into database
        Uses INSERT ... ON CONFLICT to handle duplicates
        
        Args:
            weather_records: List of weather data dictionaries
            
        Returns:
            int: Number of records inserted/updated
        """
        if not weather_records:
            logger.warning("No weather records to insert")
            return 0
        
        conn = None
        cursor = None
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # SQL for inserting weather data with upsert
            insert_query = """
                INSERT INTO weather_hourly (
                    hour_timestamp,
                    temperature_2m,
                    relative_humidity_2m,
                    precipitation,
                    wind_speed_10m,
                    weather_code,
                    latitude,
                    longitude
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (hour_timestamp) 
                DO UPDATE SET
                    temperature_2m = EXCLUDED.temperature_2m,
                    relative_humidity_2m = EXCLUDED.relative_humidity_2m,
                    precipitation = EXCLUDED.precipitation,
                    wind_speed_10m = EXCLUDED.wind_speed_10m,
                    weather_code = EXCLUDED.weather_code,
                    created_at = NOW()
            """
            
            # Prepare data for batch insert
            insert_data = []
            for record in weather_records:
                insert_data.append((
                    record['timestamp'],
                    record.get('temperature_2m'),
                    record.get('relative_humidity_2m'),
                    record.get('precipitation'),
                    record.get('wind_speed_10m'),
                    record.get('weather_code'),
                    record.get('latitude'),
                    record.get('longitude')
                ))
            
            # Execute batch insert
            cursor.executemany(insert_query, insert_data)
            conn.commit()
            
            inserted_count = cursor.rowcount
            logger.info(f"Successfully inserted/updated {inserted_count} weather records")
            
            return inserted_count
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error inserting weather data: {e}")
            return 0
            
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def get_latest_weather(self):
        """
        Get the latest weather record from database
        
        Returns:
            dict: Latest weather record or None
        """
        conn = None
        cursor = None
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            query = """
                SELECT hour_timestamp, temperature_2m, relative_humidity_2m, 
                       precipitation, wind_speed_10m, weather_code
                FROM weather_hourly
                ORDER BY hour_timestamp DESC
                LIMIT 1
            """
            
            cursor.execute(query)
            row = cursor.fetchone()
            
            if row:
                return {
                    'timestamp': row[0],
                    'temperature_2m': row[1],
                    'relative_humidity_2m': row[2],
                    'precipitation': row[3],
                    'wind_speed_10m': row[4],
                    'weather_code': row[5]
                }
            return None
            
        except Exception as e:
            logger.error(f"Error fetching latest weather: {e}")
            return None
            
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()


class WeatherCollectorService:
    """Main service to orchestrate weather data collection"""
    
    def __init__(self):
        """Initialize the weather collector service"""
        self.api_client = WeatherAPIClient()
        self.db_manager = DatabaseManager()
        logger.info("Weather Collector Service initialized")
    
    def collect_and_store_weather(self):
        """
        Main collection workflow:
        1. Fetch weather data from API
        2. Store in database
        3. Log results
        """
        logger.info("=" * 60)
        logger.info("Starting weather data collection cycle")
        logger.info("=" * 60)
        
        try:
            # Fetch weather data (current hour only)
            weather_records = self.api_client.fetch_weather_data(hours_ahead=0)
            
            if not weather_records:
                logger.warning("No weather data retrieved from API")
                return
            
            # Store in database
            inserted_count = self.db_manager.insert_weather_data(weather_records)
            
            # Get latest weather for logging
            latest = self.db_manager.get_latest_weather()
            if latest:
                logger.info(f"Latest weather: {latest['timestamp']} - "
                          f"Temp: {latest['temperature_2m']}°C, "
                          f"Humidity: {latest['relative_humidity_2m']}%, "
                          f"Precipitation: {latest['precipitation']}mm")
            
            logger.info(f"Collection cycle completed: {inserted_count} records processed")
            
        except Exception as e:
            logger.error(f"Error in collection cycle: {e}")
        
        logger.info("=" * 60)
    
    def run_once(self):
        """Run collection once (useful for testing)"""
        logger.info("Running weather collection once...")
        self.collect_and_store_weather()
    
    def run_scheduled(self):
        """
        Run collection on schedule (every hour)
        """
        logger.info("Starting scheduled weather collection service")
        logger.info("Schedule: Every hour at minute 0")
        
        # Schedule to run every hour
        schedule.every().hour.at(":00").do(self.collect_and_store_weather)
        
        # Also run immediately on startup
        self.collect_and_store_weather()
        
        # Keep running
        logger.info("Weather collector is now running. Press Ctrl+C to stop.")
        
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except KeyboardInterrupt:
                logger.info("Weather collector stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in scheduler: {e}")
                time.sleep(60)


def main():
    """Main entry point"""
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║       Weather Data Collector Service                      ║
    ║       Collecting hourly weather data                      ║
    ║       Location: Bamberg, Germany (49.891, 10.887)        ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    try:
        service = WeatherCollectorService()
        
        # Check if running in test mode
        if len(sys.argv) > 1 and sys.argv[1] == '--once':
            service.run_once()
        else:
            service.run_scheduled()
            
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
