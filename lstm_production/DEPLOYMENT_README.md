# LSTM Parking Prediction Model - Deployment Package

## Model Information
- **Model Type**: LSTM (Long Short-Term Memory)
- **Task**: 24-hour parking availability prediction
- **Input**: 48 hours of historical data
- **Output**: 24 hours ahead predictions
- **Training Date**: 2025-12-07 20:49:58
- **Performance Metrics**:
  - RMSE: 11.90 parking spaces
  - MAE: 10.21 parking spaces
  - R²: 0.6416
  - MAPE: 10.98%

## Files in This Package
1. **lstm_model.keras** - Trained LSTM model (TensorFlow/Keras format)
2. **scalers.pkl** - MinMaxScalers for all 48 features
3. **config.json** - Model configuration and metadata
4. **DEPLOYMENT_README.md** - This file

## Required Dependencies
```
tensorflow>=2.10.0
numpy>=1.21.0
pandas>=1.3.0
scikit-learn>=1.0.0
```

## Quick Start - Loading the Model
```python
import pickle
import json
from tensorflow import keras

# Load model
model = keras.models.load_model('lstm_production/lstm_model.keras')

# Load scalers
with open('lstm_production/scalers.pkl', 'rb') as f:
    scalers = pickle.load(f)

# Load config
with open('lstm_production/config.json', 'r') as f:
    config = json.load(f)

print("Model loaded successfully!")
```

## Input Data Requirements
- **Format**: NumPy array or Pandas DataFrame
- **Shape**: (n_samples, 48, 20)
- **Features**: 20 features in order:
    1. avg_free_spaces
  2. min_free_spaces
  3. max_free_spaces
  4. free_spaces_range
  5. hour_of_day
  6. day_of_week
  7. day_of_month
  8. calendar_week
  9. temperature_2m
  10. relative_humidity_2m
  11. precipitation
  12. month
  13. avg_free_spaces_rolling_24h
  14. avg_free_spaces_std_24h
  15. avg_free_spaces_diff_1h
  16. temperature_diff_1h
  17. day_type
  18. time_period
  19. temperature_category
  20. precipitation_category

## Making Predictions
```python
# Assuming you have new_data with shape (n_samples, 48, 20)

# 1. Scale the data using the loaded scalers
new_data_scaled = new_data.copy()
for i in range(20):
    new_data_scaled[:, :, i] = scalers[i].transform(new_data[:, :, i])

# 2. Make predictions
predictions = model.predict(new_data_scaled)

# 3. Predictions shape: (n_samples, 24)
# Each sample gets 24 predictions (24 hours ahead)
```

## Production Deployment Tips
1. **API Endpoint**: Wrap the model in Flask/FastAPI
2. **Caching**: Cache scalers and config on startup
3. **Validation**: Validate input data shape and types
4. **Error Handling**: Handle missing values and outliers
5. **Monitoring**: Log predictions and track model drift
6. **Scaling**: Use async processing for batch predictions

## Contact & Support
For questions about this model, refer to the training notebook.
