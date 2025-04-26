# tareeqy/views.py

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import OuterRef, Subquery
import json
from datetime import datetime
import math
import traceback # For better error logging

# Import your models
from .models import Fence, FenceStatus

# --- Import AI Predictor Functions ---
try:
    from .ai_prediction.predictor import (
        predict_jam_probability_at_arrival,
        load_prediction_artifacts,
        setup_django as predictor_setup_django
    )
    print("Attempting predictor setup and artifact load from views.py...")
    if predictor_setup_django():
        load_prediction_artifacts()
    else:
        print("CRITICAL: Django setup failed in predictor - AI features disabled.")
except ImportError as e:
    print(f"CRITICAL ERROR: Cannot import AI predictor module: {e}. AI features disabled.")
    def predict_jam_probability_at_arrival(*args, **kwargs):
        print("Warning: AI predictor called, but module was not loaded.")
        return {'success': False, 'error': 'AI predictor module not available.'}
# --- End AI Imports ---


# --- View for the Main Map Page ---
# This function renders your HTML template
def map_view(request):
    """Display the main map with initial fence statuses."""
    print("Executing map_view...")
    try:
        latest_update = FenceStatus.objects.filter(fence_id=OuterRef('pk')).order_by('-message_time')
        fences_qs = Fence.objects.annotate(
            latest_status=Subquery(latest_update.values('status')[:1]),
            latest_time=Subquery(latest_update.values('message_time')[:1]),
            latest_image=Subquery(latest_update.values('image')[:1])
        ).values('id', 'name', 'latitude', 'longitude', 'latest_status', 'latest_time', 'latest_image')

        fence_data = []
        for fence in fences_qs:
            status_time_iso = fence['latest_time'].isoformat() if fence['latest_time'] else None
            lat = float(fence['latitude']) if fence['latitude'] is not None else None
            lon = float(fence['longitude']) if fence['longitude'] is not None else None
            if lat is None or lon is None or (lat == 0 and lon == 0):
                 # print(f"Skipping fence '{fence['name']}' (ID: {fence['id']}) due to invalid coordinates for map.") # Less verbose
                 continue
            fence_data.append({
                'id': fence['id'], 'name': fence['name'],
                'status': fence['latest_status'] or 'unknown',
                'message_time': status_time_iso, 'image': fence['latest_image'],
                'latitude': lat, 'longitude': lon
            })
        context = {'fences_json': json.dumps(fence_data)}
        # *** ENSURE TEMPLATE PATH IS 'tareeqy/update_fences.html' RELATIVE TO A TEMPLATES DIRECTORY ***
        return render(request, 'update_fences.html', context)
    except Exception as e:
        print(f"ERROR in map_view: {e}")
        traceback.print_exc()
        context = {'fences_json': '[]', 'error': 'Could not load map data.'}
        # *** ENSURE TEMPLATE PATH IS 'tareeqy/update_fences.html' ***
        return render(request, 'update_fences.html', context, status=500)


# --- Helper function for distance (Haversine) ---
def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points in kilometers."""
    if None in [lat1, lon1, lat2, lon2]: return float('inf')
    try: lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    except (ValueError, TypeError): return float('inf')
    R=6371; dLat=math.radians(lat2-lat1); dLon=math.radians(lon2-lon1)
    a=math.sin(dLat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dLon/2)**2
    c=2*math.atan2(math.sqrt(a),math.sqrt(1-a)); distance=R*c
    return distance

# --- API View for Predictions ---
@require_POST
def get_predictions_for_location(request):
    """ API endpoint called by JS to get predictions """
    try:
        data = json.loads(request.body)
        user_lat = float(data['latitude']); user_lon = float(data['longitude'])
        MAX_DISTANCE_KM=75; AVG_SPEED_KMH=40; MAX_TRAVEL_MINUTES=360

        latest_update = FenceStatus.objects.filter(fence_id=OuterRef('pk')).order_by('-message_time')
        fences_qs = Fence.objects.annotate(
            latest_status=Subquery(latest_update.values('status')[:1]),
            latest_time=Subquery(latest_update.values('message_time')[:1])
        ).values('id', 'name', 'latitude', 'longitude', 'latest_status', 'latest_time')

        results = []; current_time = timezone.now()
        for fence in fences_qs:
            if fence['latitude'] is None or fence['longitude'] is None: continue
            try:
                 fence_lat=float(fence['latitude']); fence_lon=float(fence['longitude'])
                 if fence_lat == 0 and fence_lon == 0: continue
            except (ValueError, TypeError): continue

            distance_km = haversine(user_lat, user_lon, fence_lat, fence_lon)
            if distance_km > MAX_DISTANCE_KM: continue

            travel_time_minutes = int((distance_km / AVG_SPEED_KMH) * 60) if AVG_SPEED_KMH > 0 else float('inf')
            if travel_time_minutes > MAX_TRAVEL_MINUTES: continue

            ai_result = predict_jam_probability_at_arrival(
                fence_id=fence['id'], current_time=current_time, travel_time_minutes=travel_time_minutes
            )
            fence_result = {
                'id': fence['id'], 'name': fence['name'], 'latitude': fence_lat, 'longitude': fence_lon,
                'distance_km': round(distance_km, 1),
                'current_status': fence['latest_status'] or 'unknown',
                'status_time_iso': fence['latest_time'].isoformat() if fence['latest_time'] else None,
                'estimated_travel_minutes': travel_time_minutes if travel_time_minutes != float('inf') else None,
                'prediction_success': ai_result.get('success', False),
                'predicted_jam_probability_percent': ai_result.get('jam_probability_percent') if ai_result.get('success') else None,
                'prediction_arrival_time_iso': ai_result.get('estimated_arrival_time_iso') if ai_result.get('success') else None,
                'prediction_error': ai_result.get('error') if not ai_result.get('success') else None
            }
            results.append(fence_result)
        return JsonResponse({'fences': results})
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        return JsonResponse({'error': f'Invalid request data: {e}'}, status=400)
    except Exception as e:
        print(f"SERVER ERROR in get_predictions_for_location: {e}")
        traceback.print_exc()
        return JsonResponse({'error': 'Internal server error.'}, status=500)