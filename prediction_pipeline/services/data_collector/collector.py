"""
Parking Data Collector Service

This service:
1. Authenticates with the Parking API to get a token
2. Fetches current occupancy data for all parking lots
3. Extracts relevant data and creates a DataFrame
4. Saves data to PostgreSQL database
5. Runs every minute using schedule library
"""

import os
import time
import requests
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
import logging

# Try to load .env if running locally (optional for container)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # In container, env vars are passed directly

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ParkingAPIClient:
    """Client for interacting with the Parking Pilot API"""
    
    def __init__(self):
        self.base_url = "https://api.parking-pilot.com"
        self.username = os.getenv('PARKING_API_USERNAME')
        self.password = os.getenv('PARKING_API_PASSWORD')
        
        # Validate required credentials
        if not self.username or not self.password:
            raise ValueError("PARKING_API_USERNAME and PARKING_API_PASSWORD must be set in environment variables")
        
        self.token = None
        self.token_timestamp = None
        self.token_validity_hours = 24  # Token expires after 24 hours
        
    def is_token_valid(self):
        """
        Check if the current token is still valid (within 24 hours)
        """
        if not self.token or not self.token_timestamp:
            return False
        
        # Calculate time elapsed since token was obtained
        time_elapsed = datetime.now() - self.token_timestamp
        hours_elapsed = time_elapsed.total_seconds() / 3600
        
        is_valid = hours_elapsed < self.token_validity_hours
        
        if not is_valid:
            logger.info(f"🔄 Token expired ({hours_elapsed:.1f} hours old). Refreshing...")
        
        return is_valid
    
    def get_token(self):
        """
        Authenticate and get API token
        POST to /auth?remember=false
        Token is valid for 24 hours
        """
        try:
            url = f"{self.base_url}/auth?remember=false"
            
            # Send as JSON body
            response = requests.post(
                url,
                json={
                    'username': self.username,
                    'password': self.password
                },
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.token = data.get('token')
                self.token_timestamp = datetime.now()
                logger.info(f"✅ Successfully obtained API token (valid for {self.token_validity_hours} hours)")
                return self.token
            else:
                logger.error(f"❌ Failed to get token. Status: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error getting token: {e}")
            return None
    
    def get_current_occupancy(self):
        """
        Fetch current occupancy data for all parking lots
        GET to /parkinglots/current-occupancy-state
        Automatically refreshes token if expired
        """
        # Check if token is valid, refresh if needed
        if not self.is_token_valid():
            logger.info("🔑 Token invalid or expired, requesting new token...")
            self.get_token()
        
        if not self.token:
            logger.error("❌ Cannot fetch data without token")
            return None
        
        try:
            url = f"{self.base_url}/parkinglots/current-occupancy-state"
            
            # Send GET request with token in headers
            response = requests.get(
                url,
                headers={
                    'accept': 'application/json',
                    'X-Api-Key': self.token,
                    'X-Auth-Token': self.token,
                    'X-Two-Factor-Token': self.token
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Successfully fetched occupancy data for {len(data)} parking lots")
                return data
            else:
                logger.error(f"❌ Failed to fetch occupancy. Status: {response.status_code}")
                # If 401 (unauthorized), token might be invalid - refresh it
                if response.status_code == 401:
                    logger.info("🔄 Got 401 error, token might be invalid. Refreshing...")
                    self.token = None  # Force token refresh
                    self.token_timestamp = None
                    self.get_token()
                return None
                
        except Exception as e:
            logger.error(f"❌ Error fetching occupancy data: {e}")
            return None


class DatabaseManager:
    """Manager for PostgreSQL database operations"""
    
    def __init__(self):
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
    
    def get_connection(self):
        """Get database connection"""
        try:
            conn = psycopg2.connect(**self.db_config)
            return conn
        except Exception as e:
            logger.error(f"❌ Database connection error: {e}")
            return None
    
    def save_occupancy_data(self, df):
        """
        Save occupancy data to database
        Table: parking_availability_minute
        """
        if df is None or df.empty:
            logger.warning("No data to save")
            return False
        
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            
            # Prepare data for insertion - match the database schema
            insert_query = """
                INSERT INTO parking_availability_minute 
                (minute_timestamp, parking_lot_id, free_spaces, occupied_spaces, total_spaces, 
                 occupancy_rate, parking_lot_name, address, city, country, latitude, longitude,
                 family_occupied, family_total, disabled_occupied, disabled_total, 
                 electrocharger_occupied, electrocharger_total, invalid)
                VALUES %s
                ON CONFLICT (parking_lot_id, minute_timestamp) 
                DO UPDATE SET
                    free_spaces = EXCLUDED.free_spaces,
                    occupied_spaces = EXCLUDED.occupied_spaces,
                    total_spaces = EXCLUDED.total_spaces,
                    occupancy_rate = EXCLUDED.occupancy_rate,
                    parking_lot_name = EXCLUDED.parking_lot_name,
                    address = EXCLUDED.address,
                    city = EXCLUDED.city,
                    country = EXCLUDED.country,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    family_occupied = EXCLUDED.family_occupied,
                    family_total = EXCLUDED.family_total,
                    disabled_occupied = EXCLUDED.disabled_occupied,
                    disabled_total = EXCLUDED.disabled_total,
                    electrocharger_occupied = EXCLUDED.electrocharger_occupied,
                    electrocharger_total = EXCLUDED.electrocharger_total,
                    invalid = EXCLUDED.invalid
            """
            
            # Prepare values tuple
            values = [
                (
                    row['timestamp'],
                    row['parking_lot_id'],
                    row['free_spaces'],
                    row['general_occupied'],
                    row['general_total'],
                    row['occupancy_rate'],
                    row['name'],
                    row['address'],
                    row['city'],
                    row['country'],
                    row['latitude'],
                    row['longitude'],
                    row['family_occupied'],
                    row['family_total'],
                    row['disabled_occupied'],
                    row['disabled_total'],
                    row['electrocharger_occupied'],
                    row['electrocharger_total'],
                    row['invalid']
                )
                for _, row in df.iterrows()
            ]
            
            # Execute batch insert
            execute_values(cursor, insert_query, values)
            conn.commit()
            
            logger.info(f"✅ Saved {len(df)} records to database")
            
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving to database: {e}")
            if conn:
                conn.rollback()
                conn.close()
            return False


def process_occupancy_data(api_data):
    """
    Process API response and create DataFrame
    
    Args:
        api_data: List of parking lot occupancy data from API
    
    Returns:
        pandas DataFrame with processed data
    """
    if not api_data:
        return None
    
    try:
        # Current timestamp
        current_time = datetime.now()
        
        # Extract relevant fields
        processed_data = []
        
        for lot in api_data:
            record = {
                'timestamp': current_time,
                'parking_lot_id': lot.get('parking_lot_id'),
                'name': lot.get('name'),
                'address': lot.get('address'),
                'city': lot.get('city'),
                'country': lot.get('country'),
                'latitude': lot.get('latitude'),
                'longitude': lot.get('longitude'),
                'general_occupied': lot.get('general_occupied'),
                'general_total': lot.get('general_total'),
                'family_occupied': lot.get('family_occupied', 0),
                'family_total': lot.get('family_total', 0),
                'disabled_occupied': lot.get('disabled_occupied', 0),
                'disabled_total': lot.get('disabled_total', 0),
                'electrocharger_occupied': lot.get('electrocharger_occupied', 0),
                'electrocharger_total': lot.get('electrocharger_total', 0),
                'invalid': lot.get('invalid', False)
            }
            
            # Calculate free spaces and occupancy rate
            total = record['general_total']
            occupied = record['general_occupied']
            record['free_spaces'] = total - occupied if total and occupied is not None else None
            record['occupancy_rate'] = (occupied / total * 100) if total and total > 0 else None
            
            processed_data.append(record)
        
        # Create DataFrame
        df = pd.DataFrame(processed_data)
        
        logger.info(f"✅ Processed {len(df)} parking lots")
        logger.info(f"   Sample: Lot {df.iloc[0]['parking_lot_id']} - {df.iloc[0]['name']} - Free: {df.iloc[0]['free_spaces']}/{df.iloc[0]['general_total']}")
        
        return df
        
    except Exception as e:
        logger.error(f"❌ Error processing data: {e}")
        return None


def collect_and_save_data():
    """
    Main function to collect data from API and save to database
    This function will be called every minute
    Token is automatically validated and refreshed if expired (24h validity)
    """
    logger.info("="*60)
    logger.info("🔄 Starting data collection...")
    
    # Initialize API client
    api_client = ParkingAPIClient()
    
    # Fetch current occupancy data (token validation happens automatically)
    api_data = api_client.get_current_occupancy()
    
    if not api_data:
        logger.error("❌ No data fetched from API")
        return
    
    # Process data into DataFrame
    df = process_occupancy_data(api_data)
    
    if df is None or df.empty:
        logger.error("❌ Failed to process data")
        return
    
    # Save to database
    db_manager = DatabaseManager()
    success = db_manager.save_occupancy_data(df)
    
    if success:
        logger.info("✅ Data collection cycle completed successfully")
    else:
        logger.error("❌ Data collection cycle failed")
    
    logger.info("="*60)


if __name__ == "__main__":
    import schedule
    
    logger.info("🚀 Parking Data Collector Service Started")
    logger.info("📊 Collecting data every 1 minute...")
    
    # Run immediately on start
    collect_and_save_data()
    
    # Schedule to run every minute
    schedule.every(1).minutes.do(collect_and_save_data)
    
    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(1)
