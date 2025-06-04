# tareeqy/ai_prediction/xgboost_predictor.py

import os
import sys
import json
from datetime import datetime, timedelta
import traceback
import warnings

# --- Use RandomForestRegressor ---
# import xgboost as xgb # REMOVE THIS
from sklearn.ensemble import RandomForestRegressor # ADD THIS
# --- END Change ---

# --- Required libraries ---
try:
    import joblib
    import pandas as pd
    import numpy as np
    from sklearn.preprocessing import LabelEncoder, StandardScaler
    from sklearn.cluster import KMeans
    # Check if RandomForestRegressor was successfully imported
    # if 'RandomForestRegressor' not in sys.modules:
       #   raise ImportError("RandomForestRegressor could not be imported from sklearn.ensemble.")
except ImportError as e:
    print(f"CRITICAL ERROR (xgboost_predictor.py): Missing required AI/ML libraries or RandomForestRegressor: {e}")
    print("Please install them: pip install joblib pandas numpy scikit-learn")
    # Exit if essential libraries are missing
    sys.exit(1)

# Project-specific imports
try:
    # Attempt relative import assuming this is part of a package
    from . import config as ai_config
    print("Loaded config via relative import.")
except ImportError:
    # Fallback if running script directly from its directory
    try:
        import config as ai_config
        print("Loaded config via direct import.")
    except ImportError:
        print("CRITICAL: Could not import ai_prediction.config. Ensure it exists and paths are correct.")
        # Define minimal defaults if config import fails for prediction
        class FallbackConfig:
            ARTIFACTS_DIR = 'ai_artifacts'
            MODEL_PATH = os.path.join(ARTIFACTS_DIR, 'wait_time_model.pkl') # Ensure this name matches train script
            SCALER_PATH = os.path.join(ARTIFACTS_DIR, 'scaler.pkl')
            KMEANS_PATH = os.path.join(ARTIFACTS_DIR, 'kmeans_model.pkl')
            LE_STATUS_PATH = os.path.join(ARTIFACTS_DIR, 'le_status.pkl')
            LE_CITY_PATH = os.path.join(ARTIFACTS_DIR, 'le_city.pkl')
            LE_DAY_PART_PATH = os.path.join(ARTIFACTS_DIR, 'le_day_part.pkl')
            FEATURE_COLUMNS_PATH = os.path.join(ARTIFACTS_DIR, 'feature_columns.json')
            # --- Define these constants mirroring the training script's updated logic ---
            RUSH_HOURS_MORNING = (7, 9)
            RUSH_HOURS_EVENING = (16, 18)
            STATUS_OPEN = 'open'
            STATUS_CLOSED = 'closed' # Keep for reference, but *0.8 logic removed
            DEFAULT_PREDICTION_ERROR_WAIT_TIME = 15
            DEFAULT_UNKNOWN_ENCODED_VALUE = 0 # Used for LabelEncoder fallback
            KMEANS_N_CLUSTERS = 3 # Just for reference if KMeans is re-trained on the fly

        ai_config = FallbackConfig()
        print("Using fallback configuration.")


# --- Global State for Loaded Artifacts ---
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

# --- Django Initialization Function ---
# Kept for completeness if ORM is used elsewhere, but not strictly needed for prediction itself
_DJANGO_SETUP_COMPLETE = False
def setup_django():
    global _DJANGO_SETUP_COMPLETE
    if _DJANGO_SETUP_COMPLETE: return True
    # print("Attempting to initialize Django for predictor...")
    try:
        # Adjusted path logic to be relative to the script's directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Assuming project root is two levels up (ai_prediction -> tareeqy_app_dir -> project_root)
        project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
            # print(f"(xgboost_predictor.py) Added project root to sys.path: {project_root}")

        # Ensure DJANGO_SETTINGS_MODULE is set, using config if available
        settings_module = getattr(ai_config, 'DJANGO_SETTINGS_MODULE', 'tareeqy.settings')
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)

        import django
        django.setup()
        if not django.apps.apps.ready:
            raise RuntimeError("Django apps not ready after django.setup() call.")
        # print("Django initialized successfully for predictor.")
        _DJANGO_SETUP_COMPLETE = True
        return True
    except Exception as e:
        print(f"Warning: Error initializing Django for predictor: {e}")
        print(f"Settings module used: '{os.environ.get('DJANGO_SETTINGS_MODULE')}'")
        # traceback.print_exc() # Avoid excessive traceback unless needed for debugging
        _DJANGO_SETUP_COMPLETE = False # Explicitly mark as not fully set up
        return False


# --- Artifact Loading Function ---
def load_prediction_artifacts(force_reload=False):
    """Loads all necessary artifacts for RandomForest wait time prediction.""" # Updated name
    if PREDICTION_ARTIFACTS["loaded"] and not force_reload:
        return True

    print("Loading RandomForest prediction artifacts...") # Updated name
    try:
        required_files = {
            "model": ai_config.MODEL_PATH, "scaler": ai_config.SCALER_PATH,
            "le_status": ai_config.LE_STATUS_PATH, "le_city": ai_config.LE_CITY_PATH,
            "le_day_part": ai_config.LE_DAY_PART_PATH, "feature_columns": ai_config.FEATURE_COLUMNS_PATH
        }
        # KMeans is optional, handled below
        
        for key, path in required_files.items():
            if not os.path.exists(path):
                raise FileNotFoundError(f"Required artifact file for '{key}' not found at {path}")

        PREDICTION_ARTIFACTS["model"] = joblib.load(ai_config.MODEL_PATH)
        PREDICTION_ARTIFACTS["scaler"] = joblib.load(ai_config.SCALER_PATH)
        PREDICTION_ARTIFACTS["le_status"] = joblib.load(ai_config.LE_STATUS_PATH)
        PREDICTION_ARTIFACTS["le_city"] = joblib.load(ai_config.LE_CITY_PATH)
        PREDICTION_ARTIFACTS["le_day_part"] = joblib.load(ai_config.LE_DAY_PART_PATH)
        
        with open(ai_config.FEATURE_COLUMNS_PATH, 'r') as f:
            PREDICTION_ARTIFACTS["feature_columns"] = json.load(f)

        # Load KMeans separately as it might be None if clustering wasn't possible
        if os.path.exists(ai_config.KMEANS_PATH):
            try:
                 kmeans_artifact = joblib.load(ai_config.KMEANS_PATH)
                 if isinstance(kmeans_artifact, KMeans):
                     PREDICTION_ARTIFACTS["kmeans"] = kmeans_artifact
                     print("KMeans model loaded.")
                 else:
                     # Handle case where file exists but contains None or wrong type
                     PREDICTION_ARTIFACTS["kmeans"] = None
                     print(f"KMeans artifact found at {ai_config.KMEANS_PATH} but is not a valid KMeans model. Skipping.")
            except Exception as e:
                 PREDICTION_ARTIFACTS["kmeans"] = None
                 print(f"Error loading KMeans model from {ai_config.KMEANS_PATH}: {e}. Skipping KMeans.")
        else:
            PREDICTION_ARTIFACTS["kmeans"] = None
            print(f"KMeans model not found at {ai_config.KMEANS_PATH}. Skipping KMeans.")


        # Basic validation
        if not isinstance(PREDICTION_ARTIFACTS["model"], RandomForestRegressor): # Updated check
             raise TypeError("Loaded model is not a RandomForestRegressor.")
        if not isinstance(PREDICTION_ARTIFACTS["scaler"], StandardScaler):
             raise TypeError("Loaded scaler is not a StandardScaler.")
        if not isinstance(PREDICTION_ARTIFACTS["le_status"], LabelEncoder) or \
           not isinstance(PREDICTION_ARTIFACTS["le_city"], LabelEncoder) or \
           not isinstance(PREDICTION_ARTIFACTS["le_day_part"], LabelEncoder):
             raise TypeError("One or more loaded LabelEncoders are invalid.")
        if not isinstance(PREDICTION_ARTIFACTS["feature_columns"], list) or not PREDICTION_ARTIFACTS["feature_columns"]:
             raise TypeError("Loaded feature columns list is invalid or empty.")

        PREDICTION_ARTIFACTS["loaded"] = True
        print("RandomForest prediction artifacts loaded successfully.") # Updated name
        return True

    except FileNotFoundError as e:
        print(f"ERROR loading RandomForest artifacts: {e}")
        print("Attempting to train model automatically...")

    # --- NEW: Auto-trigger training ---
    try:
        from tareeqy_tracker.tareeqy.ai_prediction import train_RF_model
        train_RF_model.main()
        print("Model trained. Retrying artifact load...")
        return load_prediction_artifacts(force_reload=True)  # Retry after training
    except Exception as train_err:
        print(f"Auto-training failed: {train_err}")
        PREDICTION_ARTIFACTS["loaded"] = False
        return False


# Helper functions mirroring preprocessing logic
def _get_day_part(hour):
    # Aligned with train_xgboost_model.py logic
    if 0 <= hour < 6: return 'night'
    if 6 <= hour < 12: return 'morning'
    if 12 <= hour < 18: return 'afternoon'
    return 'evening' # Includes hour 18 up to 23

def _is_rush_hour(hour):
    # Aligned with train_xgboost_model.py logic (using config values)
    morning_start = getattr(ai_config, 'RUSH_HOURS_MORNING', (7, 9))[0]
    morning_end = getattr(ai_config, 'RUSH_HOURS_MORNING', (7, 9))[1]
    evening_start = getattr(ai_config, 'RUSH_HOURS_EVENING', (16, 18))[0]
    evening_end = getattr(ai_config, 'RUSH_HOURS_EVENING', (16, 18))[1]

    if (morning_start <= hour < morning_end) or \
       (evening_start <= hour < evening_end):
        return 1
    return 0

def _encode_feature(encoder, value, feature_name):
    """Encodes a value using a LabelEncoder, handling unseen values gracefully."""
    try:
        # Ensure value is string to match training preprocessing
        value_str = str(value) if value is not None else 'unknown' # Handle None explicitly

        # Check if value is in known classes. Handle potential 'nan' string if NaNs were encoded.
        if value_str not in encoder.classes_ and 'nan' in encoder.classes_ and value is None:
             # If original training included NaNs as 'nan', try to encode None as 'nan'
             value_to_encode = 'nan'
        elif value_str not in encoder.classes_:
            # Fallback for genuinely unseen values or other NaNs
            default_val = getattr(ai_config, 'DEFAULT_UNKNOWN_ENCODED_VALUE', 0)
            # print(f"Warning: Value '{value_str}' for '{feature_name}' not in LabelEncoder classes {encoder.classes_}. Using default encoding ({default_val}).")
            # A more robust approach might be to add 'unknown' during training
            # or find the index of a known default like 'unknown' or the most frequent class.
            # For now, stick to original script's implicit fallback (likely 0 if not handled).
            # Or better, return the encoding of a known default class if it exists:
            if 'unknown' in encoder.classes_:
                 return encoder.transform(['unknown'])[0]
            # If 'unknown' isn't a class, just use the default 0 (might map to an actual class)
            return default_val # This is risky if 0 maps to a meaningful category

        else:
            value_to_encode = value_str

        # Check again in case value_to_encode was changed
        if value_to_encode not in encoder.classes_:
             default_val = getattr(ai_config, 'DEFAULT_UNKNOWN_ENCODED_VALUE', 0)
             print(f"Warning: Value '{value_to_encode}' for '{feature_name}' still not in encoder classes. Using default {default_val}.")
             if 'unknown' in encoder.classes_:
                 return encoder.transform(['unknown'])[0]
             return default_val

        return encoder.transform([value_to_encode])[0]

    except Exception as e:
        print(f"Error encoding feature '{feature_name}' with value '{value}': {e}. Using default 0.")
        # Fallback to default encoding if any error occurs during encoding
        if hasattr(encoder, 'classes_') and 'unknown' in encoder.classes_:
             return encoder.transform(['unknown'])[0]
        return getattr(ai_config, 'DEFAULT_UNKNOWN_ENCODED_VALUE', 0)


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
    Predicts the wait time for a given fence using the loaded RandomForest model. # Updated name
    """
    # Re-check library availability might not be strictly needed if sys.exit on import fail
    # if 'RandomForestRegressor' not in sys.modules:
    #     return {'success': False, 'error': 'RandomForestRegressor library not available. Prediction aborted.', 'predicted_wait_minutes': ai_config.DEFAULT_PREDICTION_ERROR_WAIT_TIME}

    if not PREDICTION_ARTIFACTS["loaded"]:
        # Attempt to load artifacts on demand if not already loaded
        if not load_prediction_artifacts():
            return {'success': False, 'error': 'RandomForest: Failed to load prediction artifacts.', 'predicted_wait_minutes': getattr(ai_config, 'DEFAULT_PREDICTION_ERROR_WAIT_TIME', 15)} # Updated name

    model = PREDICTION_ARTIFACTS["model"]
    scaler = PREDICTION_ARTIFACTS["scaler"]
    kmeans = PREDICTION_ARTIFACTS["kmeans"] # Can be None
    le_status = PREDICTION_ARTIFACTS["le_status"]
    le_city = PREDICTION_ARTIFACTS["le_city"]
    le_day_part = PREDICTION_ARTIFACTS["le_day_part"]
    feature_columns = PREDICTION_ARTIFACTS["feature_columns"] # The expected order of features

    try:
        status_open_key = getattr(ai_config, 'STATUS_OPEN', 'open')
        if current_status_str == status_open_key:
            return {
                'success': True,
                'predicted_wait_minutes': 0,
                'debug_info': 'Status is open.'
            }

        # Feature Engineering using current time - Aligned with train script
        hour = current_time_utc.hour
        day_of_week = current_time_utc.weekday() # Monday=0, Sunday=6
        # is_weekend: Sat/Sun ([5, 6]) - Aligned
        is_weekend = 1 if day_of_week in [5, 6] else 0 
        month = current_time_utc.month
        day_part_str = _get_day_part(hour)
        is_rush = _is_rush_hour(hour)

        # Handle potential NaNs in lat/lon for prediction - Aligned with preprocessing imputation
        # Although imputation was done during training, prediction might receive NaNs.
        # Use mean/median from training scaler if available? Scaler applies transformation.
        # For input feature creation, replace NaN lat/lon before scaling.
        # A simple approach is to use a default (like 0) or the mean from the training data if accessible.
        # The scaler was fit on potentially imputed data, so its mean_ and var_ might reflect that.
        # Accessing scaler.mean_[index of lat/lon] is an option, but requires knowing indices.
        # Simpler: use 0 or mean from scaler if available, matching the geo_cluster handling.
        
        f_lat = float(fence_latitude) if pd.notna(fence_latitude) else (scaler.mean_[feature_columns.index('latitude')] if scaler and hasattr(scaler, 'mean_') and 'latitude' in feature_columns else 0.0)
        f_lon = float(fence_longitude) if pd.notna(fence_longitude) else (scaler.mean_[feature_columns.index('longitude')] if scaler and hasattr(scaler, 'mean_') and 'longitude' in feature_columns else 0.0)
        fence_city_processed = fence_city if pd.notna(fence_city) and fence_city is not None else 'unknown' # Handle None and NaN

        # Calculate geo_cluster using loaded KMeans or default if KMeans is None
        geo_cluster = 0
        if kmeans and hasattr(kmeans, 'predict'):
             try:
                # KMeans was fit on a NumPy array in training, use NumPy array for predict
                geo_cluster = kmeans.predict(pd.DataFrame([[f_lat, f_lon]], columns=["latitude", "longitude"]))[0]
             except Exception as e:
                print(f"Warning: KMeans prediction failed for [{f_lat}, {f_lon}]: {e}. Using geo_cluster=0.")
                # traceback.print_exc() # Optional: print full traceback for KMeans error
        
        # Encode categorical features using loaded encoders - Use helper with error handling
        status_encoded = _encode_feature(le_status, current_status_str, "status")
        city_encoded = _encode_feature(le_city, fence_city_processed, "city")
        day_part_encoded = _encode_feature(le_day_part, day_part_str, "day_part")

        # Create feature vector (DataFrame) matching the columns and order from training
        input_data = {
            'fence_id': fence_id,
            'latitude': f_lat,
            'longitude': f_lon,
            'hour': hour,
            'day_of_week': day_of_week,
            'is_weekend': is_weekend,
            'month': month,
            'status_encoded': status_encoded,
            'city_encoded': city_encoded,
            'geo_cluster': int(geo_cluster), # Ensure integer type
            'is_rush_hour': is_rush,
            'day_part_encoded': day_part_encoded
        }
        
        # Create DataFrame ensuring column order matches feature_columns
        try:
            input_df = pd.DataFrame([input_data], columns=feature_columns)
        except ValueError as e:
            print(f"Error creating input DataFrame. Feature columns mismatch? Expected: {feature_columns}, Got: {input_data.keys()}. Error: {e}")
            return {'success': False, 'error': f'Feature mismatch error: {e}', 'predicted_wait_minutes': getattr(ai_config, 'DEFAULT_PREDICTION_ERROR_WAIT_TIME', 15)}


        # Scale features
        input_scaled = scaler.transform(input_df)
        
        # Predict
        predicted_wait_raw = model.predict(input_scaled)[0]
        
        # Round to the nearest minute and ensure non-negative
        predicted_wait_final = int(round(max(0, predicted_wait_raw)))

        # No adjustment for 'closed' status, replicating XGBoost_Complete.py logic
        # if current_status_str == ai_config.STATUS_CLOSED:
        #    predicted_wait_adjusted =int(predicted_wait_adjusted * 0.8) # REMOVE THIS

        return {
            'success': True,
            'predicted_wait_minutes': predicted_wait_final,
            # Include debug info if helpful, match structure expected by JS
            # 'prediction_debug_info': f"Status: {current_status_str}, City: {fence_city_processed}, Hour: {hour}, DOW: {day_of_week}, GeoCluster: {int(geo_cluster)}"
        }

    except Exception as e:
        print(f"ERROR in RandomForest predict_wait_time for fence_id {fence_id}: {e}") # Updated name
        traceback.print_exc()
        return {
            'success': False,
            'error': f'Prediction error: {str(e)}', # Generic error message
            'predicted_wait_minutes': getattr(ai_config, 'DEFAULT_PREDICTION_ERROR_WAIT_TIME', 15) # Default wait time on error
        }

if __name__ == '__main__':
    print("Running RandomForest predictor standalone test...") # Updated name
    warnings.filterwarnings("ignore", category=UserWarning, module="sklearn.cluster._kmeans") # Suppress KMeans warnings

    # Ensure Django setup if needed for config loading or other reasons
    # setup_django() # Uncomment if your config relies on Django settings

    if load_prediction_artifacts():
        print("\n--- Test Prediction ---")
        # Use realistic test data
        test_fence_id = 1 # Example fence ID
        # Example historical time or current time
        # test_current_time = datetime(2023, 10, 27, 17, 30, 0) # Example: Friday 5:30 PM (likely rush hour, not weekend)
        test_current_time = datetime.utcnow() # Use current UTC time

        # Example fence data - use actual values if possible
        test_lat = 31.9632 # Example latitude
        test_lon = 35.9306 # Example longitude
        test_city = "Amman" # Example city
        
        # Test different statuses
        test_statuses = [
            "open",
            "slow",
            "heavy_traffic_jam",
            "sever_traffic_jam",
            "closed",
            "unknown_status" # Test unseen status handling
        ]

        for test_status in test_statuses:
            print(f"\nPredicting for: Fence ID {test_fence_id}, Status '{test_status}', City '{test_city}' at {test_current_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            result = predict_wait_time(
                fence_id=test_fence_id,
                current_time_utc=test_current_time,
                fence_latitude=test_lat,
                fence_longitude=test_lon,
                fence_city=test_city,
                current_status_str=test_status
            )
            print("Prediction Result:")
            # Print the dictionary directly or using json.dumps for readability
            # print(result)
            print(json.dumps(result, indent=2))

    else:
        print("CRITICAL: Could not load RandomForest artifacts. Test aborted.") # Updated name