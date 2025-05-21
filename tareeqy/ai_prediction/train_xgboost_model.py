# tareeqy/ai_prediction/train_xgboost_model.py

import os
import sys
import time
import json
import warnings
import pandas as pd
import numpy as np
from datetime import datetime
import mysql.connector # Keep direct connection as in original script
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.cluster import KMeans
# --- Change from xgboost to RandomForest ---
# import xgboost as xgb # REMOVE THIS
from sklearn.ensemble import RandomForestRegressor # ADD THIS
# --- END Change ---
from sklearn.metrics import mean_absolute_error, median_absolute_error, r2_score
import joblib

# --- Configuration Import ---
# This assumes config.py is in the same directory (tareeqy/ai_prediction/)
# or is findable via sys.path if Django setup is used later.
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
        # Define minimal defaults if config import fails to allow script to proceed partially
        class FallbackConfig:
            ARTIFACTS_DIR = 'ai_artifacts'
            MODEL_PATH = os.path.join(ARTIFACTS_DIR, 'wait_time_model.pkl')
            SCALER_PATH = os.path.join(ARTIFACTS_DIR, 'scaler.pkl')
            KMEANS_PATH = os.path.join(ARTIFACTS_DIR, 'kmeans_model.pkl')
            LE_STATUS_PATH = os.path.join(ARTIFACTS_DIR, 'le_status.pkl')
            LE_CITY_PATH = os.path.join(ARTIFACTS_DIR, 'le_city.pkl')
            LE_DAY_PART_PATH = os.path.join(ARTIFACTS_DIR, 'le_day_part.pkl')
            FEATURE_COLUMNS_PATH = os.path.join(ARTIFACTS_DIR, 'feature_columns.json')
            # --- Define these constants mirroring XGBoost_Complete.py logic ---
            RUSH_HOURS_MORNING = (7, 9)
            RUSH_HOURS_EVENING = (16, 18)
            WAIT_TIME_DEFAULT_FILL = 10
            WAIT_TIME_CLIP_LOWER = 5
            WAIT_TIME_CLIP_UPPER = 120
            KMEANS_N_CLUSTERS = 3 # Target k from XGBoost_Complete.py
            # Assume default Django app name if config missing
            APP_NAME = 'tareeqy' # Placeholder - MUST be correct for DB queries

        ai_config = FallbackConfig()
        print("Using fallback configuration.")


# --- Database Connection ---
# Using hardcoded values from the original script for consistency
DB_CONFIG = {
    "host": "yamabiko.proxy.rlwy.net",
    "port": 26213,
    "user": "root",
    "password": "sbKIFwBCaymbcggetPSaFpblUvThYNSX",
    "database": "railway",
    "charset": 'utf8mb4',
    "connect_timeout": 10
}

def get_db_connection(max_retries=3):
    for attempt in range(max_retries):
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
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
            if isinstance(df_cache, dict) and 'fences' in df_cache and 'status' in df_cache:
                print("Cache data loaded successfully.")
                return df_cache['fences'], df_cache['status']
            else:
                print("Cache structure invalid. Fetching fresh data.")
        except Exception as e:
            print(f"Error loading cache: {e}. Fetching fresh data.")

    print("Fetching data from database...")
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
             print("Failed to get DB connection.")
             return pd.DataFrame(), pd.DataFrame() # Return empty dataframes on failure

        # Use table names consistent with XGBoost_Complete.py and potential config
        # Assuming ai_config.APP_NAME is defined and correct, otherwise use tareeqy
        app_name = getattr(ai_config, 'APP_NAME', 'tareeqy')

        fences_df = pd.read_sql(f"SELECT id, name, latitude, longitude, city FROM {app_name}_fence", conn)
        status_df = pd.read_sql(f"""
            SELECT fs.id, fs.fence_id, fs.status, fs.message_time 
            FROM {app_name}_fencestatus fs
            WHERE fs.message_time >= NOW() - INTERVAL 6 MONTH
        """, conn) # Consider parameterizing interval

        print(f"Fetched {len(fences_df)} fences and {len(status_df)} status records.")
        os.makedirs(ai_config.ARTIFACTS_DIR, exist_ok=True)
        joblib.dump({'fences': fences_df, 'status': status_df}, DATA_CACHE_FILE)
        print(f"Data cached to {DATA_CACHE_FILE}")
        return fences_df, status_df
    except Exception as e:
        print(f"Error fetching data from DB: {e}")
        return pd.DataFrame(), pd.DataFrame() # Return empty dataframes on failure
    finally:
        if conn and conn.is_connected():
            conn.close()

# --- Geo Features ---
def calculate_geo_features(fences_df):
    print("Calculating geo features...")
    fences_df['geo_cluster'] = 0 # Default value
    coords = fences_df[['latitude', 'longitude']].dropna()

    # Target k=3 clusters as in XGBoost_Complete.py, but adjust if insufficient data
    target_k = getattr(ai_config, 'KMEANS_N_CLUSTERS', 3)
    
    if len(coords) >= target_k:
        try:
            # Check for sufficient unique coordinate pairs for KMeans
            if coords.drop_duplicates().shape[0] < target_k:
                optimal_k = coords.drop_duplicates().shape[0]
                if optimal_k == 0: # No valid unique coords
                    print("Warning: No valid unique coordinates for KMeans clustering. Skipping geo_cluster.")
                    joblib.dump(None, ai_config.KMEANS_PATH) # Save None if no model
                    return fences_df
                print(f"Reduced KMeans clusters to {optimal_k} due to limited unique coordinates.")
            else:
                optimal_k = target_k

            if optimal_k > 0:
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
                 print("Warning: Optimal k is 0. Skipping geo_cluster.")
                 joblib.dump(None, ai_config.KMEANS_PATH) # Save None if no model

        except Exception as e:
             print(f"Error during KMeans clustering: {e}. Skipping geo_cluster calculation and saving.")
             joblib.dump(None, ai_config.KMEANS_PATH) # Save None on error

    else:
        print("Warning: Not enough data points for KMeans clustering with k={target_k}. Skipping geo_cluster.")
        joblib.dump(None, ai_config.KMEANS_PATH) # Save None if no model

    return fences_df

# --- Preprocessing ---
def preprocess_data(fences_df, status_df):
    print("Preprocessing data...")
    
    # Handle NaNs in fences_df (city, lat/lon imputation) - Aligned with XGBoost_Complete.py
    fences_df['city'].fillna('unknown', inplace=True)
    unique_cities = fences_df['city'].unique()
    for city_val in unique_cities:
        city_mask = fences_df['city'] == city_val
        lat_median = fences_df.loc[city_mask, 'latitude'].median()
        lon_median = fences_df.loc[city_mask, 'longitude'].median()
        if not pd.isna(lat_median):
             fences_df.loc[city_mask & fences_df['latitude'].isna(), 'latitude'] = lat_median
        if not pd.isna(lon_median):
             fences_df.loc[city_mask & fences_df['longitude'].isna(), 'longitude'] = lon_median
    fences_df['latitude'].fillna(fences_df['latitude'].dropna().mean(), inplace=True)
    fences_df['longitude'].fillna(fences_df['longitude'].dropna().mean(), inplace=True)

    # Calculate geo features AFTER lat/lon imputation
    fences_df = calculate_geo_features(fences_df)

    # Merge dataframes
    df = pd.merge(status_df, fences_df, left_on='fence_id', right_on='id', how='left', suffixes=('_status', '_fence'))
    df.drop(columns=['id_fence'], inplace=True, errors='ignore')

    # Convert time column
    df['message_time'] = pd.to_datetime(df['message_time'])

    # Time features - Aligned with XGBoost_Complete.py logic
    df['hour'] = df['message_time'].dt.hour
    df['day_of_week'] = df['message_time'].dt.dayofweek
    # is_weekend: Sat/Sun ([5, 6]) as in XGBoost_Complete.py
    df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int) 
    df['month'] = df['message_time'].dt.month
    
    # is_rush_hour: 7-9 and 16-18 as in XGBoost_Complete.py
    morning_rush = getattr(ai_config, 'RUSH_HOURS_MORNING', (7, 9))
    evening_rush = getattr(ai_config, 'RUSH_HOURS_EVENING', (16, 18))
    df['is_rush_hour'] = df['hour'].apply(
        lambda x: 1 if (morning_rush[0] <= x < morning_rush[1]) or \
                         (evening_rush[0] <= x < evening_rush[1]) else 0
    )
    
    # day_part: Bins [0, 6, 12, 18, 24] labels night/morning/afternoon/evening - Aligned with XGBoost_Complete.py
    df['day_part'] = pd.cut(df['hour'], 
                            bins=[0, 6, 12, 18, 24],
                            labels=['night', 'morning', 'afternoon', 'evening'],
                            include_lowest=True, # Ensure hour 0 is included in 'night'
                            right=True) # default, hours 6, 12, 18 are right boundary

    # Label Encoders - Fit and save
    le_status = LabelEncoder()
    le_city = LabelEncoder()
    le_day_part = LabelEncoder()

    df['status_encoded'] = le_status.fit_transform(df['status'].astype(str))
    joblib.dump(le_status, ai_config.LE_STATUS_PATH)
    print(f"LabelEncoder for status saved to {ai_config.LE_STATUS_PATH}")

    df['city_encoded'] = le_city.fit_transform(df['city'].astype(str))
    joblib.dump(le_city, ai_config.LE_CITY_PATH)
    print(f"LabelEncoder for city saved to {ai_config.LE_CITY_PATH}")

    # Need to handle potential NaNs introduced by pd.cut if hours are outside bins (shouldn't happen 0-23)
    # Also ensure 'nan' is handled if any 'day_part' resulted in NaN. Fit on string representation including NaN.
    df['day_part_encoded'] = le_day_part.fit_transform(df['day_part'].astype(str))
    joblib.dump(le_day_part, ai_config.LE_DAY_PART_PATH)
    print(f"LabelEncoder for day_part saved to {ai_config.LE_DAY_PART_PATH}")

    # Calculate wait_time - Aligned with XGBoost_Complete.py logic
    df = df.sort_values(by=['fence_id', 'message_time'])
    df['time_diff_seconds'] = df.groupby('fence_id')['message_time'].diff().dt.total_seconds()

    def calculate_median_positive_diff_per_group(group_series):
        # Expects a series of time diffs for a specific group (fence, status, hour, day_of_week)
        positive_diffs = group_series[group_series > 0]
        return positive_diffs.median() if not positive_diffs.empty else np.nan

    # Apply the calculation per group (fence, status, hour, day_of_week)
    # Use transform to broadcast the median back to the original DataFrame rows
    wait_time_groups = ['fence_id', 'status', 'hour', 'day_of_week']
    # Note: This calculates the median diff *between* messages within each group,
    # which is a specific way to define "wait time" from this data.
    # Replicating the exact logic from XGBoost_Complete.py
    wait_times_agg = df.groupby(wait_time_groups)['time_diff_seconds'].apply(calculate_median_positive_diff_per_group).reset_index(name='wait_time_seconds')

    # Merge the calculated wait times back
    df = pd.merge(df, wait_times_agg, on=wait_time_groups, how='left')

    # Convert seconds to minutes
    df['wait_time_minutes'] = df['wait_time_seconds'] / 60

    # Fill NaNs and clip - Aligned with XGBoost_Complete.py logic
    default_fill = getattr(ai_config, 'WAIT_TIME_DEFAULT_FILL', 10)
    clip_lower = getattr(ai_config, 'WAIT_TIME_CLIP_LOWER', 5)
    clip_upper = getattr(ai_config, 'WAIT_TIME_CLIP_UPPER', 120)

    df['wait_time_minutes'].fillna(default_fill, inplace=True)
    df['wait_time'] = df['wait_time_minutes'].clip(lower=clip_lower, upper=clip_upper)

    # Drop intermediate columns and rows with critical NaNs introduced by merges/geo
    df.drop(columns=['time_diff_seconds', 'wait_time_seconds', 'wait_time_minutes'], inplace=True, errors='ignore')
    df.dropna(subset=['latitude', 'longitude', 'city_encoded', 'geo_cluster', 'day_part_encoded'], inplace=True)

    print(f"Preprocessing complete. Resulting DataFrame shape: {df.shape}")

    return df

# --- Prepare Training Data & Save Artifacts ---
def prepare_training_data_and_save_artifacts(df):
    print("Preparing training data and saving artifacts...")
    # Define feature columns - Must match XGBoost_Complete.py and the predictor
    feature_cols = [
        'fence_id', 'latitude', 'longitude', 'hour', 'day_of_week',
        'is_weekend', 'month', 'status_encoded', 'city_encoded',
        'geo_cluster', 'is_rush_hour', 'day_part_encoded'
    ]
    
    # Ensure all feature columns exist in df
    missing_cols = [col for col in feature_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing feature columns in DataFrame: {missing_cols}. Cannot prepare training data.")
        
    # Ensure df is not empty after drops
    if df.empty:
        print("Warning: DataFrame is empty after preprocessing and feature selection. Cannot prepare training data.")
        return None, None

    X = df[feature_cols]
    y = df['wait_time']

    # Save feature columns list
    os.makedirs(ai_config.ARTIFACTS_DIR, exist_ok=True)
    with open(ai_config.FEATURE_COLUMNS_PATH, 'w') as f:
        json.dump(feature_cols, f)
    print(f"Feature columns list saved to {ai_config.FEATURE_COLUMNS_PATH}")

    # Save Scaler
    scaler = StandardScaler()
    # Fit scaler only on the features (X)
    X_scaled = scaler.fit_transform(X)
    joblib.dump(scaler, ai_config.SCALER_PATH)
    print(f"Scaler saved to {ai_config.SCALER_PATH}")
    
    return X_scaled, y

# --- Train Model ---
def train_and_save_model(X, y):
    print("Training RandomForestRegressor model...") # Updated model name
    if X is None or y is None or X.shape[0] == 0:
        print("Error: No training data available. Aborting model training.")
        return None

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    if X_train.shape[0] < 1 or X_test.shape[0] < 1 : # Check for minimal data points
        print(f"Warning: Very small dataset for training/testing. Train: {X_train.shape[0]}, Test: {X_test.shape[0]}")
        if X_train.shape[0] == 0:
             print("Error: Training set is empty. Aborting model training.")
             return None
        # Proceed with training on potentially tiny set if X_train > 0


    # --- Use RandomForestRegressor with parameters from XGBoost_Complete.py ---
    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=None,
        min_samples_split=2,
        min_samples_leaf=1,
        max_features='sqrt', # Or 1.0 if n_features is very small, but 'sqrt' is standard
        bootstrap=True,
        random_state=42,
        n_jobs=-1,
    )
    # --- END Change ---

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

    # Save the trained model
    joblib.dump(model, ai_config.MODEL_PATH)
    print(f"RandomForest model saved to {ai_config.MODEL_PATH}") # Updated model name
    return model

# --- Main Execution ---
def main():
    print("--- Starting RandomForest Model Training Process ---") # Updated name
    
    # Ensure artifacts directory exists
    os.makedirs(ai_config.ARTIFACTS_DIR, exist_ok=True)

    # Fetch data (use_cache=True is default, change to False to force DB)
    fences_df, status_df = fetch_data(use_cache=True) 

    if fences_df.empty or status_df.empty:
        print("Error: No data fetched from database or data is empty. Aborting.")
        return

    processed_df = preprocess_data(fences_df, status_df)

    if processed_df is None or processed_df.empty:
        print("Error: Data is empty after preprocessing. Aborting.")
        return
    
    print(f"Shape of processed_df before preparing training data: {processed_df.shape}")
    if 'wait_time' in processed_df.columns:
        print(f"Wait time stats: Min={processed_df['wait_time'].min():.2f}, Max={processed_df['wait_time'].max():.2f}, Mean={processed_df['wait_time'].mean():.2f}")
    else:
         print("Warning: 'wait_time' column not found after preprocessing.")
         return # Cannot train without target variable


    X_scaled, y = prepare_training_data_and_save_artifacts(processed_df)
    
    if X_scaled is None or y is None or X_scaled.shape[0] == 0:
        print("Error: Training data preparation failed or resulted in empty data. Aborting.")
        return

    model = train_and_save_model(X_scaled, y)

    if model:
        print("--- RandomForest Model Training Process Finished Successfully ---") # Updated name
    else:
        print("--- RandomForest Model Training Process Failed ---") # Updated name

if __name__ == "__main__":
    # Suppress specific warnings if they are noisy and understood
    warnings.filterwarnings("ignore", category=UserWarning, module="sklearn.cluster._kmeans")
    main()