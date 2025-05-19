# tareeqy/ai_prediction/train_xgboost_model.py

import os
import sys
import time
import json # For saving feature columns
import warnings

# --- Django Setup (Optional but good practice if using Django ORM) ---
_DJANGO_SETUP_COMPLETE = False

def initialize_django():
    global _DJANGO_SETUP_COMPLETE
    if _DJANGO_SETUP_COMPLETE: return True
    print("Attempting to initialize Django for training script...")
    try:
        # Assuming this script is in tareeqy/ai_prediction/
        script_path = os.path.dirname(os.path.abspath(__file__))
        # Project root is two levels up (ai_prediction -> tareeqy_app_dir -> project_root)
        project_root = os.path.abspath(os.path.join(script_path, '..', '..'))

        if project_root not in sys.path:
            sys.path.insert(0, project_root)
            print(f"Added project root to sys.path: {project_root}")

        # Import config here AFTER path setup to ensure it's found
        from tareeqy.ai_prediction import config as ai_config

        os.environ.setdefault('DJANGO_SETTINGS_MODULE', ai_config.DJANGO_SETTINGS_MODULE)
        import django
        django.setup()
        if not django.apps.apps.ready: raise RuntimeError("Django apps not ready after setup.")
        print("Django initialized successfully for training script.")
        _DJANGO_SETUP_COMPLETE = True
        return True
    except Exception as e:
        print(f"Warning: Error initializing Django: {e}")
        print(f"DJANGO_SETTINGS_MODULE: {os.environ.get('DJANGO_SETTINGS_MODULE')}")
        print("Proceeding without full Django setup. If Django ORM is used, this might fail.")
        _DJANGO_SETUP_COMPLETE = False # Explicitly mark as not fully set up
        return False

# Call Django Initialization if needed, or proceed if direct DB connection is primary
# initialize_django() # Uncomment if you switch to Django ORM for data fetching

# --- Library Imports ---
try:
    import mysql.connector
    import pandas as pd
    import numpy as np
    from datetime import datetime
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import LabelEncoder, StandardScaler
    from sklearn.cluster import KMeans
    from sklearn.metrics import mean_absolute_error, median_absolute_error, r2_score
    import xgboost as xgb
    import joblib
except ImportError as e:
    print(f"CRITICAL: Missing required libraries: {e}. Please install them.")
    sys.exit(1)

# --- Configuration Import ---
# This assumes config.py is in the same directory (tareeqy/ai_prediction/)
try:
    from . import config as ai_config
except ImportError:
    try:
        import config as ai_config # Fallback if run directly from ai_prediction folder
    except ImportError:
        print("CRITICAL: Could not import ai_prediction.config. Ensure it exists and paths are correct.")
        sys.exit(1)


# --- Database Connection ---
def get_db_connection(max_retries=3):
    # Ensure environment variables are loaded if using them for DB credentials
    # For example: os.getenv('DB_HOST'), os.getenv('DB_USER'), etc.
    # The provided script has hardcoded credentials - consider using env vars.
    for attempt in range(max_retries):
        try:
            conn = mysql.connector.connect(
                host="yamabiko.proxy.rlwy.net", # Consider using env variables
                port=26213,
                user="root",
                password="sbKIFwBCaymbcggetPSaFpblUvThYNSX",
                database="railway",
                charset='utf8mb4',
                connect_timeout=10 # Increased timeout
            )
            return conn
        except Exception as e:
            print(f"DB Connection attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise e
            time.sleep(2)

# --- Data Fetching with Cache ---
DATA_CACHE_FILE = os.path.join(ai_config.ARTIFACTS_DIR, 'training_data_cache.pkl')

def fetch_data(use_cache=True):
    if use_cache and os.path.exists(DATA_CACHE_FILE):
        try:
            print(f"Loading data from cache: {DATA_CACHE_FILE}")
            df_cache = joblib.load(DATA_CACHE_FILE)
            # Validate cache structure if necessary
            if 'fences' in df_cache and 'status' in df_cache:
                return df_cache['fences'], df_cache['status']
            else:
                print("Cache is invalid. Fetching fresh data.")
        except Exception as e:
            print(f"Error loading cache: {e}. Fetching fresh data.")

    print("Fetching data from database...")
    conn = get_db_connection()
    try:
        # Use table names from your Django models if they differ
        # e.g., f"{ai_config.APP_NAME}_fence"
        fences_df = pd.read_sql(f"SELECT id, name, latitude, longitude, city FROM {ai_config.APP_NAME}_fence", conn)
        status_df = pd.read_sql(f"""
            SELECT fs.id, fs.fence_id, fs.status, fs.message_time 
            FROM {ai_config.APP_NAME}_fencestatus fs
            WHERE fs.message_time >= NOW() - INTERVAL 6 MONTH
        """, conn) # Consider parameterizing interval

        print(f"Fetched {len(fences_df)} fences and {len(status_df)} status records.")
        os.makedirs(ai_config.ARTIFACTS_DIR, exist_ok=True)
        joblib.dump({'fences': fences_df, 'status': status_df}, DATA_CACHE_FILE)
        print(f"Data cached to {DATA_CACHE_FILE}")
        return fences_df, status_df
    finally:
        if conn and conn.is_connected():
            conn.close()

# --- Geo Features ---
def calculate_geo_features(fences_df):
    print("Calculating geo features...")
    fences_df['geo_cluster'] = 0 # Default
    coords = fences_df[['latitude', 'longitude']].dropna()

    if len(coords) >= 3: # Need at least k_clusters points
        # Simple approach: fixed number of clusters, or basic elbow method
        optimal_k = min(10, len(coords)) # Max 3 clusters or fewer if not enough unique points
        
        # Check for sufficient unique coordinate pairs for KMeans
        if coords.drop_duplicates().shape[0] < optimal_k:
            optimal_k = coords.drop_duplicates().shape[0]
            if optimal_k == 0: # No valid coords
                 print("Warning: No valid coordinates for KMeans clustering.")
                 joblib.dump(None, ai_config.KMEANS_PATH) # Save None if no model
                 return fences_df
            print(f"Reduced KMeans clusters to {optimal_k} due to limited unique coordinates.")


        if optimal_k > 0: # Proceed if we can form at least one cluster
            kmeans = KMeans(n_clusters=optimal_k, random_state=42, n_init='auto')
            # Fit on non-NA coordinates and assign back
            valid_coords_mask = fences_df[['latitude', 'longitude']].notna().all(axis=1)
            if valid_coords_mask.sum() >= optimal_k:
                fences_df.loc[valid_coords_mask, 'geo_cluster'] = kmeans.fit_predict(fences_df.loc[valid_coords_mask, ['latitude', 'longitude']])
                joblib.dump(kmeans, ai_config.KMEANS_PATH)
                print(f"KMeans model saved to {ai_config.KMEANS_PATH}")
            else:
                print(f"Warning: Not enough valid data points ({valid_coords_mask.sum()}) for KMeans with k={optimal_k}. Skipping geo_cluster.")
                joblib.dump(None, ai_config.KMEANS_PATH) # Save None if no model
        else:
            print("Warning: Not enough unique coordinates for KMeans. Skipping geo_cluster.")
            joblib.dump(None, ai_config.KMEANS_PATH) # Save None if no model

    else:
        print("Warning: Not enough data points for KMeans clustering. Skipping geo_cluster.")
        joblib.dump(None, ai_config.KMEANS_PATH) # Save None if no model
    return fences_df

# --- Preprocessing ---
def preprocess_data(fences_df, status_df):
    print("Preprocessing data...")
    # Handle NaNs in fences_df
    fences_df['city'].fillna('unknown', inplace=True)
    # Impute lat/lon based on city median, then global mean
    for city_val in fences_df['city'].unique():
        city_mask = fences_df['city'] == city_val
        lat_median = fences_df.loc[city_mask, 'latitude'].median()
        lon_median = fences_df.loc[city_mask, 'longitude'].median()
        fences_df.loc[city_mask & fences_df['latitude'].isna(), 'latitude'] = lat_median
        fences_df.loc[city_mask & fences_df['longitude'].isna(), 'longitude'] = lon_median
    fences_df['latitude'].fillna(fences_df['latitude'].mean(), inplace=True)
    fences_df['longitude'].fillna(fences_df['longitude'].mean(), inplace=True)

    fences_df = calculate_geo_features(fences_df)

    df = pd.merge(status_df, fences_df, left_on='fence_id', right_on='id', how='left', suffixes=('_status', '_fence'))
    df.drop(columns=['id_fence'], inplace=True, errors='ignore') # Drop redundant ID

    df['message_time'] = pd.to_datetime(df['message_time'])
    df['hour'] = df['message_time'].dt.hour
    df['day_of_week'] = df['message_time'].dt.dayofweek
    df['is_weekend'] = df['day_of_week'].isin([4, 5]).astype(int) # Assuming Fri/Sat weekend
    df['month'] = df['message_time'].dt.month
    
    df['is_rush_hour'] = df['hour'].apply(
        lambda x: 1 if (ai_config.RUSH_HOURS_MORNING[0] <= x < ai_config.RUSH_HOURS_MORNING[1]) or \
                         (ai_config.RUSH_HOURS_EVENING[0] <= x < ai_config.RUSH_HOURS_EVENING[1]) else 0
    )
    df['day_part'] = pd.cut(df['hour'],
                            bins=[0, 6, 12, 18, 24], # Adjusted bins for 0-23 hours
                            labels=['night', 'morning', 'afternoon', 'evening'], right=True)
    
    # Label Encoders
    le_status = LabelEncoder()
    le_city = LabelEncoder()
    le_day_part = LabelEncoder()

    # Fit and transform, then save encoders
    df['status_encoded'] = le_status.fit_transform(df['status'].astype(str)) # Ensure string type
    joblib.dump(le_status, ai_config.LE_STATUS_PATH)
    print(f"LabelEncoder for status saved to {ai_config.LE_STATUS_PATH}")

    df['city_encoded'] = le_city.fit_transform(df['city'].astype(str)) # Ensure string type
    joblib.dump(le_city, ai_config.LE_CITY_PATH)
    print(f"LabelEncoder for city saved to {ai_config.LE_CITY_PATH}")

    df['day_part_encoded'] = le_day_part.fit_transform(df['day_part'].astype(str)) # Ensure string type
    joblib.dump(le_day_part, ai_config.LE_DAY_PART_PATH)
    print(f"LabelEncoder for day_part saved to {ai_config.LE_DAY_PART_PATH}")

    # Calculate wait_time (target variable)
    # This is a crucial step, ensure it aligns with how wait time is defined
    df = df.sort_values(by=['fence_id', 'message_time'])
    df['time_diff_seconds'] = df.groupby('fence_id')['message_time'].diff().dt.total_seconds()
    # Heuristic for wait time: use time diffs only for 'sever_traffic_jam' or 'closed' leading to it.
    # This is complex; the original script uses a median of positive diffs.
    # For simplicity and robustness, let's refine the original approach.
    
    def calculate_median_positive_diff(series):
        positive_diffs = series[series > 0]
        return positive_diffs.median() if not positive_diffs.empty else np.nan

    # Group by more granular features to get representative wait times
    wait_time_groups = ['fence_id', 'status', 'hour', 'day_of_week']
    df['wait_time_calc'] = df.groupby(wait_time_groups)['time_diff_seconds'].transform(calculate_median_positive_diff) / 60 # in minutes

    # Fill NaNs in wait_time_calc:
    # 1. Median wait_time for the same fence_id and status
    df['wait_time_calc'] = df['wait_time_calc'].fillna(df.groupby(['fence_id', 'status'])['wait_time_calc'].transform('median'))
    # 2. Median wait_time for the same status globally
    df['wait_time_calc'] = df['wait_time_calc'].fillna(df.groupby('status')['wait_time_calc'].transform('median'))
    # 3. Global median (or a default like 10 minutes)
    df['wait_time_calc'].fillna(df['wait_time_calc'].median(), inplace=True)
    df['wait_time_calc'].fillna(10, inplace=True) # Final fallback

    df['wait_time'] = df['wait_time_calc'].clip(lower=1, upper=120) # Clip to reasonable bounds

    # Drop intermediate columns
    df.drop(columns=['time_diff_seconds', 'wait_time_calc'], inplace=True, errors='ignore')
    
    # Drop rows where crucial features for training might still be NaN after merge/processing
    # (e.g., if a status record links to a fence_id not in fences_df)
    df.dropna(subset=['latitude', 'longitude', 'city_encoded', 'geo_cluster'], inplace=True)


    return df

# --- Prepare Training Data & Save Artifacts ---
def prepare_training_data_and_save_artifacts(df):
    print("Preparing training data and saving artifacts...")
    # Define feature columns based on what's available after preprocessing
    # Must match the order and names expected by the predictor
    feature_cols = [
        'fence_id', 'latitude', 'longitude', 'hour', 'day_of_week',
        'is_weekend', 'month', 'status_encoded', 'city_encoded',
        'geo_cluster', 'is_rush_hour', 'day_part_encoded'
    ]
    
    # Ensure all feature columns exist in df
    missing_cols = [col for col in feature_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing feature columns in DataFrame: {missing_cols}")

    X = df[feature_cols]
    y = df['wait_time']

    # Save feature columns list
    with open(ai_config.FEATURE_COLUMNS_PATH, 'w') as f:
        json.dump(feature_cols, f)
    print(f"Feature columns list saved to {ai_config.FEATURE_COLUMNS_PATH}")

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    joblib.dump(scaler, ai_config.SCALER_PATH)
    print(f"Scaler saved to {ai_config.SCALER_PATH}")
    
    return X_scaled, y

# --- Train Model ---
def train_and_save_model(X, y):
    print("Training XGBoost model...")
    if X.shape[0] == 0 or y.shape[0] == 0:
        print("Error: No data available for training. Aborting model training.")
        return None
        
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    if X_train.shape[0] < 5 or X_test.shape[0] < 1 : # Arbitrary small number check
        print(f"Warning: Very small dataset for training/testing. Train: {X_train.shape[0]}, Test: {X_test.shape[0]}")
        print("Model performance might be unreliable. Consider gathering more data.")
        if X_train.shape[0] == 0:
             print("Error: Training set is empty. Aborting model training.")
             return None


    model = xgb.XGBRegressor(
        objective='reg:squarederror',
        n_estimators=250, # Reduced for faster training, adjust as needed
        learning_rate=0.03,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
        # early_stopping_rounds=10 # Consider adding if you have a validation set in fit
    )

    # model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False) # If using early stopping
    model.fit(X_train, y_train)
    print("Model training complete.")

    # Evaluate
    if X_test.shape[0] > 0:
        y_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        medae = median_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        print(f"  Test MAE: {mae:.2f} minutes")
        print(f"  Test MedianAE: {medae:.2f} minutes")
        print(f"  Test R2 Score: {r2:.2f}")
    else:
        print("  Skipping evaluation as test set is empty.")


    joblib.dump(model, ai_config.MODEL_PATH)
    print(f"XGBoost model saved to {ai_config.MODEL_PATH}")
    return model

# --- Main Execution ---
def main():
    print("--- Starting XGBoost Model Training Process ---")
    # Ensure artifacts directory exists
    os.makedirs(ai_config.ARTIFACTS_DIR, exist_ok=True)

    fences_df, status_df = fetch_data(use_cache=True) # Set use_cache=False to force DB fetch

    if fences_df.empty or status_df.empty:
        print("Error: No data fetched from database. Aborting.")
        return

    processed_df = preprocess_data(fences_df, status_df)

    if processed_df.empty:
        print("Error: Data is empty after preprocessing. Aborting.")
        return
    
    print(f"Shape of processed_df before preparing training data: {processed_df.shape}")
    print(f"Wait time stats: Min={processed_df['wait_time'].min()}, Max={processed_df['wait_time'].max()}, Mean={processed_df['wait_time'].mean()}")


    X_scaled, y = prepare_training_data_and_save_artifacts(processed_df)
    
    if X_scaled is None or y is None or X_scaled.shape[0] == 0:
        print("Error: Training data preparation failed or resulted in empty data. Aborting.")
        return

    model = train_and_save_model(X_scaled, y)

    if model:
        print("--- XGBoost Model Training Process Finished Successfully ---")
        # Optional: Run a quick test prediction here if desired
        # (requires loading all artifacts similar to xgboost_predictor.py)
    else:
        print("--- XGBoost Model Training Process Failed ---")

if __name__ == "__main__":
    # Suppress specific warnings if they are noisy and understood
    warnings.filterwarnings("ignore", category=UserWarning, module="sklearn.cluster._kmeans")
    main()