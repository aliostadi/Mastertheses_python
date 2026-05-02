"""
Parking Availability Predictor
Fetches latest data from AWS, applies proper preprocessing (encoding + scaling),
makes 24-hour predictions for EACH LOT SEPARATELY, and saves to database.

Each lot uses its OWN:
- config.json
- encoder.pkl  
- scalers.pkl
- linear_regression_model.pkl

Preprocessing Pipeline (matches training exactly):
1. OrdinalEncoder for categorical features (lot-specific encoder.pkl)
2. Reshape to (1, 48, 20)
3. MinMaxScaler per timestep (lot-specific scalers.pkl)
4. Flatten to (1, 960)
5. Predict 24 hours (lot-specific model.pkl)
"""

import os
import sys
import pickle
import json
import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Try to load .env if running locally
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def get_model_dir(parking_lot_id):
    """
    Get the model directory for a specific parking lot.
    Checks multiple locations in priority order.
    """
    current_file = os.path.abspath(__file__)
    current_dir = os.path.dirname(current_file)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
    
    lot_folder = f'lot{parking_lot_id}'
    
    # Priority 1: MODEL_DIR environment variable
    env_model_dir = os.getenv('MODEL_DIR')
    if env_model_dir:
        path = os.path.join(env_model_dir, lot_folder)
        if os.path.exists(path):
            return path
    
    # Priority 2: Local models/ directory (for Docker)
    local_path = os.path.join(current_dir, 'models', lot_folder)
    if os.path.exists(local_path):
        return local_path
    
    # Priority 3: training_pipeline/results/ (for local development)
    training_path = os.path.join(project_root, 'training_pipeline', 'results', lot_folder)
    return training_path


def get_db_config():
    """Get database configuration from environment variables."""
    # Validate required database credentials
    db_password = os.getenv('DB_PASSWORD')
    if not db_password:
        raise ValueError("DB_PASSWORD must be set in environment variables")
    
    return {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', '5432')),
        'database': os.getenv('DB_NAME', 'parking_predictions'),
        'user': os.getenv('DB_USER', 'parking_user'),
        'password': db_password
    }


def load_lot_resources(parking_lot_id, model_name='linear_regression'):
    """
    Load ALL resources for a specific parking lot.
    Each lot has its own config, encoder, scalers, and model.
    
    Returns:
        dict with config, encoder, scalers, model, model_dir
    """
    model_dir = get_model_dir(parking_lot_id)
    
    print(f"\n{'='*60}")
    print(f"Loading resources for Lot {parking_lot_id}")
    print(f"{'='*60}")
    print(f"Model directory: {model_dir}")
    
    # Check files exist
    config_path = os.path.join(model_dir, 'config.json')
    encoder_path = os.path.join(model_dir, 'encoder.pkl')
    scalers_path = os.path.join(model_dir, 'scalers.pkl')
    model_path = os.path.join(model_dir, f'{model_name}_model.pkl')
    
    files_exist = {
        'config.json': os.path.exists(config_path),
        'encoder.pkl': os.path.exists(encoder_path),
        'scalers.pkl': os.path.exists(scalers_path),
        f'{model_name}_model.pkl': os.path.exists(model_path)
    }
    
    print(f"\nFiles check:")
    for fname, exists in files_exist.items():
        status = "✓" if exists else "✗ MISSING"
        print(f"  {fname}: {status}")
    
    if not all(files_exist.values()):
        missing = [f for f, e in files_exist.items() if not e]
        raise FileNotFoundError(f"Lot {parking_lot_id} missing files: {missing}")
    
    # Load config
    with open(config_path, 'r') as f:
        config = json.load(f)
    print(f"\nConfig loaded: {config['n_features']} features, {config['past_history']}h history")
    
    # Load encoder (lot-specific!)
    with open(encoder_path, 'rb') as f:
        encoder = pickle.load(f)
    print(f"Encoder loaded: OrdinalEncoder for {config['ordinal_features']}")
    
    # Load scalers (lot-specific!)
    with open(scalers_path, 'rb') as f:
        scalers = pickle.load(f)
    print(f"Scalers loaded: {len(scalers)} MinMaxScalers (one per timestep)")
    
    # Load model (lot-specific!)
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    print(f"Model loaded: {model_name}")
    
    return {
        'config': config,
        'encoder': encoder,
        'scalers': scalers,
        'model': model,
        'model_dir': model_dir,
        'model_name': model_name
    }


def fetch_training_data(parking_lot_id, hours_back=72):
    """
    Fetch recent training data from database for a specific lot.
    """
    db_config = get_db_config()
    conn = None
    
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        query = """
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
            FROM training_data_hourly
            WHERE parking_lot_id = %s
            ORDER BY hour_timestamp DESC
            LIMIT %s
        """
        
        cursor.execute(query, (parking_lot_id, hours_back))
        rows = cursor.fetchall()
        
        if not rows:
            print(f"No data found for lot {parking_lot_id}")
            return None
        
        columns = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(rows, columns=columns)
        df = df.sort_values('hour_timestamp').reset_index(drop=True)
        df['hour_timestamp'] = pd.to_datetime(df['hour_timestamp'])
        
        print(f"\nFetched {len(df)} hours of data")
        print(f"  Range: {df['hour_timestamp'].min()} to {df['hour_timestamp'].max()}")
        
        return df
        
    except Exception as e:
        print(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()


def engineer_features(df):
    """Add engineered features to match training."""
    df_eng = df.copy()
    
    # Clean categorical features
    for col in ['temperature_category', 'precipitation_category', 'day_type', 'time_period']:
        if col in df_eng.columns:
            df_eng[col] = df_eng[col].astype(str).str.strip()
    
    # Add month feature
    df_eng['month'] = df_eng['hour_timestamp'].dt.month
    
    # Recalculate rolling features if missing
    if df_eng['avg_free_spaces_rolling_24h'].isna().all():
        df_eng['avg_free_spaces_rolling_24h'] = df_eng['avg_free_spaces'].rolling(24, min_periods=1).mean()
    
    if df_eng['avg_free_spaces_std_24h'].isna().all():
        df_eng['avg_free_spaces_std_24h'] = df_eng['avg_free_spaces'].rolling(24, min_periods=1).std()
    
    df_eng['avg_free_spaces_std_24h'] = df_eng['avg_free_spaces_std_24h'].fillna(0)
    
    if df_eng['avg_free_spaces_diff_1h'].isna().all():
        df_eng['avg_free_spaces_diff_1h'] = df_eng['avg_free_spaces'].diff(1).fillna(0)
    
    if df_eng['temperature_diff_1h'].isna().all():
        df_eng['temperature_diff_1h'] = df_eng['temperature_2m'].diff(1).fillna(0)
    
    df_eng = df_eng.fillna(method='ffill').fillna(method='bfill').fillna(0)
    
    return df_eng


def preprocess_and_predict(df, resources, parking_lot_id):
    """
    Apply preprocessing and make predictions using LOT-SPECIFIC resources.
    
    IMPORTANT: Each lot uses its own encoder and scalers!
    """
    config = resources['config']
    encoder = resources['encoder']  # Lot-specific!
    scalers = resources['scalers']  # Lot-specific!
    model = resources['model']      # Lot-specific!
    
    past_history = config['past_history']
    feature_names = config['feature_names']
    ordinal_features = config['ordinal_features']
    ordinal_mappings = config['ordinal_mappings']
    
    print(f"\n{'='*60}")
    print(f"Preprocessing Lot {parking_lot_id}")
    print(f"{'='*60}")
    
    # Ensure enough data
    if len(df) < past_history:
        print(f"Warning: Only {len(df)} hours, padding to {past_history}")
        padding = pd.concat([df.iloc[[0]]] * (past_history - len(df)), ignore_index=True)
        df = pd.concat([padding, df], ignore_index=True)
    
    # Take last past_history hours
    input_window = df.iloc[-past_history:].copy()
    last_timestamp = input_window['hour_timestamp'].max()
    
    print(f"Input window: {input_window['hour_timestamp'].min()} to {last_timestamp}")
    
    # Step 1: Map categorical values to training format
    print(f"\n1. Mapping categorical values...")
    
    # Map day_type
    input_window['day_type'] = input_window['day_type'].replace({
        'weekday': 'Weekday', 'Weekday': 'Weekday',
        'weekend': 'Weekend', 'Weekend': 'Weekend'
    })
    
    # Map precipitation_category  
    input_window['precipitation_category'] = input_window['precipitation_category'].replace({
        'none': 'no_rain', 'no_rain': 'no_rain',
        'light': 'light_rain', 'light_rain': 'light_rain',
        'moderate': 'moderate_rain', 'moderate_rain': 'moderate_rain',
        'heavy': 'heavy_rain', 'heavy_rain': 'heavy_rain'
    })
    
    # Validate categories
    for feat in ordinal_features:
        expected = ordinal_mappings[feat]
        actual = input_window[feat].unique()
        invalid = [v for v in actual if v not in expected]
        if invalid:
            print(f"   Warning: {feat} has invalid values {invalid}, replacing with '{expected[0]}'")
            input_window[feat] = input_window[feat].apply(lambda x: x if x in expected else expected[0])
    
    # Step 2: Encode categorical features with LOT-SPECIFIC encoder
    print(f"2. Encoding with lot{parking_lot_id} encoder...")
    categorical_data = input_window[ordinal_features].values
    encoded_data = encoder.transform(categorical_data)
    
    for i, feat in enumerate(ordinal_features):
        input_window[feat] = encoded_data[:, i]
    
    # Step 3: Extract features in correct order
    print(f"3. Extracting {len(feature_names)} features...")
    X_input = input_window[feature_names].values.astype(np.float64)
    
    # Step 4: Reshape to 3D
    X_reshaped = X_input.reshape(1, past_history, config['n_features'])
    print(f"4. Reshaped to: {X_reshaped.shape}")
    
    # Step 5: Apply LOT-SPECIFIC scalers
    print(f"5. Scaling with lot{parking_lot_id} scalers...")
    X_scaled = X_reshaped.copy()
    for i in range(X_scaled.shape[1]):
        if i in scalers:
            X_scaled[:, i, :] = scalers[i].transform(X_scaled[:, i, :])
    
    # Step 6: Flatten
    X_flat = X_scaled.reshape(1, -1)
    print(f"6. Flattened to: {X_flat.shape}")
    
    # Step 7: Predict with LOT-SPECIFIC model
    print(f"7. Predicting with lot{parking_lot_id} model...")
    predictions_raw = model.predict(X_flat)
    
    if len(predictions_raw.shape) > 1:
        predictions = predictions_raw[0]
    else:
        predictions = predictions_raw
    
    predictions = [max(0, round(float(p))) for p in predictions[:24]]
    
    # Generate timestamps
    prediction_timestamps = [last_timestamp + timedelta(hours=i+1) for i in range(24)]
    
    print(f"\n✓ Generated {len(predictions)} hour predictions for Lot {parking_lot_id}")
    
    return {
        'timestamps': prediction_timestamps,
        'predictions': predictions,
        'parking_lot_id': parking_lot_id,
        'model_name': resources['model_name'],
        'last_known_timestamp': last_timestamp,
        'last_known_value': float(df['avg_free_spaces'].iloc[-1])
    }


def save_predictions_to_db(prediction_result):
    """Save predictions to database - both summary table and hourly table for ML monitoring."""
    db_config = get_db_config()
    conn = None
    
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        predictions = prediction_result['predictions']
        timestamps = prediction_result['timestamps']
        parking_lot_id = prediction_result['parking_lot_id']
        model_name = prediction_result['model_name']
        prediction_timestamp = datetime.now()
        
        # --- Save to predictions_24h (summary table) ---
        hour_values = predictions + [None] * (24 - len(predictions))
        
        insert_query = """
            INSERT INTO predictions_24h (
                prediction_timestamp, parking_lot_id, model_name,
                predicted_free_spaces,
                hour_1, hour_2, hour_3, hour_4, hour_5, hour_6,
                hour_7, hour_8, hour_9, hour_10, hour_11, hour_12,
                hour_13, hour_14, hour_15, hour_16, hour_17, hour_18,
                hour_19, hour_20, hour_21, hour_22, hour_23, hour_24,
                confidence_score
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s
            )
        """
        
        cursor.execute(insert_query, (
            prediction_timestamp, parking_lot_id, model_name,
            predictions,
            *hour_values[:24],
            0.85
        ))
        
        # --- Save to predictions_hourly (for ML monitoring) ---
        hourly_insert = """
            INSERT INTO predictions_hourly (
                prediction_made_at, target_hour, parking_lot_id, model_name,
                hours_ahead, predicted_free_spaces
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (parking_lot_id, target_hour, model_name, prediction_made_at) 
            DO UPDATE SET predicted_free_spaces = EXCLUDED.predicted_free_spaces
        """
        
        for i, (target_hour, pred_value) in enumerate(zip(timestamps, predictions)):
            cursor.execute(hourly_insert, (
                prediction_timestamp,
                target_hour,
                parking_lot_id,
                model_name,
                i + 1,  # hours_ahead (1-24)
                int(pred_value)
            ))
        
        conn.commit()
        print(f"✓ Saved to database: Lot {parking_lot_id} (24h summary + {len(predictions)} hourly records)")
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Database save error: {e}")
        raise
    finally:
        if conn:
            conn.close()


def predict_for_lot(parking_lot_id, model_name='linear_regression', save_to_db=True):
    """
    Run complete prediction pipeline for a SINGLE lot.
    Uses lot-specific resources (encoder, scalers, model).
    """
    print(f"\n{'#'*70}")
    print(f"# PREDICTING FOR LOT {parking_lot_id}")
    print(f"{'#'*70}")
    
    # Load lot-specific resources
    resources = load_lot_resources(parking_lot_id, model_name)
    
    # Fetch data for this lot
    print(f"\nFetching data for lot {parking_lot_id}...")
    df = fetch_training_data(parking_lot_id, hours_back=72)
    if df is None:
        print(f"✗ No data for lot {parking_lot_id}")
        return None
    
    # Engineer features
    df = engineer_features(df)
    
    # Preprocess and predict with lot-specific resources
    result = preprocess_and_predict(df, resources, parking_lot_id)
    
    # Print predictions
    print(f"\n{'='*60}")
    print(f"PREDICTIONS FOR LOT {parking_lot_id}")
    print(f"{'='*60}")
    for i, (ts, pred) in enumerate(zip(result['timestamps'], result['predictions'])):
        print(f"  Hour {i+1:2d}: {ts.strftime('%Y-%m-%d %H:00')} -> {int(pred):4d} spaces")
    
    # Save to database
    if save_to_db:
        try:
            save_predictions_to_db(result)
        except Exception as e:
            print(f"Warning: Could not save to DB: {e}")
    
    return result


def run_all_predictions(model_name='linear_regression', save_to_db=True):
    """
    Run predictions for ALL parking lots.
    Each lot uses its OWN encoder, scalers, and model.
    """
    print("\n" + "="*70)
    print("PARKING AVAILABILITY PREDICTION SYSTEM")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Model: {model_name}")
    
    # Both lots to predict
    lots = [38, 634]
    results = {}
    
    for lot_id in lots:
        try:
            result = predict_for_lot(
                parking_lot_id=lot_id,
                model_name=model_name,
                save_to_db=save_to_db
            )
            if result:
                results[lot_id] = result
        except Exception as e:
            print(f"\n✗ Lot {lot_id} FAILED: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "="*70)
    print("PREDICTION SUMMARY")
    print("="*70)
    
    for lot_id, result in results.items():
        avg_pred = np.mean(result['predictions'])
        min_pred = min(result['predictions'])
        max_pred = max(result['predictions'])
        print(f"\nLot {lot_id}:")
        print(f"  Model: {result['model_name']}")
        print(f"  Last known: {result['last_known_value']:.0f} spaces")
        print(f"  Predicted: {min_pred} - {max_pred} (avg: {avg_pred:.0f}) spaces")
    
    print("\n" + "="*70)
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Completed: {len(results)}/{len(lots)} lots")
    print("="*70)
    
    return results


if __name__ == "__main__":
    results = run_all_predictions(
        model_name='linear_regression',
        save_to_db=True
    )
