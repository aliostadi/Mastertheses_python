# Training Pipeline - Data Preparation & Model Training

This pipeline is used to prepare datasets and train machine learning models for parking availability forecasting.

**Status**: Offline training (runs locally or on cloud, not in production)

---

##  Overview

The training pipeline consists of:
1. **Data Preparation** - Fetch and clean parking & weather data
2. **Feature Engineering** - Create features for model training
3. **Model Training** - Train hybrid ML models (Lot 38 & Lot 634)
4. **Hyperparameter Optimization** - Optimize alpha blending weights
5. **Model Export** - Save trained models for deployment

---

## 🎯 Running the Pipeline

### **⚙️ Step 1: Configure Credentials (Local Machine)**

#### 🔐 Understanding Credential Security

The file `src/config/settings.py` contains **sensitive credentials** and is **NOT committed to git** (protected in `.gitignore`). 

**How Credentials Work:**
Instead of hardcoding an API key, we use a **secure authentication flow**:

```
1. Store username/password in settings.py (protected)
   ↓
2. Script authenticates at runtime (gets temporary API key)
   ↓
3. Uses API key to fetch CSV data
   ↓
4. Persists data to database
```

**Advantages:**
- ✅ API key is temporary (not hardcoded)
- ✅ If credentials change, just update `settings.py`
- ✅ No need to manage static API keys
- ✅ Automatic re-authentication on each run

---

#### Setup Your Configuration

**Copy template to local config** (never committed to git):
```bash
cp src/config/settings.py.example src/config/settings.py
```

**Edit with your credentials:**
```python
DB_URL = "postgresql://USERNAME:PASSWORD@HOST:PORT/DATABASE"
PARKING_API_USERNAME = "FutureIOT_MOBI"
PARKING_API_PASSWORD = "your_password_here"
```

**Credentials are automatically used to:**
- Authenticate with Parking Pilot API
- Fetch temporary API key
- Download CSV data
- Store in database

---

### **⚙️ Step 2: Run Data Preparation (Local Machine - Fully Automated)**

The automated script handles everything - no manual setup needed!

**Windows Users:**
```batch
prepare_training_data.bat
```

**macOS/Linux Users:**
```bash
bash prepare_training_data.sh
```

**What the script does automatically:**
- ✅ Creates Python virtual environment (if not exist)
- ✅ Installs all dependencies from requirements.txt
- ✅ Executes all 8 data preparation steps sequentially:
  1. Fetch parking data from API
  2. Fetch weather data from API
  3. Create minute-level data (Lot 38)
  4. Aggregate to hourly (Lot 38)
  5. Create training dataset (Lot 38)
  6. Create minute-level data (Lot 634)
  7. Aggregate to hourly (Lot 634)
  8. Create training dataset (Lot 634)

**Runtime:** ~30-60 minutes depending on data size

---

### **✅ Step 3: Verify Success (Local Machine)**

Check if training data was created successfully:

**Windows (PowerShell):**
```powershell
psql -U parking_user -d parking -c "SELECT COUNT(*) FROM ali_training_data_hourly_availability_hourly_lot38;"
psql -U parking_user -d parking -c "SELECT COUNT(*) FROM ali_training_data_hourly_availability_hourly_lot634;"
```

**macOS/Linux:**
```bash
psql -U parking_user -d parking -c "SELECT COUNT(*) FROM ali_training_data_hourly_availability_hourly_lot38;"
psql -U parking_user -d parking -c "SELECT COUNT(*) FROM ali_training_data_hourly_availability_hourly_lot634;"
```

You should see row counts > 0.




---

### **⚡ Step 4: Train Models (Recommended: Google Colab)**

**Why Google Colab?**
- ✅ All ML libraries pre-installed (TensorFlow, scikit-learn, pandas, numpy, etc.)
- ✅ Free GPU/TPU access for faster model training
- ✅ No dependency management required
- ✅ Zero setup time - just upload and run

training notebooks are in training_pipeline\src\scripts\training_models_lot*.ipynb. Please open it in google colab. then upload the parquet files and run entire notbook 

**4.1 Two Options for Loading Training Data to Google Colab**

You have two approaches to get training data into Google Colab for model training:

#### **Option A: Upload Parquet Files (Recommended ⭐)**

**What are Parquet files?**
- Parquet is a columnar binary format (like compressed CSV but more efficient)
- Training data is pre-exported: `src/scripts/parking_data_lot38.parquet` and `parking_data_lot634.parquet`
- Files are already cleaned, aggregated, and feature-engineered

**Why use Parquet?**
- ✅ **Fast**: Binary format loads 10x faster than CSV
- ✅ **Efficient**: Compressed file size (~10-50 MB vs 100-500 MB CSV)
- ✅ **Self-contained**: Data completely prepared, no database needed in Colab
- ✅ **Offline**: Works without database credentials in Colab
- ✅ **Reproducible**: Exact same data used for all experiments





#### **Option B: Load Directly from PostgreSQL Database (Alternative)**

**When to use this?**
- You want to train on **fresh data** (not pre-exported files)
- You need **dynamic data updates** during training
- You want to **avoid file uploads** to Colab

**Steps: Connect to Database from Google Colab**

1. Install PostgreSQL driver:
   ```python
   !pip install psycopg2-binary sqlalchemy
   ```

2. Connect to your database and load data:
   ```python
   import pandas as pd
   from sqlalchemy import create_engine

   # Database connection string
   # Format: postgresql://username:password@host:port/database
   db_url = "postgresql://parking_user:your_password@your_host:5432/parking"
   
   # Create connection
   engine = create_engine(db_url)
   
   # Load training data directly from database
   df = pd.read_sql(
       "SELECT * FROM ali_training_data_hourly_availability_hourly_lot38;",
       engine
   )
   print(df.head())
   print(f"Shape: {df.shape}")
   ```

3. Use the data for model training (same as Parquet approach)

---

### **4.2 Download Trained Models from Google Colab**

After training completes in Google Colab:

1. **In Google Colab**, all trained models are saved in the `ml_models_production/` folder
   - `lot38_linear_regression_model.pkl`
   - `lot38_encoder_decoder_model.keras`
   - `lot38_hybrid_metadata.json`
   - `lot634_random_forest_model.pkl`
   - `lot634_gradient_boosting_model.pkl`
   - `lot634_hybrid_metadata.json`

2. **Download the entire `ml_models_production` folder** to your local machine (via Colab's file download interface or left sidebar)

---

### **4.3 Organize Trained Models Locally**

Move all downloaded models from the `ml_models_production` folder to the prediction pipeline predictor models folders.

**For Lot 38** (move files from downloaded ml_models_production folder):
```bash
# Create lot38 directory in prediction pipeline if not exists
mkdir -p prediction_pipeline/services/predictor/models/lot38

# Move Lot 38 models FROM ml_models_production TO predictor models/lot38
mv ml_models_production/lot38_linear_regression_model.pkl prediction_pipeline/services/predictor/models/lot38/linear_regression_model.pkl
mv ml_models_production/lot38_encoder_decoder_model.keras prediction_pipeline/services/predictor/models/lot38/encoder_decoder_model.keras
mv ml_models_production/lot38_hybrid_metadata.json prediction_pipeline/services/predictor/models/lot38/local_weighted_blend_hybrid_metadata.json

# Verify
ls -lh prediction_pipeline/services/predictor/models/lot38/
```

**For Lot 634** (move files from downloaded ml_models_production folder):
```bash
# Create lot634 directory in prediction pipeline if not exists
mkdir -p prediction_pipeline/services/predictor/models/lot634

# Move Lot 634 models FROM ml_models_production TO predictor models/lot634
mv ml_models_production/lot634_random_forest_model.pkl prediction_pipeline/services/predictor/models/lot634/random_forest_model.pkl
mv ml_models_production/lot634_gradient_boosting_model.pkl prediction_pipeline/services/predictor/models/lot634/gradient_boosting_model.pkl
mv ml_models_production/lot634_hybrid_metadata.json prediction_pipeline/services/predictor/models/lot634/local_weighted_blend_hybrid_metadata.json

# Verify
ls -lh prediction_pipeline/services/predictor/models/lot634/
```



**Tested & Verified:** These notebooks were developed and trained in Google Colab with all dependencies working seamlessly.

---

## 📁 Project Structure

```
training_pipeline/
├── README.md                                      ← You are here
├── requirements.txt                               ← Python dependencies
├── prepare_training_data.bat                      ← Data preparation (Windows)
├── prepare_training_data.sh                       ← Data preparation (Linux/Mac)
│
├── src/
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py                            ← LOCAL CONFIG (ignored in git)
│   │   └── settings.py.example                    ← TEMPLATE config
│   │
│   ├── raw_data_processing/
│   │   ├── __init__.py
│   │   │
│   │   ├── sql/                                   ← SQL scripts
│   │   │   ├── create_training_data_lot38.sql
│   │   │   ├── create_training_data_lot634.sql
│   │   │   ├── parking_availability_hourly_lot38.sql
│   │   │   ├── parking_availability_hourly_lot634.sql
│   │   │   ├── parking_availability_minute_lot38.sql
│   │   │   └── parking_availability_minute_lot634.sql
│   │   │
│   │   ├── create_training_data_lot38.py
│   │   ├── create_training_data_lot634.py
│   │   ├── ingest_parking_data.py
│   │   ├── ingest_weather_data.py
│   │   ├── parking_availability_hourly_lot38.py
│   │   ├── parking_availability_hourly_lot634.py
│   │   ├── parking_availability_minute_lot38.py
│   │   └── parking_availability_minute_lot634.py
│   │
│   ├── scripts/
│   │   ├── __init__.py
│   │   ├── parking_availability_analysis_lot38.ipynb
│   │   ├── parking_availability_analysis_lot634.ipynb
│   │   ├── parking_data_lot38.parquet
│   │   ├── parking_data_lot634.parquet
│   │   ├── training_models_lot38.ipynb
│   │   └── training_models_lot634.ipynb
│   │
│   └── utils/
│       ├── __init__.py
│       ├── parking_api_client.py                  ← API interaction
│       └── sql_executor.py                        ← Execute SQL scripts
│


```

---

## ✅ Setup Checklist 

**For Data Preparation:**
- [ ] Clone repository: `git clone <repo-url>`
- [ ] Navigate to training_pipeline: `cd training_pipeline`
- [ ] Copy config template: `cp src/config/settings.py.example src/config/settings.py`
- [ ] Edit `settings.py` with your database credentials
- [ ] Run automated preparation: `prepare_training_data.bat` (Windows) or `bash prepare_training_data.sh` (macOS/Linux)

**For Model Training:**
- [ ] Open Google Colab: https://colab.research.google.com
- [ ] Upload `src/scripts/training_models_lot38.ipynb`
- [ ] Upload `src/scripts/parking_data_lot38.parquet` into Google Colab
- [ ] Run all cells (no setup needed - packages pre-installed)
- [ ] **Download trained models from Colab** to your local machine:
  - `linear_regression_model.pkl`
  - `encoder_decoder_model.keras`
  - `hybrid_metadata.json`
- [ ] Organize files in `results/lot38/` folder locally
- [ ] Repeat steps for `training_models_lot634.ipynb` and organize in `results/lot634/`
- [ ] Verify: `ls -lh results/lot38/` and `ls -lh results/lot634/`

---

## 🧠 ML Models & Hybrid Approach

This project implements **horizon-aware hybrid forecasting models** that combine multiple algorithms for improved accuracy.

### Lot 38 (113 spaces)
- **Model A**: Linear Regression (baseline, fast, explainable)
- **Model B**: Encoder-Decoder Neural Network (deep learning, captures patterns)
- **Hybrid**: Alpha-blended predictions (per-horizon optimized)

### Lot 634 (64 spaces)
- **Model A**: Random Forest (ensemble, robust)
- **Model B**: Gradient Boosting (ensemble, powerful)
- **Hybrid**: Alpha-blended predictions (per-horizon optimized)

**Hybrid Blending Formula:**
```
y_hybrid[h] = α[h] × model_A[h] + (1 - α[h]) × model_B[h]

where α ∈ [0,1] is optimized separately for each prediction horizon h ∈ [1..24]
```

**Why Hybrid?**
- ✅ Combines strengths of different algorithms
- ✅ Lot-specific optimization (different blending weights per parking lot)
- ✅ Horizon-aware weighting (near-term vs. far-term predictions)
- ✅ Outperforms individual baseline models on test data

---

## 🛠️ Requirements

- Python 3.9+
- PostgreSQL 15 (local or remote)

See `requirements.txt` for Python packages.

---

## ❓ Troubleshooting

| Issue | Solution |
|-------|----------|
| `.bat` or `.sh` file won't run | Ensure you're in `training_pipeline/` directory, use `bash prepare_training_data.sh` on macOS/Linux |
| `Permission denied` on `.sh` file | Run `chmod +x prepare_training_data.sh` first |
| `settings.py` not found | Run `cp src/config/settings.py.example src/config/settings.py` |
| Database connection fails | Check credentials in `settings.py`, ensure PostgreSQL is running |
| Import errors (local Python) | Run `pip install -r requirements.txt` in activated venv |
| Models not training (local) | Try Google Colab instead - all packages pre-installed there |
| Parquet files not created | Check database connection, verify data rows exist in PostgreSQL |
| Google Colab module errors | All packages are pre-installed in Colab - if errors occur, try: `!pip install package_name` |

**Pro Tip:** If you encounter dependency issues locally, Google Colab is the recommended solution - it comes with all ML libraries pre-configured.


---

**Last Updated**: April 2026
