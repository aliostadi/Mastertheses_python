"""
Parking Dashboard Web Application
Fetches predictions from database and weather forecast from Open-Meteo API,
displays interactive visualizations for parking availability.
"""

import os
import sys
from flask import Flask, render_template, jsonify, request
import psycopg2
import requests
from datetime import datetime, timedelta
import json

# Try to load .env if running locally
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)

# Parking lot capacities (maximum spots) - from actual data
LOT_CAPACITIES = {
    38: 113,   # Actual capacity from database
    634: 64    # Actual capacity from database
}

# Bamberg coordinates
LATITUDE = 49.891
LONGITUDE = 10.887

# Hybrid model mapping for display
HYBRID_MODEL_NAMES = {
    38: "Linear Regression + Encoder-Decoder Neural Network",
    634: "Random Forest + Gradient Boosting"
}

def get_hybrid_model_name(lot_id, db_model_name):
    """Get the hybrid model display name for a parking lot."""
    if "hybrid" in db_model_name.lower():
        return HYBRID_MODEL_NAMES.get(lot_id, f"Hybrid Model (Lot {lot_id})")
    return db_model_name


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


def get_availability_category(probability):
    """
    Categorize the probability of finding a free spot.
    
    Args:
        probability: float between 0 and 1 (free_spots / total_capacity)
    
    Returns:
        tuple: (category_name, color)
    """
    if probability >= 0.5:
        return ("Very High", "#2ecc71")  # Green
    elif probability >= 0.3:
        return ("High", "#f1c40f")       # Yellow
    elif probability >= 0.15:
        return ("Low", "#e67e22")        # Orange
    else:
        return ("Very Low", "#e74c3c")   # Red


def fetch_latest_predictions(lot_id):
    """
    Fetch the latest 24-hour prediction for a specific parking lot.
    Uses predictions_hourly table for accurate target hours.
    
    Returns:
        dict with prediction data or None
    """
    db_config = get_db_config()
    conn = None
    
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        # Get the latest prediction batch for this lot
        query = """
            SELECT 
                prediction_made_at,
                target_hour,
                hours_ahead,
                predicted_free_spaces,
                model_name
            FROM predictions_hourly
            WHERE parking_lot_id = %s
              AND prediction_made_at = (
                  SELECT MAX(prediction_made_at) 
                  FROM predictions_hourly 
                  WHERE parking_lot_id = %s
              )
            ORDER BY hours_ahead
        """
        
        cursor.execute(query, (lot_id, lot_id))
        rows = cursor.fetchall()
        
        if not rows:
            return None
        
        prediction_timestamp = rows[0][0]
        model_name = rows[0][4]
        
        # Extract data from rows
        target_hours = [row[1] for row in rows]
        hours_ahead = [row[2] for row in rows]
        raw_predictions = [row[3] for row in rows]
        
        # Generate hour labels (HH:00 format)
        timestamps = [th.strftime('%H:00') for th in target_hours]
        full_timestamps = [th.isoformat() for th in target_hours]
        
        # Get capacity
        capacity = LOT_CAPACITIES.get(lot_id, 100)
        
        # Clip predictions to valid range [0, capacity]
        # This handles model predictions that exceed physical constraints
        predictions = [max(0, min(pred, capacity)) for pred in raw_predictions]
        
        # Calculate occupied spots and probabilities
        occupied = [capacity - pred for pred in predictions]
        free = predictions
        probabilities = [pred / capacity for pred in predictions]
        categories = [get_availability_category(p) for p in probabilities]
        
        return {
            'lot_id': lot_id,
            'capacity': capacity,
            'prediction_time': prediction_timestamp.isoformat(),
            'model': get_hybrid_model_name(lot_id, model_name),
            'hours': timestamps,
            'full_timestamps': full_timestamps,
            'target_hours': [th.isoformat() for th in target_hours],
            'hours_ahead': hours_ahead,
            'free_spots': free,
            'occupied_spots': occupied,
            'probabilities': probabilities,
            'categories': [c[0] for c in categories],
            'colors': [c[1] for c in categories]
        }
        
    except Exception as e:
        print(f"Database error: {e}")
        return None
    finally:
        if conn:
            conn.close()


def fetch_weather_forecast():
    """
    Fetch 24-hour weather forecast from Open-Meteo API.
    
    Returns:
        dict with weather data
    """
    try:
        now = datetime.now()
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        end_hour = current_hour + timedelta(hours=24)
        
        params = {
            'latitude': LATITUDE,
            'longitude': LONGITUDE,
            'hourly': [
                'temperature_2m',
                'relative_humidity_2m',
                'precipitation',
                'weather_code'
            ],
            'start_date': current_hour.strftime('%Y-%m-%d'),
            'end_date': end_hour.strftime('%Y-%m-%d'),
            'timezone': 'auto'
        }
        
        response = requests.get(
            'https://api.open-meteo.com/v1/forecast',
            params=params,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        hourly = data.get('hourly', {})
        times = hourly.get('time', [])
        temps = hourly.get('temperature_2m', [])
        humidity = hourly.get('relative_humidity_2m', [])
        precipitation = hourly.get('precipitation', [])
        weather_codes = hourly.get('weather_code', [])
        
        # Filter to next 24 hours from now
        current_iso = current_hour.isoformat()
        start_idx = 0
        for i, t in enumerate(times):
            if t >= current_iso[:13]:  # Compare hour level
                start_idx = i
                break
        
        end_idx = min(start_idx + 24, len(times))
        
        # Weather code descriptions
        weather_descriptions = {
            0: "Clear", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
            45: "Fog", 48: "Depositing Rime Fog",
            51: "Light Drizzle", 53: "Moderate Drizzle", 55: "Dense Drizzle",
            61: "Slight Rain", 63: "Moderate Rain", 65: "Heavy Rain",
            71: "Slight Snow", 73: "Moderate Snow", 75: "Heavy Snow",
            80: "Slight Showers", 81: "Moderate Showers", 82: "Violent Showers",
            95: "Thunderstorm", 96: "Thunderstorm with Hail", 99: "Thunderstorm with Heavy Hail"
        }
        
        # Current weather
        current_temp = temps[start_idx] if temps else None
        current_weather = weather_descriptions.get(weather_codes[start_idx], "Unknown") if weather_codes else "Unknown"
        
        return {
            'current': {
                'temperature': current_temp,
                'humidity': humidity[start_idx] if humidity else None,
                'precipitation': precipitation[start_idx] if precipitation else None,
                'weather': current_weather,
                'timestamp': times[start_idx] if times else None
            },
            'forecast': {
                'hours': [t[11:16] for t in times[start_idx:end_idx]],  # HH:MM format
                'full_timestamps': times[start_idx:end_idx],
                'temperatures': temps[start_idx:end_idx],
                'humidity': humidity[start_idx:end_idx],
                'precipitation': precipitation[start_idx:end_idx],
                'weather_codes': weather_codes[start_idx:end_idx],
                'weather_descriptions': [weather_descriptions.get(c, "Unknown") for c in weather_codes[start_idx:end_idx]]
            }
        }
        
    except Exception as e:
        print(f"Weather API error: {e}")
        return None


def fetch_current_status(lot_id):
    """
    Fetch the latest minute-level data for a parking lot.
    Returns current availability status as KPI.
    """
    db_config = get_db_config()
    conn = None
    
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        query = """
            SELECT 
                minute_timestamp,
                free_spaces,
                occupied_spaces,
                total_spaces,
                occupancy_rate,
                parking_lot_name
            FROM parking_availability_minute
            WHERE parking_lot_id = %s
            ORDER BY minute_timestamp DESC
            LIMIT 1
        """
        
        cursor.execute(query, (lot_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        timestamp, free, occupied, total, occupancy_rate, name = row
        capacity = LOT_CAPACITIES.get(lot_id, total or 100)
        probability = free / capacity if capacity > 0 else 0
        category, color = get_availability_category(probability)
        
        return {
            'lot_id': lot_id,
            'lot_name': name or f'Parking Lot {lot_id}',
            'timestamp': timestamp.isoformat() if timestamp else None,
            'free_spaces': int(free) if free else 0,
            'occupied_spaces': int(occupied) if occupied else 0,
            'total_spaces': int(capacity),
            'occupancy_rate': float(occupancy_rate) if occupancy_rate else 0,
            'availability_probability': round(probability * 100, 1),
            'availability_category': category,
            'availability_color': color
        }
        
    except Exception as e:
        print(f"Database error fetching current status: {e}")
        return None
    finally:
        if conn:
            conn.close()


def fetch_historical_data(lot_id, hours_back=48):
    """
    Fetch last N hours of historical parking data for a lot.
    
    Returns:
        dict with historical data or None
    """
    db_config = get_db_config()
    conn = None
    
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        query = """
            SELECT 
                hour_timestamp,
                avg_free_spaces
            FROM training_data_hourly
            WHERE parking_lot_id = %s
            ORDER BY hour_timestamp DESC
            LIMIT %s
        """
        
        cursor.execute(query, (lot_id, hours_back))
        rows = cursor.fetchall()
        
        if not rows:
            return None
        
        # Reverse to get chronological order
        rows = list(reversed(rows))
        
        timestamps = [row[0].strftime('%H:00') for row in rows]
        full_timestamps = [row[0].isoformat() for row in rows]
        values = [float(row[1]) if row[1] else 0 for row in rows]
        
        return {
            'lot_id': lot_id,
            'hours': timestamps,
            'full_timestamps': full_timestamps,
            'free_spots': values
        }
        
    except Exception as e:
        print(f"Database error fetching historical data: {e}")
        return None
    finally:
        if conn:
            conn.close()


@app.route('/')
def index():
    """Render main dashboard page."""
    return render_template('index.html')


@app.route('/api/current-status')
def get_current_status():
    """API endpoint to get current real-time status for all lots."""
    status = {}
    for lot_id in LOT_CAPACITIES.keys():
        current = fetch_current_status(lot_id)
        if current:
            status[lot_id] = current
    
    return jsonify({
        'status': 'success',
        'data': status,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/current-status/<int:lot_id>')
def get_lot_current_status(lot_id):
    """API endpoint to get current real-time status for a specific lot."""
    current = fetch_current_status(lot_id)
    
    if current:
        return jsonify({
            'status': 'success',
            'data': current
        })
    else:
        return jsonify({
            'status': 'error',
            'message': f'No current data found for lot {lot_id}'
        }), 404


@app.route('/api/predictions')
def get_predictions():
    """API endpoint to get predictions for all lots."""
    predictions = {}
    for lot_id in LOT_CAPACITIES.keys():
        pred = fetch_latest_predictions(lot_id)
        if pred:
            predictions[lot_id] = pred
    
    return jsonify({
        'status': 'success',
        'data': predictions,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/predictions/<int:lot_id>')
def get_lot_predictions(lot_id):
    """API endpoint to get predictions for a specific lot."""
    pred = fetch_latest_predictions(lot_id)
    
    if pred:
        return jsonify({
            'status': 'success',
            'data': pred
        })
    else:
        return jsonify({
            'status': 'error',
            'message': f'No predictions found for lot {lot_id}'
        }), 404


@app.route('/api/historical/<int:lot_id>')
def get_lot_historical(lot_id):
    """API endpoint to get historical data for a specific lot."""
    hours = request.args.get('hours', 48, type=int)
    historical = fetch_historical_data(lot_id, hours)
    
    if historical:
        return jsonify({
            'status': 'success',
            'data': historical
        })
    else:
        return jsonify({
            'status': 'error',
            'message': f'No historical data found for lot {lot_id}'
        }), 404


@app.route('/api/trend/<int:lot_id>')
def get_lot_trend(lot_id):
    """API endpoint to get combined historical + prediction trend for a lot."""
    historical = fetch_historical_data(lot_id, 48)
    prediction = fetch_latest_predictions(lot_id)
    
    if historical and prediction:
        return jsonify({
            'status': 'success',
            'historical': historical,
            'prediction': prediction
        })
    else:
        return jsonify({
            'status': 'error',
            'message': f'Data not available for lot {lot_id}'
        }), 404


@app.route('/api/weather')
def get_weather():
    """API endpoint to get weather forecast."""
    weather = fetch_weather_forecast()
    
    if weather:
        return jsonify({
            'status': 'success',
            'data': weather
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Failed to fetch weather data'
        }), 500


@app.route('/api/dashboard')
def get_dashboard_data():
    """API endpoint to get all dashboard data (predictions + weather + historical + current status)."""
    predictions = {}
    historical = {}
    current_status = {}
    for lot_id in LOT_CAPACITIES.keys():
        pred = fetch_latest_predictions(lot_id)
        if pred:
            predictions[lot_id] = pred
        hist = fetch_historical_data(lot_id, 48)
        if hist:
            historical[lot_id] = hist
        current = fetch_current_status(lot_id)
        if current:
            current_status[lot_id] = current
    
    weather = fetch_weather_forecast()
    
    return jsonify({
        'status': 'success',
        'predictions': predictions,
        'historical': historical,
        'current_status': current_status,
        'weather': weather,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/ml-performance')
def get_ml_performance():
    """API endpoint to get ML model performance metrics."""
    db_config = get_db_config()
    conn = None
    
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        # Overall metrics per lot/model
        overall_query = """
            SELECT 
                parking_lot_id,
                model_name,
                COUNT(*) as total_predictions,
                AVG(absolute_error) as mae,
                SQRT(AVG(prediction_error * prediction_error)) as rmse,
                AVG(percentage_error) as mape,
                MIN(target_hour) as first_prediction,
                MAX(target_hour) as last_prediction
            FROM predictions_hourly
            WHERE actual_free_spaces IS NOT NULL
            GROUP BY parking_lot_id, model_name
            ORDER BY parking_lot_id, model_name
        """
        
        cursor.execute(overall_query)
        overall_rows = cursor.fetchall()
        
        overall_metrics = []
        for row in overall_rows:
            overall_metrics.append({
                'lot_id': row[0],
                'model': row[1],
                'count': row[2],
                'mae': float(row[3]) if row[3] else None,
                'rmse': float(row[4]) if row[4] else None,
                'mape': float(row[5]) if row[5] else None,
                'first_prediction': row[6].isoformat() if row[6] else None,
                'last_prediction': row[7].isoformat() if row[7] else None
            })
        
        # Metrics by hours_ahead
        hourly_query = """
            SELECT 
                parking_lot_id,
                model_name,
                hours_ahead,
                COUNT(*) as count,
                AVG(absolute_error) as mae,
                AVG(percentage_error) as mape
            FROM predictions_hourly
            WHERE actual_free_spaces IS NOT NULL
            GROUP BY parking_lot_id, model_name, hours_ahead
            ORDER BY parking_lot_id, model_name, hours_ahead
        """
        
        cursor.execute(hourly_query)
        hourly_rows = cursor.fetchall()
        
        hourly_metrics = []
        for row in hourly_rows:
            hourly_metrics.append({
                'lot_id': row[0],
                'model': row[1],
                'hours_ahead': row[2],
                'count': row[3],
                'mae': float(row[4]) if row[4] else None,
                'mape': float(row[5]) if row[5] else None
            })
        
        # Recent errors (last 48 hours)
        recent_query = """
            SELECT 
                target_hour,
                parking_lot_id,
                hours_ahead,
                predicted_free_spaces,
                actual_free_spaces,
                prediction_error,
                percentage_error
            FROM predictions_hourly
            WHERE actual_free_spaces IS NOT NULL
              AND evaluated_at > NOW() - INTERVAL '48 hours'
            ORDER BY target_hour DESC
            LIMIT 100
        """
        
        cursor.execute(recent_query)
        recent_rows = cursor.fetchall()
        
        recent_errors = []
        for row in recent_rows:
            recent_errors.append({
                'target_hour': row[0].isoformat(),
                'lot_id': row[1],
                'hours_ahead': row[2],
                'predicted': row[3],
                'actual': row[4],
                'error': float(row[5]) if row[5] else None,
                'percentage_error': float(row[6]) if row[6] else None
            })
        
        return jsonify({
            'status': 'success',
            'overall_metrics': overall_metrics,
            'hourly_metrics': hourly_metrics,
            'recent_errors': recent_errors,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    print(f"Starting Parking Dashboard on port {port}")
    print(f"Debug mode: {debug}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
