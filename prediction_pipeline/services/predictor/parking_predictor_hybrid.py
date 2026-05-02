#!/usr/bin/env python3
"""
ENHANCED PARKING PREDICTOR WITH LOCAL WEIGHTED BLENDING HYBRID MODEL
=====================================================================

This predictor combines TWO models per lot using optimized alpha values per horizon:
- Lot 38: Linear Regression + Encoder-Decoder (24 alpha values)
- Lot 634: Random Forest + Gradient Boosting (24 alpha values)

Blending Formula: y_hybrid[:, h] = (alpha * model_A) + ((1-alpha) * model_B)
- Each horizon (1-24 hours) has its own optimized alpha weight
- Alpha values are pre-calculated and stored in local_weighted_blend_hybrid_metadata.json

Author: Generated for Advanced ML Deployment
Date: 2025-01-09
"""

import os
import sys
import json
import pickle
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import psycopg2
from sklearn.preprocessing import LabelEncoder
import tensorflow as tf
from tensorflow.keras.models import load_model


def get_db_config():
    """Database configuration from environment variables."""
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


def generate_mock_data(parking_lot_id, hours_back=72):
    """
    Generate realistic mock data for offline testing.
    Simulates parking patterns with realistic variations.
    """
    # Lot-specific configurations
    if parking_lot_id == 38:
        total_spaces = 120
        typical_occupancy = 0.65  # 65% typical occupancy
    elif parking_lot_id == 634:
        total_spaces = 200
        typical_occupancy = 0.55  # 55% typical occupancy
    else:
        total_spaces = 100
        typical_occupancy = 0.6
    
    print(f"🧪 Generating {hours_back} hours of mock data for lot {parking_lot_id} ({total_spaces} spaces)")
    
    # Generate timestamp range
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours_back)
    
    data = []
    current_time = start_time
    
    while current_time <= end_time:
        hour_of_day = current_time.hour
        day_of_week = current_time.weekday()  # 0=Monday, 6=Sunday
        is_weekend = 1 if day_of_week >= 5 else 0
        
        # Create realistic occupancy patterns
        if is_weekend:
            # Weekend pattern: lighter in morning, busier afternoon
            if 6 <= hour_of_day <= 10:
                base_occupancy = typical_occupancy * 0.7  # Lighter morning
            elif 11 <= hour_of_day <= 16:
                base_occupancy = typical_occupancy * 1.1  # Busier afternoon
            else:
                base_occupancy = typical_occupancy * 0.8
        else:
            # Weekday pattern: rush hours
            if 7 <= hour_of_day <= 9 or 17 <= hour_of_day <= 19:
                base_occupancy = typical_occupancy * 1.2  # Rush hours
            elif 10 <= hour_of_day <= 16:
                base_occupancy = typical_occupancy * 0.9  # Business hours
            else:
                base_occupancy = typical_occupancy * 0.6  # Off hours
        
        # Add random variation (±15%)
        variation = random.uniform(-0.15, 0.15)
        actual_occupancy = max(0.1, min(0.95, base_occupancy + variation))
        
        free_spaces = int(total_spaces * (1 - actual_occupancy))
        occupancy_rate = 1 - (free_spaces / total_spaces)
        
        data.append({
            'timestamp': current_time,
            'free_spaces': free_spaces,
            'total_spaces': total_spaces,
            'occupancy_rate': occupancy_rate,
            'day_of_week': day_of_week,
            'hour_of_day': hour_of_day,
            'is_weekend': is_weekend
        })
        
        current_time += timedelta(hours=1)
    
    df = pd.DataFrame(data)
    
    print(f"✓ Generated {len(df)} mock records")
    print(f"  - Free spaces range: {df['free_spaces'].min():.0f} - {df['free_spaces'].max():.0f}")
    print(f"  - Average occupancy: {df['occupancy_rate'].mean():.1%}")
    
    # Apply feature engineering to mock data (same as real data pipeline)
    print("🔧 Applying feature engineering to mock data...")
    df = engineer_features(df)
    
    return df


def load_hybrid_lot_resources(parking_lot_id):
    """
    Load resources for hybrid prediction including TWO models per lot.
    
    Lot 38: Linear Regression + Encoder-Decoder
    Lot 634: Random Forest + Gradient Boosting
    
    Returns:
        dict: Contains both models, preprocessing components, and alpha values
    """
    try:
        models_dir = f'models/lot{parking_lot_id}'
        
        print(f"Loading hybrid resources from {models_dir}...")
        
        # Common resources (same for all lots)
        with open(f'{models_dir}/config.json', 'r') as f:
            config = json.load(f)
        
        with open(f'{models_dir}/encoder.pkl', 'rb') as f:
            encoder = pickle.load(f)
            
        with open(f'{models_dir}/scalers.pkl', 'rb') as f:
            scalers = pickle.load(f)
        
        # Load alpha values for local weighted blending
        with open(f'{models_dir}/local_weighted_blend_hybrid_metadata.json', 'r') as f:
            hybrid_metadata = json.load(f)
            alpha_values = hybrid_metadata['optimized_alpha_per_horizon']
        
        # Load TWO models per lot based on lot configuration
        if parking_lot_id == 38:
            # Lot 38: Linear Regression + Encoder-Decoder
            print("  → Loading Linear Regression model...")
            with open(f'{models_dir}/linear_regression_model.pkl', 'rb') as f:
                model_a = pickle.load(f)
            
            print("  → Loading Encoder-Decoder model...")
            model_b = load_model(f'{models_dir}/encoder_decoder_model.keras')
            
            model_types = {
                'model_a_type': 'linear_regression',
                'model_b_type': 'encoder_decoder'
            }
            
        elif parking_lot_id == 634:
            # Lot 634: Random Forest + Gradient Boosting  
            print("  → Loading Random Forest model...")
            with open(f'{models_dir}/random_forest_model.pkl', 'rb') as f:
                model_a = pickle.load(f)
            
            print("  → Loading Gradient Boosting model...")
            with open(f'{models_dir}/gradient_boosting_model.pkl', 'rb') as f:
                model_b = pickle.load(f)
            
            model_types = {
                'model_a_type': 'random_forest',
                'model_b_type': 'gradient_boosting'
            }
        
        else:
            raise ValueError(f"Hybrid configuration not defined for lot {parking_lot_id}")
        
        print(f"✓ Loaded lot {parking_lot_id} hybrid resources:")
        print(f"  - Model A: {model_types['model_a_type']}")
        print(f"  - Model B: {model_types['model_b_type']}")
        print(f"  - Alpha values: {len(alpha_values)} horizons")
        print(f"  - Alpha range: {min(alpha_values):.2f} - {max(alpha_values):.2f}")
        
        return {
            'config': config,
            'encoder': encoder,
            'scalers': scalers,
            'model_a': model_a,
            'model_b': model_b,
            'model_types': model_types,
            'alpha_values': alpha_values,
            'parking_lot_id': parking_lot_id
        }
        
    except Exception as e:
        print(f"✗ Error loading lot {parking_lot_id} resources: {e}")
        raise


def fetch_training_data(parking_lot_id, hours_back=72, offline_mode=False):
    """Fetch recent data for prediction (same as original)."""
    
    # For local testing without database
    if offline_mode:
        return generate_mock_data(parking_lot_id, hours_back)
    
    db_config = get_db_config()
    conn = None  # Initialize conn to avoid UnboundLocalError
    
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        query = """
        SELECT timestamp, free_spaces, total_spaces, occupancy_rate, day_of_week, hour_of_day, is_weekend
        FROM parking_data 
        WHERE parking_lot_id = %s AND timestamp >= %s
        ORDER BY timestamp ASC
        """
        
        cursor.execute(query, (parking_lot_id, cutoff_time))
        result = cursor.fetchall()
        
        if not result:
            print(f"No data found for lot {parking_lot_id}")
            return None
            
        df = pd.DataFrame(result, columns=[
            'timestamp', 'free_spaces', 'total_spaces', 'occupancy_rate',
            'day_of_week', 'hour_of_day', 'is_weekend'
        ])
        
        print(f"✓ Fetched {len(df)} records for lot {parking_lot_id}")
        return df
        
    except Exception as e:
        print(f"Database fetch error: {e}")
        return None
    finally:
        if conn:
            conn.close()


def engineer_features(df):
    """Feature engineering (same as original)."""
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Rolling averages
    df['free_spaces_ma_3'] = df['free_spaces'].rolling(window=3, min_periods=1).mean()
    df['free_spaces_ma_6'] = df['free_spaces'].rolling(window=6, min_periods=1).mean()
    df['free_spaces_ma_12'] = df['free_spaces'].rolling(window=12, min_periods=1).mean()
    df['free_spaces_ma_24'] = df['free_spaces'].rolling(window=24, min_periods=1).mean()
    
    # Lag features
    for lag in [1, 2, 3, 6, 12, 24]:
        df[f'free_spaces_lag_{lag}'] = df['free_spaces'].shift(lag)
        df[f'occupancy_rate_lag_{lag}'] = df['occupancy_rate'].shift(lag)
    
    # Trend indicators
    df['trend_1h'] = df['free_spaces'] - df['free_spaces'].shift(1)
    df['trend_3h'] = df['free_spaces'] - df['free_spaces'].shift(3)
    df['trend_6h'] = df['free_spaces'] - df['free_spaces'].shift(6)
    
    # Time features
    df['hour_sin'] = np.sin(2 * np.pi * df['hour_of_day'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour_of_day'] / 24)
    df['day_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
    df['day_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
    
    return df


def preprocess_and_predict_hybrid(df, resources):
    """
    Enhanced preprocessing and prediction using TWO models with local weighted blending.
    
    Applies the formula: y_hybrid[:, h] = (alpha * model_A) + ((1-alpha) * model_B)
    """
    try:
        config = resources['config']
        encoder = resources['encoder']
        scalers = resources['scalers']
        model_a = resources['model_a']
        model_b = resources['model_b']
        model_types = resources['model_types']
        alpha_values = resources['alpha_values']
        parking_lot_id = resources['parking_lot_id']
        
        # Use latest data point as starting point
        latest_idx = len(df) - 1
        latest_data = df.iloc[latest_idx].copy()
        last_known_value = latest_data['free_spaces']
        
        print(f"Starting prediction from: {latest_data['timestamp']}")
        print(f"Last known value: {last_known_value:.0f} spaces")
        
        # Prepare features for prediction
        # Use original feature set to match trained models (20 features as per config)
        # Based on config.json: models were trained with these specific 20 features
        original_features = [
            'free_spaces', 'occupancy_rate', 'hour_of_day', 'day_of_week', 'is_weekend',
            'free_spaces_ma_3', 'free_spaces_ma_6', 'free_spaces_ma_12', 'free_spaces_ma_24',
            'free_spaces_lag_1', 'free_spaces_lag_2', 'free_spaces_lag_3', 'free_spaces_lag_6', 'free_spaces_lag_12', 'free_spaces_lag_24',
            'trend_1h', 'trend_3h', 'trend_6h', 
            'hour_sin', 'hour_cos'
        ]
        
        # Use only the features that exist and match the trained model (20 features)
        available_features = [col for col in original_features if col in df.columns]
        sequence_length = config.get('sequence_length', config.get('past_history', 48))
        
        print(f"Model expects 20 features × {sequence_length} timesteps = {20 * sequence_length} total")
        print(f"Using {len(available_features)} available features: {available_features[:3]}...{available_features[-2:]}")
        
        # Pad with zeros or duplicate features if we have fewer than 20
        if len(available_features) < 20:
            print(f"⚠️ Warning: Only {len(available_features)}/20 features available, padding with defaults")
            # Add missing features as zeros
            for i in range(20 - len(available_features)):
                col_name = f'missing_feature_{i}'
                df[col_name] = 0
                available_features.append(col_name)
        elif len(available_features) > 20:
            print(f"📉 Truncating to first 20 features to match trained model")
            available_features = available_features[:20]
        
        X_latest = df[available_features].iloc[-sequence_length:].copy()
        
        # Handle missing values before scaling
        print("🧹 Handling missing values...")
        for col in X_latest.columns:
            if X_latest[col].isna().any():
                if col in ['day_of_week', 'hour_of_day', 'is_weekend']:
                    X_latest[col] = X_latest[col].fillna(latest_data[col] if col in latest_data else 0)
                else:
                    X_latest[col] = X_latest[col].fillna(method='ffill').fillna(method='bfill').fillna(0)
        
        print(f"✓ Prepared feature matrix: {X_latest.shape}")
        
        # Scale features
        try:
            X_scaled = scalers['feature_scaler'].transform(X_latest)
            print("✓ Features scaled successfully")
        except Exception as e:
            print(f"⚠️ Scaling warning: {e}")
            # Fallback: use raw features if scaling fails
            X_scaled = X_latest.values
        
        # Prepare input format based on model requirements
        # Models expect flattened sequence: (samples, timesteps * features)
        print(f"📐 Reshaping data for model input...")
        print(f"   Original shape: {X_scaled.shape}")
        
        # Flatten the sequence for scikit-learn models
        X_flattened = X_scaled.flatten().reshape(1, -1)
        print(f"   Flattened shape: {X_flattened.shape}")
        
        # For neural networks, keep 3D shape: (batch, timesteps, features) 
        X_sequence = X_scaled.reshape(1, X_scaled.shape[0], X_scaled.shape[1])
        print(f"   Sequence shape: {X_sequence.shape}")
        
        # Prepare for predictions
        predictions_24h = []
        timestamps_24h = []
        current_time = pd.to_datetime(latest_data['timestamp']) + timedelta(hours=1)
        
        # ========================================
        # DUAL MODEL PREDICTIONS WITH BLENDING
        # ========================================
        
        print(f"\nRunning hybrid predictions with {model_types['model_a_type']} + {model_types['model_b_type']}...")
        
        for hour in range(24):
            target_time = current_time + timedelta(hours=hour)
            timestamps_24h.append(target_time)
            
            # ===================
            # MODEL A PREDICTION
            # ===================
            if model_types['model_a_type'] == 'encoder_decoder':
                # Encoder-decoder expects 3D input: (batch_size, sequence_length, features)
                input_a = X_sequence
                pred_a_full = model_a.predict(input_a, verbose=0)[0]  # Get predictions for all hours
                
                # Handle different output shapes from encoder-decoder
                if len(pred_a_full.shape) > 0 and pred_a_full.shape[0] >= 24:
                    # Multi-hour output: extract specific hour
                    pred_a_raw = pred_a_full[hour]
                elif len(pred_a_full.shape) > 0 and pred_a_full.shape[0] == 1:
                    # Single output: use as-is for all hours
                    pred_a_raw = pred_a_full[0]
                else:
                    # Fallback: use the prediction as-is
                    pred_a_raw = pred_a_full
                
                # Ensure scalar value for encoder-decoder
                pred_a_raw = float(np.asarray(pred_a_raw).flatten()[0])
            else:
                # Scikit-learn models expect flattened sequence input
                input_a = X_flattened
                pred_a_raw = model_a.predict(input_a)[0]
                # For multi-output models, get the specific hour prediction
                if hasattr(pred_a_raw, '__len__') and len(pred_a_raw) > 1:
                    pred_a_raw = pred_a_raw[hour] if hour < len(pred_a_raw) else pred_a_raw[-1]
                # Ensure scalar value
                pred_a_raw = float(pred_a_raw)
            
            # ===================
            # MODEL B PREDICTION  
            # ===================
            if model_types['model_b_type'] == 'encoder_decoder':
                # Encoder-decoder expects 3D input
                input_b = X_sequence
                pred_b_full = model_b.predict(input_b, verbose=0)[0]  # Get predictions for all hours
                
                # Handle different output shapes from encoder-decoder
                if len(pred_b_full.shape) > 0 and pred_b_full.shape[0] >= 24:
                    # Multi-hour output: extract specific hour
                    pred_b_raw = pred_b_full[hour]
                elif len(pred_b_full.shape) > 0 and pred_b_full.shape[0] == 1:
                    # Single output: use as-is for all hours
                    pred_b_raw = pred_b_full[0]
                else:
                    # Fallback: use the prediction as-is
                    pred_b_raw = pred_b_full
                
                # Ensure scalar value for encoder-decoder
                pred_b_raw = float(np.asarray(pred_b_raw).flatten()[0])
            else:
                # Scikit-learn models expect flattened sequence input
                input_b = X_flattened
                pred_b_raw = model_b.predict(input_b)[0]
                # For multi-output models, get the specific hour prediction
                if hasattr(pred_b_raw, '__len__') and len(pred_b_raw) > 1:
                    pred_b_raw = pred_b_raw[hour] if hour < len(pred_b_raw) else pred_b_raw[-1]
                # Ensure scalar value
                pred_b_raw = float(pred_b_raw)
            
            # ========================================
            # LOCAL WEIGHTED BLENDING WITH ALPHA
            # ========================================
            alpha = alpha_values[hour]  # Use hour-specific alpha value
            
            # Apply blending formula: y_hybrid = alpha * model_A + (1-alpha) * model_B
            blended_prediction = (alpha * pred_a_raw) + ((1 - alpha) * pred_b_raw)
            
            # Inverse transform to get actual values (handle missing target_scaler)
            try:
                if 'target_scaler' in scalers:
                    pred_scaled = np.array([[blended_prediction]])
                    pred_actual = scalers['target_scaler'].inverse_transform(pred_scaled)[0, 0]
                elif 'y_scaler' in scalers:
                    pred_scaled = np.array([[blended_prediction]])
                    pred_actual = scalers['y_scaler'].inverse_transform(pred_scaled)[0, 0]
                else:
                    # No target scaling available, use raw prediction
                    pred_actual = blended_prediction
                    print(f"⚠️ No target scaler found, using raw prediction for hour {hour+1}")
            except Exception as e:
                print(f"⚠️ Scaling error for hour {hour+1}: {e}, using raw prediction")
                pred_actual = blended_prediction
            
            # Apply constraints (0 <= prediction <= total_spaces)
            pred_constrained = np.clip(pred_actual, 0, latest_data['total_spaces'])
            predictions_24h.append(pred_constrained)
            
            # Debug output for first few predictions
            if hour < 3:
                print(f"  Hour {hour+1:2d}: α={alpha:.2f} | A={pred_a_raw:.1f} | B={pred_b_raw:.1f} | Blend={blended_prediction:.1f} | Final={pred_constrained:.0f}")
        
        print(f"✓ Completed 24-hour hybrid predictions")
        
        # Return comprehensive results
        return {
            'predictions': predictions_24h,
            'timestamps': timestamps_24h,
            'parking_lot_id': parking_lot_id,
            'model_name': f"hybrid_{model_types['model_a_type']}_{model_types['model_b_type']}",
            'model_details': {
                'model_a': model_types['model_a_type'],
                'model_b': model_types['model_b_type'],
                'alpha_values': alpha_values,
                'blending_method': 'local_weighted_blend'
            },
            'last_known_value': last_known_value,
            'prediction_timestamp': datetime.now()
        }
        
    except Exception as e:
        print(f"Prediction error: {e}")
        import traceback
        traceback.print_exc()
        raise


def save_predictions_to_db(prediction_result):
    """Save hybrid predictions to database (same structure as original)."""
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
            0.92  # Higher confidence for hybrid model
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
        print(f"✓ Saved hybrid predictions to database: Lot {parking_lot_id} ({model_name})")
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Database save error: {e}")
        raise
    finally:
        if conn:
            conn.close()


def predict_hybrid_for_lot(parking_lot_id, save_to_db=True, offline_mode=False):
    """
    Run complete HYBRID prediction pipeline for a single lot.
    Uses TWO models per lot with local weighted blending.
    """
    print(f"\n{'#'*80}")
    print(f"# HYBRID PREDICTION FOR LOT {parking_lot_id}")
    print(f"{'#'*80}")
    
    # Load lot-specific hybrid resources (both models + alpha values)
    resources = load_hybrid_lot_resources(parking_lot_id)
    
    # Fetch data for this lot
    if offline_mode:
        print(f"\n🧪 Generating mock data for lot {parking_lot_id} (offline test mode)...")
    else:
        print(f"\nFetching data for lot {parking_lot_id}...")
    df = fetch_training_data(parking_lot_id, hours_back=72, offline_mode=offline_mode)
    if df is None:
        print(f"✗ No data for lot {parking_lot_id}")
        return None
    
    # Engineer features
    df = engineer_features(df)
    
    # Run hybrid prediction with dual models and blending
    result = preprocess_and_predict_hybrid(df, resources)
    
    # Print detailed results
    print(f"\n{'='*70}")
    print(f"HYBRID PREDICTIONS FOR LOT {parking_lot_id}")
    print(f"{'='*70}")
    print(f"Model Combination: {result['model_details']['model_a']} + {result['model_details']['model_b']}")
    print(f"Blending Method: {result['model_details']['blending_method']}")
    print(f"Last Known Value: {result['last_known_value']:.0f} spaces")
    print("-" * 70)
    
    for i, (ts, pred) in enumerate(zip(result['timestamps'], result['predictions'])):
        alpha = result['model_details']['alpha_values'][i]
        print(f"  Hour {i+1:2d}: {ts.strftime('%Y-%m-%d %H:00')} -> {int(pred):4d} spaces (α={alpha:.2f})")
    
    avg_pred = np.mean(result['predictions'])
    print("-" * 70)
    print(f"Summary: {int(min(result['predictions']))}-{int(max(result['predictions']))} spaces (avg: {avg_pred:.0f})")
    
    # Save to database
    if save_to_db:
        try:
            save_predictions_to_db(result)
        except Exception as e:
            print(f"Warning: Could not save to DB: {e}")
    
    return result


def run_all_hybrid_predictions(save_to_db=True, offline_mode=False):
    """
    Run HYBRID predictions for ALL parking lots.
    Each lot uses TWO models with optimized local weighted blending.
    """
    print("\n" + "="*80)
    print("ADVANCED PARKING PREDICTION SYSTEM - HYBRID LOCAL WEIGHTED BLENDING")
    print("="*80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if offline_mode:
        print("Mode: OFFLINE TESTING with mock data")
    else:
        print("Mode: LIVE with database connection")
    print("Model Strategy: Two models per lot with horizon-specific alpha blending")
    
    # Both lots to predict
    lots = [38, 634]
    results = {}
    
    for lot_id in lots:
        try:
            result = predict_hybrid_for_lot(
                parking_lot_id=lot_id,
                save_to_db=save_to_db and not offline_mode,  # Don't save to DB in offline mode
                offline_mode=offline_mode
            )
            if result:
                results[lot_id] = result
        except Exception as e:
            print(f"\n✗ Lot {lot_id} FAILED: {e}")
            import traceback
            traceback.print_exc()
    
    # Comprehensive summary
    print("\n" + "="*80)
    print("HYBRID PREDICTION SUMMARY")
    print("="*80)
    
    for lot_id, result in results.items():
        model_details = result['model_details']
        avg_pred = np.mean(result['predictions'])
        min_pred = min(result['predictions'])
        max_pred = max(result['predictions'])
        avg_alpha = np.mean(model_details['alpha_values'])
        
        print(f"\nLot {lot_id}:")
        print(f"  Hybrid Models: {model_details['model_a']} + {model_details['model_b']}")
        print(f"  Blending: {model_details['blending_method']} (α avg: {avg_alpha:.2f})")
        print(f"  Last known: {result['last_known_value']:.0f} spaces")
        print(f"  Predicted: {int(min_pred)} - {int(max_pred)} (avg: {avg_pred:.0f}) spaces")
        print(f"  Model ID: {result['model_name']}")
    
    print("\n" + "="*80)
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Successfully completed: {len(results)}/{len(lots)} lots")
    print(f"Enhanced with: Local weighted blending hybrid models")
    print("="*80)
    
    return results


if __name__ == "__main__":
    print("🚀 Starting Enhanced Hybrid Parking Predictor...")
    
    # Check if we can connect to database
    try:
        import psycopg2
        db_config = get_db_config()
        test_conn = psycopg2.connect(**db_config)
        test_conn.close()
        print("✅ Database connection successful - running in LIVE mode")
        results = run_all_hybrid_predictions(save_to_db=True, offline_mode=False)
    except Exception as e:
        print(f"⚠️  Database unavailable: {e}")
        print("🧪 Running in OFFLINE TEST mode with mock data...")
        results = run_all_hybrid_predictions(save_to_db=False, offline_mode=True)
    
    if results:
        print(f"\n🎯 Success! Generated hybrid predictions for {len(results)} lots")
        print("📊 Ready for dashboard visualization")
    else:
        print("\n❌ No predictions generated")