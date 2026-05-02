"""
Prediction Scheduler - Runs predictions every hour at :10 past the hour
"""

import schedule
import time
import logging
from datetime import datetime
from parking_predictor_hybrid import run_all_hybrid_predictions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def scheduled_prediction():
    """Run prediction and log the results"""
    try:
        logger.info("Starting scheduled HYBRID prediction run...")
        start_time = datetime.now()
        
        # Run hybrid predictions for all lots
        results = run_all_hybrid_predictions(save_to_db=True)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"Prediction completed successfully in {duration:.1f}s")
        logger.info(f"Processed {len(results)} parking lots")
        
        for lot_id, result in results.items():
            avg_pred = sum(result['predictions']) / len(result['predictions'])
            logger.info(f"Lot {lot_id}: avg prediction = {avg_pred:.1f} spots")
            
    except Exception as e:
        logger.error(f"Prediction failed: {str(e)}", exc_info=True)

def main():
    """Main scheduler loop"""
    logger.info("Starting Hybrid Parking Prediction Scheduler")
    logger.info("Enhanced predictions with dual-model blending will run every hour at :10")
    
    # Schedule predictions at 10 minutes past every hour
    schedule.every().hour.at(":10").do(scheduled_prediction)
    
    # Run initial prediction on startup (optional)
    logger.info("Running initial prediction...")
    scheduled_prediction()
    
    # Keep the scheduler running  
    while True:
        schedule.run_pending()
        time.sleep(30)  # Check every 30 seconds

if __name__ == "__main__":
    main()