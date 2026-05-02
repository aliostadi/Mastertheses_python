import os
import schedule
import time
import subprocess
from datetime import datetime

def run_transformations():
    """Run hourly aggregator and feature engineer"""
    print(f"[{datetime.now()}] Starting hourly transformations...")
    
    try:
        # Run hourly aggregator
        print("Running hourly aggregator...")
        result = subprocess.run(['python', 'hourly_aggregator.py'], 
                              capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.returncode == 0:
            print("✓ Hourly aggregator completed successfully")
        else:
            print(f"✗ Hourly aggregator failed: {result.stderr}")
        
        # Run feature engineer
        print("Running feature engineer...")
        result = subprocess.run(['python', 'feature_engineer.py'], 
                              capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.returncode == 0:
            print("✓ Feature engineer completed successfully")
        else:
            print(f"✗ Feature engineer failed: {result.stderr}")
            
    except Exception as e:
        print(f"Error during transformation: {e}")
    
    print(f"[{datetime.now()}] Transformations completed\n")

if __name__ == "__main__":
    print("Starting Data Transformer Scheduler")
    print(f"Current time: {datetime.now()}")
    print("Schedule: Every hour at :05 past the hour\n")
    
    # Schedule to run at 5 minutes past every hour
    schedule.every().hour.at(":05").do(run_transformations)
    
    # Run once immediately on startup (after 1 minute to let data accumulate)
    time.sleep(60)
    run_transformations()
    
    # Keep running scheduled tasks
    while True:
        schedule.run_pending()
        time.sleep(30)  # Check every 30 seconds
