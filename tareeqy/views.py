from django.shortcuts import render
from django.http import HttpResponse
import asyncio
from .telegram_listener import start_client
from .models import Fence, FenceStatus  # Import your models here

# Make the view asynchronous
async def update_fences(request):
    """Trigger the process to fetch and update fences"""
    # Start the Telegram client asynchronously
    await start_client()  # Ensure the start_client function is async
    return render(request, 'update_fences.html')

def fence_status(request):
    """Display the status of fences"""
    fences = Fence.objects.all()  # Get all fences from the database
    statuses = FenceStatus.objects.all()  # Get all statuses from the database
    context = {
        'fences': fences,
        'statuses': statuses
    }
    return render(request, 'fences.html', context)  # Render the fences.html template with the fence data


# In your Django view
from ai_prediction.predictor import predict_status_at_arrival, load_prediction_artifacts
from datetime import datetime

# Load artifacts when the Django app starts (e.g., in apps.py ready() method or on first view call)
# You might want a more robust way to ensure this runs once in production.
if not load_prediction_artifacts():
    # Handle error - prediction service unavailable
    pass

def get_fence_prediction(request, fence_id_from_url):
    # Get user location, calculate travel time (e.g., using Maps API)
    current_time = datetime.now()
    fence_id = int(fence_id_from_url)
    estimated_travel_time = 15 # Example: calculate this properly

    prediction = predict_status_at_arrival(
        fence_id=fence_id,
        current_time=current_time,
        travel_time_minutes=estimated_travel_time
    )

    # Use the 'prediction' dictionary in your template or API response
    # Check prediction['success'] first
    # ... render template or return JsonResponse ...