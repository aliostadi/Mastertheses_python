import os
from ..utils.sql_executor import SQLExecutor


def main():
    """Execute hourly parking availability aggregation SQL"""
    # Initialize SQL executor
    executor = SQLExecutor()
    
    # Get SQL file path
    sql_folder = os.path.join(os.path.dirname(__file__), 'sql')
    sql_file = 'parking_availability_hourly_lot634.sql'
    
    print(f"Executing SQL file: {sql_file}")
    print("Creating hourly aggregation from minute-level data...")
    
    try:
        # Execute the SQL file
        executor.execute_sql_from_folder(sql_folder, sql_file)
        print("✅ Hourly parking availability table created successfully!")
        
        # Show sample hourly data
        sample_sql = """
            SELECT hour_timestamp, avg_free_spaces, min_free_spaces, max_free_spaces,
                   free_spaces_range, hour_of_day, day_of_week, weekday_name
            FROM ali_parking_availability_hourly_lot634 
            ORDER BY hour_timestamp 
            LIMIT 10;
        """
        results = executor.execute_sql(sample_sql, commit=False, fetch_results=True)
        
        if results and results['data']:
            print("\n📈 Sample hourly data:")
            print("Hour                  | Avg Free | Min | Max | Range | Hour | DOW | Weekday")
            print("-" * 80)
            for row in results['data']:
                print(f"{row[0]} | {row[1]:8.1f} | {row[2]:3d} | {row[3]:3d} | {row[4]:5.1f} | {row[5]:4d} | {row[6]:3d} | {row[7].strip()}")
        
        # Show hourly pattern summary
        summary_sql = """
            SELECT hour_of_day, 
                   ROUND(AVG(avg_free_spaces), 2) AS daily_avg_free_spaces,
                   ROUND(MIN(avg_free_spaces), 2) AS daily_min_free_spaces,
                   ROUND(MAX(avg_free_spaces), 2) AS daily_max_free_spaces,
                   COUNT(*) AS total_hours
            FROM ali_parking_availability_hourly_lot634
            GROUP BY hour_of_day 
            ORDER BY hour_of_day;
        """
        summary_results = executor.execute_sql(summary_sql, commit=False, fetch_results=True)
        
        if summary_results and summary_results['data']:
            print("\n📊 Daily hourly patterns:")
            print("Hour | Daily Avg Free | Min | Max | Hours Sampled")
            print("-" * 55)
            for row in summary_results['data']:
                print(f"{row[0]:4d} | {row[1]:13.1f} | {row[2]:3.1f} | {row[3]:3.1f} | {row[4]:11d}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()