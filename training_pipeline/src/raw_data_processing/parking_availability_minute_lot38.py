import os
from ..utils.sql_executor import SQLExecutor


def main():
    """Execute parking availability SQL using the general SQLExecutor class"""
    # Initialize SQL executor
    executor = SQLExecutor()
    
    # Get SQL file path
    sql_folder = os.path.join(os.path.dirname(__file__), 'sql')
    sql_file = 'parking_availability_minute_lot38.sql'
    
    print(f"Executing SQL file: {sql_file}")
    
    try:
        # Execute the SQL file
        executor.execute_sql_from_folder(sql_folder, sql_file)
        print("✅ Parking availability table created successfully!")
        
        # Show sample data
        sample_sql = """
            SELECT minute_timestamp, free_spaces, occupied_spaces
            FROM ali_parking_availability_minute_lot38 
            ORDER BY minute_timestamp 
            LIMIT 5;
        """
        results = executor.execute_sql(sample_sql, commit=False, fetch_results=True)
        
        if results and results['data']:
            print("\n📈 Sample data:")
            print("Timestamp                | Free | Occupied ")
            print("-" * 55)
            for row in results['data']:
                print(f"{row[0]} | {row[1]:4d} | {row[2]:8d} | {row[3]:9.1f}%")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()