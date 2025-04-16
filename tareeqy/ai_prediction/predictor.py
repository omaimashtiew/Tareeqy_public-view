# ai_prediction/predictor.py

# Standard library imports
import os
import sys
from datetime import datetime, timedelta
import json # For printing results nicely

# --- Path Setup ---
# Needs to happen before we try to import Django or project modules
# Only run when the script is executed directly
if __name__ == "__main__":
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up two levels: ai_prediction -> tareeqy -> project_root
        project_root = os.path.dirname(os.path.dirname(script_dir))
        if project_root not in sys.path:
            print(f"(predictor.py) Adding project root to sys.path: {project_root}")
            sys.path.insert(0, project_root)
    except Exception as e:
        print(f"Error during path setup: {e}")
        sys.exit("Exiting due to path setup error.")

# --- Third-party library imports ---
# These are generally safe to import after path setup but before Django setup
try:
    import joblib
    import pandas as pd
    import numpy as np
except ImportError as e:
    print(f"Error importing required libraries (joblib, pandas, numpy): {e}")
    print("Please ensure these libraries are installed in your environment (`pip install joblib pandas numpy`).")
    sys.exit("Exiting due to missing libraries.")

# --- Django import (AFTER path setup) ---
try:
    import django
except ImportError as e:
    print(f"Error importing Django: {e}")
    print("Ensure Django is installed (`pip show django`).")
    sys.exit("Exiting due to missing Django.")


# --- Configuration ---
# Project settings module (relative to project root added to sys.path)
# <<< CONFIRM THIS IS CORRECT >>>
DJANGO_SETTINGS_MODULE = 'tareeqy_tracker.settings'
# Paths for ML artifacts (relative to this script's location)
CURRENT_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(CURRENT_DIR, 'traffic_model.pkl') # Path to the BINARY model
FEATURE_COLUMNS_PATH = os.path.join(CURRENT_DIR, 'feature_columns.pkl')


# --- Global State for Loaded Artifacts & Django Setup ---
PREDICTION_ARTIFACTS = {
    "model": None,
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

    print("Attempting to initialize Django...")
    try:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', DJANGO_SETTINGS_MODULE)
        django.setup()
        # Verify that setup worked and apps are ready
        if not django.apps.apps.ready:
            raise RuntimeError("Django apps not ready after django.setup() call.")
        print("Django initialized successfully.")
        _DJANGO_SETUP_COMPLETE = True
        return True
    except Exception as e:
        print(f"Error initializing Django: {e}")
        print(f"Settings module used: '{os.environ.get('DJANGO_SETTINGS_MODULE')}'")
        import traceback
        traceback.print_exc()
        # Do not set _DJANGO_SETUP_COMPLETE to True on failure
        return False

# --- Artifact Loading Function ---
def load_prediction_artifacts(force_reload=False):
    """Loads the trained binary model and feature columns."""
    if PREDICTION_ARTIFACTS["loaded"] and not force_reload:
        return True

    print("Loading prediction artifacts (binary model)...")
    try:
        # Check file existence first
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Model file not found at {MODEL_PATH}")
        if not os.path.exists(FEATURE_COLUMNS_PATH):
            raise FileNotFoundError(f"Feature columns file not found at {FEATURE_COLUMNS_PATH}")

        # Load the artifacts
        PREDICTION_ARTIFACTS["model"] = joblib.load(MODEL_PATH)
        PREDICTION_ARTIFACTS["feature_columns"] = joblib.load(FEATURE_COLUMNS_PATH)
        PREDICTION_ARTIFACTS["loaded"] = True

        print("Prediction artifacts loaded successfully.")
        # Optional details for confirmation
        # print(f" - Model type: {type(PREDICTION_ARTIFACTS['model'])}")
        # print(f" - Number of feature columns expected: {len(PREDICTION_ARTIFACTS['feature_columns'])}")
        return True

    except FileNotFoundError as e:
        print(f"Error loading artifacts: {e}")
        print("Please ensure the BINARY model has been trained using 'model.py' and artifacts exist.")
        PREDICTION_ARTIFACTS["loaded"] = False
        return False
    except Exception as e:
        print(f"An unexpected error occurred loading artifacts: {e}")
        import traceback
        traceback.print_exc()
        PREDICTION_ARTIFACTS["loaded"] = False
        return False

# --- Prediction Function (Binary Jam Probability) ---
def predict_jam_probability_at_arrival(fence_id: int, current_time: datetime, travel_time_minutes: int):
    """
    Predicts the probability of a severe traffic jam for a fence at the estimated arrival time.
    Uses the loaded binary classification model.
    """
    # 1. Ensure artifacts are loaded
    if not PREDICTION_ARTIFACTS["loaded"]:
        if not load_prediction_artifacts():
            # Attempt to load if not already loaded
            return {'success': False, 'error': 'Failed to load prediction artifacts.'}

    # 2. Calculate Arrival Time and Validate Inputs
    try:
        if not isinstance(current_time, datetime):
             raise TypeError("current_time must be a datetime object")
        if not isinstance(travel_time_minutes, (int, float)) or travel_time_minutes < 0:
             raise ValueError("travel_time_minutes must be a non-negative number")
        arrival_time = current_time + timedelta(minutes=travel_time_minutes)
    except (TypeError, ValueError) as e:
         return {'success': False, 'error': f"Invalid input for time calculation: {e}"}
    except Exception as e:
         return {'success': False, 'error': f"Error calculating arrival time: {e}"}

    # 3. Feature Engineering (matching data_loader for the binary model)
    try:
        # Extract base time features
        hour = arrival_time.hour
        day_of_week = arrival_time.weekday() # Monday=0, Sunday=6
        is_weekend = 1 if day_of_week in [5, 6] else 0 # Assumes Sat/Sun weekend

        # Prepare input dict using expected feature columns
        input_features = {}
        all_feature_columns = PREDICTION_ARTIFACTS["feature_columns"]
        if not all_feature_columns:
             raise ValueError("Feature column list loaded from artifact is empty.")

        # Initialize all expected columns to 0
        for col in all_feature_columns:
            input_features[col] = 0

        # Populate the known features
        if 'hour' in input_features: input_features['hour'] = hour
        if 'day_of_week' in input_features: input_features['day_of_week'] = day_of_week
        if 'is_weekend' in input_features: input_features['is_weekend'] = is_weekend
        # Add any other non-one-hot features if they were added during training

        # Handle the one-hot encoded fence ID
        fence_col_name = f"fence_{fence_id}" # Matches prefix from pd.get_dummies
        if fence_col_name in input_features:
            input_features[fence_col_name] = 1
        else:
            # Fence ID not seen during training
            print(f" - Warning: Fence ID {fence_id} (column '{fence_col_name}') was not present during model training.")
            # Return an error as prediction is unreliable
            return {'success': False, 'error': f"Fence ID {fence_id} not recognized by the model."}

        # Create a Pandas DataFrame with columns in the exact order expected by the model
        input_df = pd.DataFrame([input_features], columns=all_feature_columns)

    except Exception as e:
        print(f"Error during feature engineering: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': f"Feature engineering failed: {e}"}

    # 4. Make Prediction
    try:
        model = PREDICTION_ARTIFACTS["model"]
        if model is None:
            raise ValueError("Model artifact is not loaded.")

        # Predict probabilities: result is array like [[prob_class_0, prob_class_1]]
        probabilities_array = model.predict_proba(input_df)

        # Extract probability of the positive class (Jam = Class 1 - index 1)
        jam_probability = probabilities_array[0, 1]

        # Return results
        return {
            'success': True,
            'fence_id': fence_id,
            'current_time_iso': current_time.isoformat(),
            'travel_time_minutes': travel_time_minutes,
            'estimated_arrival_time_iso': arrival_time.isoformat(),
            'jam_probability_percent': round(jam_probability * 100, 1) # Return the percentage
        }

    except Exception as e:
        print(f"Error during prediction execution: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': f"Prediction execution failed: {e}"}


# --- Main Execution Block (for testing this script) ---
if __name__ == "__main__":
    # Path setup is done above this block
    print("-" * 50)
    print("Running predictor.py as standalone script...")
    print("-" * 50)

    # Attempt Django setup first
    if setup_django():
        print("\n--- Running Predictor Standalone Test (Jam Probability) ---")

        # Load artifacts (required for prediction)
        if load_prediction_artifacts():

            # --- Define Test Cases ---
            test_cases = [
                {"fence_id": 1, "travel_time": 20, "description": "Fence 1, current time arrival + 20 min"},
                {"fence_id": 22, "travel_time": 10, "description": "Fence 22, arrival at ~8:40 AM", "current_time": datetime.now().replace(hour=8, minute=30)},
                # Example: Test a fence ID known NOT to be in the training data (if you know one)
                # {"fence_id": 999, "travel_time": 5, "description": "Unknown Fence ID"},
            ]

            for i, case in enumerate(test_cases):
                print(f"\n--- Test Case {i+1}: {case['description']} ---")
                fence_id = case["fence_id"]
                travel_time = case["travel_time"]
                # Use specified current_time or default to now
                current_time = case.get("current_time", datetime.now())

                prediction_result = predict_jam_probability_at_arrival(
                    fence_id=fence_id,
                    current_time=current_time,
                    travel_time_minutes=travel_time
                )
                print(f"\nPrediction Result (Test Case {i+1}):")
                # Use json.dumps for nicely formatted dictionary output
                print(json.dumps(prediction_result, indent=2))

        else:
            print("\nCritical Error: Could not load prediction artifacts. Tests aborted.")
            print("Please ensure the binary model was trained successfully using model.py.")

    else:
        print("\nCritical Error: Django initialization failed. Script cannot proceed.")
        print("Please check Django setup and settings module path.")

    print("-" * 50)
    print("predictor.py script finished.")
    print("-" * 50)