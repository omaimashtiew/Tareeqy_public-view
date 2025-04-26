# ai_prediction/model.py


# Standard library imports first
import os
import sys
import warnings

# --- Django Setup ---
_DJANGO_SETUP_COMPLETE = False

def initialize_django():
    global _DJANGO_SETUP_COMPLETE
    if _DJANGO_SETUP_COMPLETE: return True
    print("Attempting to initialize Django...")
    try:
        script_path = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(script_path, '..', '..'))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
            print(f"Added project root to sys.path: {project_root}")
        settings_module = 'tareeqy_tracker.settings' # <<< CONFIRM THIS
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)
        import django
        django.setup()
        if not django.apps.apps.ready: raise RuntimeError("Django apps not ready after setup.")
        print("Django initialized successfully.")
        _DJANGO_SETUP_COMPLETE = True
        return True
    except Exception as e:
        print(f"Error initializing Django: {e}")
        print(f"DJANGO_SETTINGS_MODULE: {os.environ.get('DJANGO_SETTINGS_MODULE')}")
        print("Ensure settings module is correct and you run from project root.")
        _DJANGO_SETUP_COMPLETE = True # Mark as attempted
        return False

# --- Call Django Initialization ---
if initialize_django():

    # --- Third-party Imports ---
    try:
        import pandas as pd
        import joblib
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import (accuracy_score, classification_report,
                                     confusion_matrix, roc_auc_score)
        print("AI/ML libraries imported successfully.")
    except ImportError as e:
        print(f"Error importing AI/ML library: {e}")
        print("Please ensure pandas, joblib, scikit-learn are installed.")
        sys.exit(1)

    # --- Local Application Imports ---
    try:
        from tareeqy.ai_prediction.data_loader import load_and_preprocess_data # Use the modified one
        print("Data loader imported successfully.")
    except ImportError:
        print("Error: Could not import 'load_and_preprocess_data'. Check path/app name.")
        sys.exit(1)

    # --- Configuration ---
    CURRENT_DIR = os.path.dirname(__file__)
    MODEL_SAVE_PATH = os.path.join(CURRENT_DIR, 'traffic_model.pkl')
    FEATURE_COLUMNS_PATH = os.path.join(CURRENT_DIR, 'feature_columns.pkl')
    # Label encoder path removed

    # --- Model Training Function ---
    def train_and_evaluate_binary_model():
        """
        Loads preprocessed data (binary target), trains a RandomForestClassifier
        for jam prediction, evaluates it, and saves the model and features.
        """
        print("\n--- Starting Binary Model Training Process (Jam Prediction) ---")

        # --- 1. Load Preprocessed Data ---
        X_train, X_test, y_train, y_test = load_and_preprocess_data() # Gets binary y

        if X_train is None:
            print("Error: Failed to load/preprocess data. Aborting.")
            return False

        if X_train.empty or y_train.empty:
            print("Error: Training data is empty. Aborting.")
            return False

        print(f"\nData loaded for binary training.")
        print(f"Training samples: {X_train.shape[0]}, Features: {X_train.shape[1]}")
        print(f"Test samples: {X_test.shape[0]}")

        # --- 2. Train the Binary Model ---
        # Use class_weight='balanced' due to expected imbalance (fewer jams)
        model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced', n_jobs=-1)

        print("\nTraining RandomForestClassifier model (for Jam vs Not Jam)...")
        try:
            model.fit(X_train, y_train)
            print("Model training completed successfully!")
        except Exception as e:
            print(f"Error during model training: {e}")
            import traceback; traceback.print_exc()
            return False

        # --- 3. Evaluate the Binary Model ---
        print("\nEvaluating model performance on the test set (Jam vs Not Jam)...")
        if X_test.empty or y_test.empty:
            print("Warning: Test data is empty. Skipping evaluation.")
        else:
            try:
                y_pred = model.predict(X_test)
                # Get probability of the positive class (Jam = 1) for ROC AUC
                y_pred_proba = model.predict_proba(X_test)[:, 1]

                accuracy = accuracy_score(y_test, y_pred)
                print(f"  Overall Accuracy (Jam vs Not Jam): {accuracy * 100:.2f}%")

                print("\n  Classification Report (0=Not Jam, 1=Jam):")
                target_names = ['Not Jam', 'Jam']
                print(classification_report(y_test, y_pred, target_names=target_names, zero_division=0))

                print("\n  Confusion Matrix (Rows=Actual, Cols=Predicted):")
                cm = confusion_matrix(y_test, y_pred)
                cm_df = pd.DataFrame(cm, index=target_names, columns=target_names)
                print(cm_df)

                # ROC AUC Score is good for binary imbalanced problems
                try:
                    roc_auc = roc_auc_score(y_test, y_pred_proba)
                    print(f"\n  ROC AUC Score: {roc_auc:.4f}")
                except Exception as e_auc:
                    print(f"\n  Could not calculate ROC AUC: {e_auc}")

            except Exception as e:
                print(f"Error during model evaluation: {e}")
                import traceback; traceback.print_exc()

        # --- 4. Save Trained Model & Feature Columns ---
        print(f"\nSaving the trained binary model to: {MODEL_SAVE_PATH}")
        try:
            os.makedirs(os.path.dirname(MODEL_SAVE_PATH), exist_ok=True)
            joblib.dump(model, MODEL_SAVE_PATH)
            print("Model saved successfully!")
        except Exception as e:
            print(f"Error saving the model: {e}")
            return False

        # Save feature columns list used during training
        try:
            feature_columns = list(X_train.columns)
            joblib.dump(feature_columns, FEATURE_COLUMNS_PATH)
            print(f"Feature column list saved to: {FEATURE_COLUMNS_PATH}")
        except Exception as e:
            print(f"Warning: Could not save feature columns list: {e}")

        print("\n--- Model Training Process Finished ---")
        return True

    # --- Main Execution Logic ---
    if __name__ == "__main__":
        if not train_and_evaluate_binary_model():
            print("\nModel training process failed.")
            sys.exit(1)
        else:
            print("\nModel training script completed successfully.")

else:
    print("\nExiting script: Django initialization failed.")
    sys.exit(1)