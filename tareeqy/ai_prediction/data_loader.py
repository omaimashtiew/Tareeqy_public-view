# ai_prediction/data_loader.py

import os
import django
import pandas as pd
from sklearn.model_selection import train_test_split
# Removed LabelEncoder import
import joblib
import sys # For path checking in main block

# --- Configuration ---
# Define output directory for saved artifacts relative to this file
OUTPUT_DIR = os.path.dirname(__file__)
# Only need to save feature columns now
FEATURE_COLUMNS_PATH = os.path.join(OUTPUT_DIR, 'feature_columns.pkl')
# Label encoder path removed

# DJANGO_SETTINGS_MODULE should be set by the calling script (model.py/predictor.py)
# but we need the model import path. Ensure 'tareeqy' is your app name.
APP_NAME = 'tareeqy'

def load_and_preprocess_data(test_size=0.2, random_state=42):
    """
    Loads fence status data from the Django model 'FenceStatus', preprocesses it
    for binary jam prediction (feature engineering, one-hot encoding), saves
    feature columns, and splits the data into train/test sets.

    Args:
        test_size (float): Proportion of the dataset to include in the test split.
        random_state (int): Controls the shuffling applied to the data before splitting.

    Returns:
        tuple: (X_train, X_test, y_train, y_test) pandas DataFrames/Series with binary target.
               Returns (None, None, None, None) if loading or processing fails.
    """
    print("--- Starting Data Loading and Preprocessing (Binary Jam Target) ---")
    try:
        # Import Django model inside the function to ensure Django apps are ready
        from tareeqy.models import FenceStatus # Assuming your app is named 'tareeqy'

        # --- 1. Load Data from Django Model ---
        print("Loading data from Django model 'FenceStatus'...")
        data_qs = FenceStatus.objects.all().values('fence_id', 'status', 'message_time')
        df = pd.DataFrame(list(data_qs))

        if df.empty:
            print("Error: No data found in the 'FenceStatus' table.")
            return None, None, None, None

        print(f"Loaded {len(df)} records.")

        # --- 2. Basic Cleaning & Type Conversion ---
        df['message_time'] = pd.to_datetime(df['message_time'])
        df.dropna(subset=['fence_id', 'status', 'message_time'], inplace=True)
        print(f"Records after potential NA drop: {len(df)}")
        if df.empty:
            print("Error: Dataframe is empty after dropping NA.")
            return None, None, None, None

        # --- 3. Feature Engineering ---
        print("Engineering time features from 'message_time'...")
        df['hour'] = df['message_time'].dt.hour
        df['day_of_week'] = df['message_time'].dt.dayofweek # Monday=0, Sunday=6
        # Adjust weekend definition if necessary (e.g., 4, 5 for Fri/Sat)
        df['is_weekend'] = df['message_time'].dt.dayofweek.isin([5, 6]).astype(int) # Sat/Sun = 1

        # --- 4. Create Binary Target Variable & Encode Features ---
        # a) Create Target Variable ('is_jam')
        print("Creating binary target variable 'is_jam' (1 if sever_traffic_jam, 0 otherwise)...")
        df['is_jam'] = df['status'].apply(lambda x: 1 if x == 'sever_traffic_jam' else 0)

        # b) Encode Feature ('fence_id') using One-Hot Encoding
        print("Encoding feature 'fence_id' using One-Hot Encoding...")
        df['fence_id'] = df['fence_id'].astype(str)
        df_encoded = pd.get_dummies(df, columns=['fence_id'], prefix='fence', drop_first=False)

        # --- Define Features (X) and Target (y) ---
        target_column = 'is_jam' # Use the new binary target
        features_to_drop = ['status', 'message_time', target_column]
        # Remove status_encoded if it somehow exists from old runs
        if 'status_encoded' in df_encoded.columns:
             features_to_drop.append('status_encoded')

        X = df_encoded.drop(columns=features_to_drop)
        y = df_encoded[target_column] # y is now binary

        # --- Save the feature columns list (Still needed) ---
        feature_columns = list(X.columns)
        print(f"Saving feature column list ({len(feature_columns)} features) to {FEATURE_COLUMNS_PATH}")
        os.makedirs(os.path.dirname(FEATURE_COLUMNS_PATH), exist_ok=True)
        joblib.dump(feature_columns, FEATURE_COLUMNS_PATH)

        # --- 5. Split Data ---
        print(f"Splitting data into train/test sets (test_size={test_size})...")
        # Stratify based on the new binary target 'y'
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=test_size,
            random_state=random_state,
            stratify=y # Stratify based on 0s and 1s (important for imbalance)
        )

        print(f"Training set shape: X={X_train.shape}, y={y_train.shape}")
        print(f"Test set shape: X={X_test.shape}, y={y_test.shape}")
        print("Class distribution in y_train (0=Not Jam, 1=Jam):\n", y_train.value_counts(normalize=True))
        print("--- Data Loading and Preprocessing Finished Successfully ---")

        return X_train, X_test, y_train, y_test

    except ImportError as e:
        print(f"Error: Failed to import Django model. Is Django setup correctly? App name: '{APP_NAME}'? {e}")
        return None, None, None, None
    except Exception as e:
        print(f"An error occurred during data loading/preprocessing: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None, None

# --- Example Usage Block (for testing this script directly via Django shell) ---
# To test: python manage.py shell
# >>> from tareeqy.ai_prediction.data_loader import load_and_preprocess_data
# >>> X_train, X_test, y_train, y_test = load_and_preprocess_data()
# >>> if X_train is not None: print(X_train.head())