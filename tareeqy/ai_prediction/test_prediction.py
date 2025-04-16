# ai_prediction/test_prediction.py
import unittest
from datetime import datetime
import os
import sys

# Add project root to path to allow importing ai_prediction modules
# Adjust the path depth ('..') based on your test execution location
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Set up Django environment for testing (needed if predictor uses Django)
# Note: For pure unit tests, you might mock Django interactions
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tareeqy_tracker.settings') # Use your actual settings
import django
try:
    django.setup()
except Exception as e:
    print(f"Warning: Django setup failed during test import: {e}")
    # Decide if tests can proceed without full Django setup (e.g., if mocking)

from ai_prediction.predictor import predict_status_at_arrival, load_prediction_artifacts

class TestPrediction(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Load artifacts once for all tests in this class
        # Ensure artifacts exist before running tests
        print("Setting up test class - loading prediction artifacts...")
        if not load_prediction_artifacts():
           raise RuntimeError("Failed to load prediction artifacts. Cannot run tests.")
        print("Artifacts loaded for testing.")


    def test_successful_prediction_weekday_morning(self):
        """Test prediction for a known fence ID during a weekday morning."""
        fence_id = 1  # Assuming fence 1 exists and was trained on
        # Pick a specific weekday morning time
        current_time = datetime(2024, 5, 15, 8, 30, 0) # Wednesday 8:30 AM
        travel_time = 15
        result = predict_status_at_arrival(fence_id, current_time, travel_time)

        self.assertTrue(result['success'])
        self.assertEqual(result['fence_id'], fence_id)
        self.assertIn('predicted_status', result)
        self.assertIn('probabilities', result)
        self.assertIn('open', result['probabilities']) # Check if all keys exist
        self.assertIn('closed', result['probabilities'])
        self.assertIn('sever_traffic_jam', result['probabilities'])
        # Add more specific assertions if you know the expected outcome for this time

    def test_successful_prediction_weekend_evening(self):
        """Test prediction for a known fence ID during a weekend evening."""
        fence_id = 22 # Assuming fence 22 exists
        # Pick a specific weekend evening time
        current_time = datetime(2024, 5, 18, 19, 0, 0) # Saturday 7:00 PM
        travel_time = 10
        result = predict_status_at_arrival(fence_id, current_time, travel_time)

        self.assertTrue(result['success'])
        self.assertEqual(result['fence_id'], fence_id)
        # Add more assertions

    # def test_unknown_fence_id(self):
    #     """Test prediction for a fence ID not seen during training."""
    #     fence_id = 999 # An unlikely fence ID
    #     current_time = datetime.now()
    #     travel_time = 5
    #     result = predict_status_at_arrival(fence_id, current_time, travel_time)
         # Depending on how you handled unknown IDs in predictor.py:
         # Option 1: Assert failure
         # self.assertFalse(result['success'])
         # self.assertIn('error', result)
         # Option 2: Assert success but maybe check probabilities are less confident
         # self.assertTrue(result['success'])
         # # Check the specific behaviour for unknown IDs

    def test_zero_travel_time(self):
        """Test prediction when travel time is zero."""
        fence_id = 5
        current_time = datetime.now()
        travel_time = 0
        result = predict_status_at_arrival(fence_id, current_time, travel_time)

        self.assertTrue(result['success'])
        # Check if arrival time equals current time (within tolerance if needed)
        self.assertEqual(result['estimated_arrival_time'], result['current_time'])


if __name__ == '__main__':
    unittest.main()