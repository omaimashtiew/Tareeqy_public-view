# tareeqy/ai_prediction/xgboost_predictor.py

import os
import sys
import json
from datetime import datetime, timedelta
import traceback

# --- Conditionally Import XGBoost ---
XGBOOST_AVAILABLE = False
xgb = None # Placeholder for xgboost module
try:
    import xgboost as xgb_module # Use a different alias during import
    xgb = xgb_module # Assign to the commonly used 'xgb' if successful
    XGBOOST_AVAILABLE = True
    print("XGBoost library loaded successfully in xgboost_predictor.py.")
except ImportError as e:
    print(f"WARNING (xgboost_predictor.py): XGBoost library not found: {e}. XGBoost-dependent features will be disabled.")
    # Do NOT sys.exit here. Allow the module to load so Django doesn't crash.

try:
    import joblib
    import pandas as pd
    import numpy as np
    from sklearn.preprocessing import LabelEncoder, StandardScaler # For type hints and structure
    from sklearn.cluster import KMeans # For type hints
except ImportError as e:
    print(f"CRITICAL ERROR (xgboost_predictor.py): Required AI/ML libraries (joblib, pandas, numpy, scikit-learn) not found: {e}")
    print("Please install them: pip install joblib pandas numpy scikit-learn")


# Project-specific imports
try:
    from . import config # Loads paths from config.py
except ImportError:
    import config # Fallback for cases where the script might be run in a way that . doesn't work


# --- Global State for Loaded Artifacts & Django Setup ---
PREDICTION_ARTIFACTS = {
    "model": None,
    "scaler": None,
    "kmeans": None,
    "le_status": None,
    "le_city": None,
    "le_day_part": None,
    "feature_columns": None,
    "loaded": False
}
_DJANGO_SETUP_COMPLETE = False


# --- Django Initialization Function ---
def setup_django():
    """Initializes the Django environment if not already done."""
    global _DJANGO_SETUP_COMPLETE
    if _DJANGO_SETUP_COMPLETE:
        return True

    print("Attempting to initialize Django for XGBoost predictor...")
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(script_dir))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
            print(f"(xgboost_predictor.py) Added project root to sys.path: {project_root}")

        os.environ.setdefault('DJANGO_SETTINGS_MODULE', config.DJANGO_SETTINGS_MODULE)
        import django
        django.setup()
        
        if not django.apps.apps.ready:
            raise RuntimeError("Django apps not ready after django.setup() call.")
        print("Django initialized successfully for XGBoost predictor.")
        _DJANGO_SETUP_COMPLETE = True
        return True
    except Exception as e:
        print(f"Error initializing Django for XGBoost predictor: {e}")
        print(f"Settings module used: '{os.environ.get('DJANGO_SETTINGS_MODULE')}'")
        traceback.print_exc()
        return False

# --- Artifact Loading Function ---
def load_prediction_artifacts(force_reload=False):
    """Loads all necessary artifacts for XGBoost wait time prediction."""
    if PREDICTION_ARTIFACTS["loaded"] and not force_reload:
        return True

    print("Loading XGBoost prediction artifacts...")
    try:
        required_files = {
            "model": config.MODEL_PATH, "scaler": config.SCALER_PATH,
            "kmeans": config.KMEANS_PATH, "le_status": config.LE_STATUS_PATH,
            "le_city": config.LE_CITY_PATH, "le_day_part": config.LE_DAY_PART_PATH,
            "feature_columns": config.FEATURE_COLUMNS_PATH
        }
        for key, path in required_files.items():
            if not os.path.exists(path):
                raise FileNotFoundError(f"Required artifact file for '{key}' not found at {path}")

        PREDICTION_ARTIFACTS["model"] = joblib.load(config.MODEL_PATH)
        PREDICTION_ARTIFACTS["scaler"] = joblib.load(config.SCALER_PATH)
        PREDICTION_ARTIFACTS["kmeans"] = joblib.load(config.KMEANS_PATH)
        PREDICTION_ARTIFACTS["le_status"] = joblib.load(config.LE_STATUS_PATH)
        PREDICTION_ARTIFACTS["le_city"] = joblib.load(config.LE_CITY_PATH)
        PREDICTION_ARTIFACTS["le_day_part"] = joblib.load(config.LE_DAY_PART_PATH)
        
        with open(config.FEATURE_COLUMNS_PATH, 'r') as f:
            PREDICTION_ARTIFACTS["feature_columns"] = json.load(f)

        PREDICTION_ARTIFACTS["loaded"] = True
        print("XGBoost prediction artifacts loaded successfully.")
        return True

    except FileNotFoundError as e:
        print(f"ERROR loading XGBoost artifacts: {e}")
        print("Please ensure the XGBoost model has been trained and all artifacts exist.")
        PREDICTION_ARTIFACTS["loaded"] = False
        return False
    except Exception as e:
        print(f"An unexpected error occurred loading XGBoost artifacts: {e}")
        traceback.print_exc()
        PREDICTION_ARTIFACTS["loaded"] = False
        return False


def _get_day_part(hour):
    if 0 <= hour < 6: return 'night'
    if 6 <= hour < 12: return 'morning'
    if 12 <= hour < 18: return 'afternoon'
    return 'evening'

def _is_rush_hour(hour):
    morning_start, morning_end = config.RUSH_HOURS_MORNING
    evening_start, evening_end = config.RUSH_HOURS_EVENING
    if (morning_start <= hour < morning_end) or \
       (evening_start <= hour < evening_end):
        return 1
    return 0

def _encode_feature(encoder, value, feature_name):
    try:
        if value not in encoder.classes_:
            print(f"Warning: Value '{value}' for '{feature_name}' not in LabelEncoder classes. Using default encoding.")
            return config.DEFAULT_UNKNOWN_ENCODED_VALUE
        return encoder.transform([value])[0]
    except Exception as e:
        print(f"Error encoding feature '{feature_name}' with value '{value}': {e}. Using default.")
        return config.DEFAULT_UNKNOWN_ENCODED_VALUE


# --- Main Prediction Function ---
def predict_wait_time(
    fence_id: int,
    current_time_utc: datetime,
    fence_latitude: float,
    fence_longitude: float,
    fence_city: str,
    current_status_str: str
):
    """
    Predicts the wait time for a given fence using the loaded XGBoost model.
    """
    if not XGBOOST_AVAILABLE:
        return {'success': False, 'error': 'XGBoost library not available. Prediction aborted.', 'predicted_wait_minutes': config.DEFAULT_PREDICTION_ERROR_WAIT_TIME}

    if not PREDICTION_ARTIFACTS["loaded"]:
        if not load_prediction_artifacts():
            return {'success': False, 'error': 'XGBoost: Failed to load prediction artifacts.'}

    model = PREDICTION_ARTIFACTS["model"]
    scaler = PREDICTION_ARTIFACTS["scaler"]
    kmeans = PREDICTION_ARTIFACTS["kmeans"]
    le_status = PREDICTION_ARTIFACTS["le_status"]
    le_city = PREDICTION_ARTIFACTS["le_city"]
    le_day_part = PREDICTION_ARTIFACTS["le_day_part"]
    feature_columns = PREDICTION_ARTIFACTS["feature_columns"]

    try:
        if current_status_str == config.STATUS_OPEN:
            return {
                'success': True,
                'predicted_wait_minutes': 0,
                'debug_info': 'Status is open.'
            }

        hour = current_time_utc.hour
        day_of_week = current_time_utc.weekday() 
        is_weekend = 1 if day_of_week >= 5 else 0 
        month = current_time_utc.month
        day_part_str = _get_day_part(hour)
        is_rush = _is_rush_hour(hour)

        f_lat = float(fence_latitude) if fence_latitude is not None else 0.0
        f_lon = float(fence_longitude) if fence_longitude is not None else 0.0
        
        geo_cluster = 0 
        if kmeans and hasattr(kmeans, 'predict'):
             try:
                # Pass DataFrame to KMeans predict to avoid feature name warnings, assuming KMeans was fit with names
                coords_df_for_kmeans = pd.DataFrame([[f_lat, f_lon]], columns=['latitude', 'longitude'])
                geo_cluster = kmeans.predict(coords_df_for_kmeans)[0]
             except Exception as e:
                print(f"Warning: KMeans prediction failed for [{f_lat}, {f_lon}]: {e}. Using geo_cluster=0.")
        
        status_encoded = _encode_feature(le_status, current_status_str, "status")
        city_encoded = _encode_feature(le_city, fence_city if fence_city else "unknown", "city")
        day_part_encoded = _encode_feature(le_day_part, day_part_str, "day_part")

        input_data = {col: 0 for col in feature_columns} 
        
        input_data.update({
            'fence_id': fence_id,
            'latitude': f_lat,
            'longitude': f_lon,
            'hour': hour,
            'day_of_week': day_of_week,
            'is_weekend': is_weekend,
            'month': month,
            'status_encoded': status_encoded,
            'city_encoded': city_encoded,
            'geo_cluster': int(geo_cluster),
            'is_rush_hour': is_rush,
            'day_part_encoded': day_part_encoded
        })
        
        for col in feature_columns:
            if col not in input_data:
                print(f"Warning: Feature '{col}' was missing from input_data construction. Defaulting to 0.")
                input_data[col] = 0 

        input_df = pd.DataFrame([input_data], columns=feature_columns)
        input_scaled = scaler.transform(input_df)
        predicted_wait_raw = model.predict(input_scaled)[0]
        
        predicted_wait_adjusted = float(predicted_wait_raw)

        if current_status_str == config.STATUS_CLOSED:
           predicted_wait_adjusted =int(predicted_wait_adjusted * 0.8)
       
        
        predicted_wait_final = int(round(predicted_wait_adjusted))

        return {
            'success': True,
            'predicted_wait_minutes': predicted_wait_final,
            'debug_info': f"Status: {current_status_str}, City: {fence_city}"
        }

    except Exception as e:
        print(f"ERROR in XGBoost predict_wait_time for fence_id {fence_id}: {e}")
        traceback.print_exc()
        return {
            'success': False,
            'error': f'XGBoost: Prediction error - {str(e)}',
            'predicted_wait_minutes': config.DEFAULT_PREDICTION_ERROR_WAIT_TIME 
        }

if __name__ == '__main__':
    print("Running XGBoost predictor standalone test...")
    if setup_django(): 
        if load_prediction_artifacts():
            print("\n--- Test Prediction ---")
            test_fence_id = 1
            test_current_time = datetime.utcnow() 
            test_lat = 31.9522
            test_lon = 35.2332
            test_city = "Jerusalem" 
            test_status = "sever_traffic_jam"

            print(f"Predicting for: Fence ID {test_fence_id}, Status '{test_status}', City '{test_city}' at {test_current_time}")
            
            result = predict_wait_time(
                fence_id=test_fence_id,
                current_time_utc=test_current_time,
                fence_latitude=test_lat,
                fence_longitude=test_lon,
                fence_city=test_city,
                current_status_str=test_status
            )
            print("\nPrediction Result:")
            print(json.dumps(result, indent=2))

            test_status_open = "open"
            print(f"\nPredicting for: Fence ID {test_fence_id}, Status '{test_status_open}', City '{test_city}' at {test_current_time}")
            result_open = predict_wait_time(
                fence_id=test_fence_id,
                current_time_utc=test_current_time,
                fence_latitude=test_lat,
                fence_longitude=test_lon,
                fence_city=test_city,
                current_status_str=test_status_open
            )
            print("\nPrediction Result (Open):")
            print(json.dumps(result_open, indent=2))
        else:
            print("CRITICAL: Could not load XGBoost artifacts. Test aborted.")
    else:
        print("CRITICAL: Django setup failed for XGBoost predictor. Test aborted.")