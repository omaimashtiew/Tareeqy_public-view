# tareeqy/ai_prediction/test_prediction.py


import unittest
import os
import sys
from datetime import datetime, timedelta

# --- Path Setup ---
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    if project_root not in sys.path:
        print(f"(test_prediction.py) Adding project root to sys.path: {project_root}")
        sys.path.insert(0, project_root)
except Exception as e:
    print(f"Error during test path setup: {e}")
    sys.exit("Exiting test setup due to path error.")

# --- Django Setup ---
try:
    settings_module = 'tareeqy_tracker.settings' # <<< CONFIRM THIS IS CORRECT >>>
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)
    import django
    # Only run setup if running standalone (not via manage.py test)
    if not django.apps.apps.ready and __name__ == "__main__":
        print("(test_prediction.py) Setting up Django for standalone test run...")
        django.setup()
        print("(test_prediction.py) Django setup complete.")
except Exception as e:
    print(f"Warning: Django setup failed during test import: {e}")

# --- Import the functions to test ---
try:
    # Use the correct function name for jam probability
    from tareeqy.ai_prediction.predictor import (
        predict_jam_probability_at_arrival,
        load_prediction_artifacts
    )
    print("(test_prediction.py) Predictor functions imported.")
except ImportError as e:
    print(f"Failed to import predictor functions: {e}")
    sys.exit("Exiting tests due to import error.")

# --- Test Class ---
class TestJamPrediction(unittest.TestCase):

    _artifacts_loaded = False

    @classmethod
    def setUpClass(cls):
        """Load AI artifacts once before running tests."""
        print("\nSetting up test class - loading prediction artifacts...")
        if load_prediction_artifacts():
            cls._artifacts_loaded = True
            print("Artifacts loaded successfully for testing.")
        else:
            print("WARNING: Failed to load artifacts. Tests will be skipped.")

    def setUp(self):
        """Skip test if artifacts couldn't be loaded."""
        if not TestJamPrediction._artifacts_loaded:
            self.skipTest("Prediction artifacts could not be loaded.")

    # --- Test Cases ---
    def test_high_probability_scenario(self):
        """Test prediction for a known fence ID during expected high traffic time."""
        fence_id = 22 # Example ID
        current_time = datetime.now().replace(hour=8, minute=30, second=0, microsecond=0)
        travel_time = 10 # arrival at 8:40 AM
        result = predict_jam_probability_at_arrival(fence_id, current_time, travel_time)
        print(f"\nTest High Prob (Fence {fence_id}, ~8:40 AM): {result}")
        self.assertTrue(result.get('success'), f"Prediction failed: {result.get('error')}")
        self.assertIn('jam_probability_percent', result) # Check correct key name
        self.assertIsInstance(result['jam_probability_percent'], (float, int))
        self.assertGreaterEqual(result['jam_probability_percent'], 45.0, "Expected reasonable jam probability for rush hour (~>=45%)")
    def test_low_probability_scenario(self):
        """Test prediction for a known fence ID during expected low traffic time."""
        fence_id = 1 # Example ID
        current_time = datetime.now().replace(hour=2, minute=0, second=0, microsecond=0)
        travel_time = 15 # arrival at 2:15 AM
        result = predict_jam_probability_at_arrival(fence_id, current_time, travel_time)
        print(f"\nTest Low Prob (Fence {fence_id}, ~2:15 AM): {result}")
        self.assertTrue(result.get('success'), f"Prediction failed: {result.get('error')}")
        self.assertIn('jam_probability_percent', result) # Check correct key name
        self.assertIsInstance(result['jam_probability_percent'], (float, int))
        self.assertLess(result['jam_probability_percent'], 40, "Expected jam probability < 40%")

    def test_unknown_fence_id(self):
        """Test prediction fails correctly for a fence ID not seen during training."""
        fence_id = 999 # Assumed unknown ID
        current_time = datetime.now()
        travel_time = 5
        result = predict_jam_probability_at_arrival(fence_id, current_time, travel_time)
        print(f"\nTest Unknown Fence ({fence_id}): {result}")
        self.assertFalse(result.get('success'), "Prediction should fail for unknown fence ID")
        error_msg = result.get('error', '')
        self.assertTrue(error_msg.startswith('Fence ID'), "Error message should start with 'Fence ID'")
        self.assertIn('not recognized by the model', error_msg, "Error message should contain 'not recognized by the model'")
    def test_zero_travel_time(self):
        """Test prediction works when travel time is zero."""
        fence_id = 5 # Any known ID
        current_time = datetime.now()
        travel_time = 0
        result = predict_jam_probability_at_arrival(fence_id, current_time, travel_time)
        print(f"\nTest Zero Travel (Fence {fence_id}): {result}")
        self.assertTrue(result.get('success'), f"Prediction failed: {result.get('error')}")
        self.assertIn('jam_probability_percent', result)
        arrival_dt = datetime.fromisoformat(result['estimated_arrival_time_iso'])
        current_dt_for_compare = datetime.fromisoformat(current_time.isoformat())
        time_diff = abs((arrival_dt - current_dt_for_compare).total_seconds())
        self.assertLess(time_diff, 0.1, "Arrival time should closely match current time")

    def test_invalid_travel_time(self):
        """Test prediction fails with negative travel time."""
        fence_id = 1
        current_time = datetime.now()
        travel_time = -10
        result = predict_jam_probability_at_arrival(fence_id, current_time, travel_time)
        print(f"\nTest Invalid Travel ({travel_time} min): {result}")
        self.assertFalse(result.get('success'), "Prediction should fail for negative travel time")
        self.assertIn('invalid', result.get('error', '').lower()) # Check for 'invalid' in error

# --- Standard unittest runner ---
if __name__ == '__main__':
    print("-" * 60 + "\nRunning prediction tests...\n" + "-" * 60)
    unittest.main(verbosity=2)
    print("-" * 60 + "\nFinished prediction tests.\n" + "-" * 60)