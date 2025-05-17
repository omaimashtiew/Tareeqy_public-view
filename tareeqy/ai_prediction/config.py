# tareeqy/ai_prediction/config.py
import os

# Directory where this config.py file is located
AI_PREDICTION_DIR = os.path.dirname(os.path.abspath(__file__))

# Sub-directory for storing/loading model artifacts
ARTIFACTS_DIR = os.path.join(AI_PREDICTION_DIR, 'artifacts')
os.makedirs(ARTIFACTS_DIR, exist_ok=True) # Ensure it exists

# --- Artifact Paths ---
# XGBoost Model and related components
MODEL_PATH = os.path.join(ARTIFACTS_DIR, 'xgboost_wait_time_model.pkl')
SCALER_PATH = os.path.join(ARTIFACTS_DIR, 'xgboost_scaler.pkl')
KMEANS_PATH = os.path.join(ARTIFACTS_DIR, 'xgboost_kmeans_model.pkl')

# Label Encoders
LE_STATUS_PATH = os.path.join(ARTIFACTS_DIR, 'xgboost_label_encoder_status.pkl')
LE_CITY_PATH = os.path.join(ARTIFACTS_DIR, 'xgboost_label_encoder_city.pkl')
LE_DAY_PART_PATH = os.path.join(ARTIFACTS_DIR, 'xgboost_label_encoder_day_part.pkl')

# Feature columns (expected by the model)
FEATURE_COLUMNS_PATH = os.path.join(ARTIFACTS_DIR, 'xgboost_feature_columns.json')


# --- Django Settings ---
# This should match your project's settings module
DJANGO_SETTINGS_MODULE = 'tareeqy_tracker.settings' # <<< CONFIRM THIS IS CORRECT FOR YOUR PROJECT
APP_NAME = 'tareeqy' # Your Django app name

# --- Prediction Defaults and Constants ---
DEFAULT_UNKNOWN_ENCODED_VALUE = 0 # Assuming 0 is the encoding for 'unknown' or default
RUSH_HOURS_MORNING = (7, 10) # e.g., 7 AM to 10 AM
RUSH_HOURS_EVENING = (14, 16) # e.g., 2 PM to 4 PM
DEFAULT_PREDICTION_ERROR_WAIT_TIME = 15 # Default wait time in minutes if prediction fails

# Status strings that might have special handling (must match training data)
STATUS_OPEN = 'open'
STATUS_SEVERE_TRAFFIC = 'sever_traffic_jam' # Ensure this matches exactly what's in your DB/training
STATUS_CLOSED = 'closed'