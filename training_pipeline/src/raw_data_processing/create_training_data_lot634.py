import os
from ..utils.sql_executor import SQLExecutor


def main():
    """Create training data by joining parking availability with weather data"""
    # Initialize SQL executor
    executor = SQLExecutor()
    
    # Get SQL file path
    sql_folder = os.path.join(os.path.dirname(__file__), 'sql')
    sql_file = 'create_training_data_lot634.sql'
    
    print(f"Executing SQL file: {sql_file}")
    print("Creating training data by joining parking and weather data...")
    
    try:
        # Execute the SQL file
        executor.execute_sql_from_folder(sql_folder, sql_file)
        print("✅ Training data table created successfully!")
        
        # Show sample training data
        sample_sql = """
            SELECT hour_timestamp, avg_free_spaces, temperature_2m, 
                   relative_humidity_2m, precipitation, day_type, time_period,
                   temperature_category, precipitation_category
            FROM ali_training_data_hourly_availability_hourly_lot634 
            ORDER BY hour_timestamp 
            LIMIT 10;
        """
        results = executor.execute_sql(sample_sql, commit=False, fetch_results=True)
        
        if results and results['data']:
            print("\n📈 Sample training data:")
            print("Hour                  | Free | Temp | Humid | Rain | Type    | Period      | Temp Cat | Rain Cat")
            print("-" * 100)
            for row in results['data']:
                print(f"{row[0]} | {row[1]:4.1f} | {row[2]:4.1f} | {row[3]:5.1f} | {row[4]:4.1f} | {row[5]:7s} | {row[6]:11s} | {row[7]:8s} | {row[8]:8s}")
        
        
        
        
        
        # Show total record count
        count_sql = "SELECT COUNT(*) FROM ali_training_data_hourly_availability_hourly_lot634;"
        count_results = executor.execute_sql(count_sql, commit=False, fetch_results=True)
        
        if count_results and count_results['data']:
            total_records = count_results['data'][0][0]
            print(f"\n📊 Total training records: {total_records:,}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()