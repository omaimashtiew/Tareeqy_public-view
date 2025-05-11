# tareeqy/views.py

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import OuterRef, Subquery, Q
import json
from datetime import datetime
import math
import traceback

from .models import Fence, FenceStatus

# --- AI Predictor Imports (Ensure this block is correctly set up for your project) ---
try:
    from .ai_prediction.predictor import (
        predict_jam_probability_at_arrival,
        load_prediction_artifacts,
        setup_django as predictor_setup_django
    )
    print("Attempting predictor setup and artifact load from views.py...")
    if predictor_setup_django(): # Call the setup function
        load_prediction_artifacts()
        print("Predictor setup and artifact load successful from views.py.")
    else:
        print("CRITICAL: Django setup failed in predictor - AI features will be unstable or disabled.")
except ImportError as e:
    print(f"CRITICAL ERROR: Cannot import AI predictor module: {e}. AI features disabled.")
    def predict_jam_probability_at_arrival(*args, **kwargs):
        print("Warning: AI predictor called, but module was not loaded due to import error.")
        return {'success': False, 'error': 'AI predictor module not available.'}
# --- End AI Imports ---


def welcome_view(request):
    """Display the welcome page."""
    return render(request, 'welcome.html')


def map_view(request):
    """Display the main map with initial fence statuses."""
    print("Executing map_view to render tareeqy/map_view.html")
    try:
        latest_status_sq = FenceStatus.objects.filter(
            fence_id=OuterRef('pk')
        ).order_by('-message_time')

        fences_qs = Fence.objects.annotate(
            latest_status=Subquery(latest_status_sq.values('status')[:1]),
            latest_time=Subquery(latest_status_sq.values('message_time')[:1]),
            latest_image=Subquery(latest_status_sq.values('image')[:1])
        ).values(
            'id', 'name', 'latitude', 'longitude', 'city',
            'latest_status', 'latest_time', 'latest_image'
        )

        fence_data = []
        for fence in fences_qs:
            status_time_iso = fence['latest_time'].isoformat() if fence['latest_time'] else None
            try:
                lat = float(fence['latitude']) if fence['latitude'] is not None else None
                lon = float(fence['longitude']) if fence['longitude'] is not None else None
            except (ValueError, TypeError):
                lat, lon = None, None

            if lat is None or lon is None or (abs(lat) < 0.0001 and abs(lon) < 0.0001):
                continue # Skip fences with invalid or zero coordinates
            
            fence_data.append({
                'id': fence['id'],
                'name': fence['name'],
                'status': fence['latest_status'] or 'unknown',
                'message_time': status_time_iso,
                'image': fence['latest_image'] or '',
                'city': fence['city'] or '',
                'latitude': lat,
                'longitude': lon
            })

        context = {'fences_json': json.dumps(fence_data)}
        return render(request, 'map_view.html', context)

    except Exception as e:
        print(f"ERROR in map_view: {e}")
        traceback.print_exc()
        error_context = {
            'fences_json': '[]',
            'error_message': 'حدث خطأ أثناء تحميل بيانات الخريطة. يرجى المحاولة مرة أخرى لاحقًا.'
        }
        return render(request, 'map_view.html', error_context, status=500)


def search_city_or_fence(request): # THIS IS THE RENAMED FUNCTION
    """AJAX endpoint to search for fences by city name OR fence name."""
    try:
        query = request.GET.get('q', '').strip()
        if not query: # Return empty if query is empty
            return JsonResponse([], safe=False)
        
        # Optional: Minimum query length for backend search.
        # The frontend JS already checks for len < 2, but backend can enforce too.
        if len(query) < 2:
             return JsonResponse({'message': 'يرجى إدخال حرفين على الأقل للبحث.'}, status=400, safe=False)

        latest_status_sq = FenceStatus.objects.filter(
            fence_id=OuterRef('pk')
        ).order_by('-message_time')

        # Using Q objects for OR condition: search in 'city' OR 'name'
        fences_found = Fence.objects.filter(
            Q(city__icontains=query) | Q(name__icontains=query)
        ).annotate(
            latest_status=Subquery(latest_status_sq.values('status')[:1]),
            latest_time=Subquery(latest_status_sq.values('message_time')[:1]),
            latest_image=Subquery(latest_status_sq.values('image')[:1])
        ).values(
            'id', 'name', 'city', 'latitude', 'longitude', # Include coordinates for map interaction
            'latest_status', 'latest_time', 'latest_image'
        )[:10] # Limit to 10 results for performance and UI manageability

        results = []
        for fence in fences_found:
            try:
                lat = float(fence['latitude']) if fence['latitude'] is not None else None
                lon = float(fence['longitude']) if fence['longitude'] is not None else None
            except (ValueError, TypeError):
                lat, lon = None, None

            # Skip if coordinates are invalid, so frontend doesn't try to place a marker at null/0,0
            if lat is None or lon is None or (abs(lat) < 0.0001 and abs(lon) < 0.0001):
                continue

            results.append({
                'id': fence['id'],
                'name': fence['name'],
                'city': fence['city'] or '',
                'latitude': lat,
                'longitude': lon,
                'status': fence['latest_status'] or 'unknown',
                'message_time': fence['latest_time'].isoformat() if fence['latest_time'] else None,
                'image': fence['latest_image'] or ''
            })
        return JsonResponse(results, safe=False)

    except Exception as e:
        print(f"ERROR in search_city_or_fence: {e}")
        traceback.print_exc()
        return JsonResponse({'error': 'فشل البحث. يرجى المحاولة مرة أخرى.'}, status=500)


def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points in kilometers."""
    if None in [lat1, lon1, lat2, lon2]: return float('inf')
    try:
        lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    except (ValueError, TypeError):
        return float('inf') # Return infinity if conversion fails
    
    R = 6371  # Radius of Earth in kilometers
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = (math.sin(dLat / 2) * math.sin(dLat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dLon / 2) * math.sin(dLon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    return distance


@require_POST # Ensures this view only accepts POST requests
def get_predictions_for_location(request):
    """ API endpoint called by JS to get predictions for nearby fences. """
    try:
        data = json.loads(request.body)
        user_lat = float(data['latitude'])
        user_lon = float(data['longitude'])
        
        MAX_DISTANCE_KM = 75
        AVG_SPEED_KMH = 40
        MAX_TRAVEL_MINUTES = 360 # 6 hours

        latest_status_sq = FenceStatus.objects.filter(
            fence_id=OuterRef('pk')
        ).order_by('-message_time')

        fences_qs = Fence.objects.annotate(
            latest_status=Subquery(latest_status_sq.values('status')[:1]),
            latest_time=Subquery(latest_status_sq.values('message_time')[:1])
        ).values(
            'id', 'name', 'latitude', 'longitude', 'city',
            'latest_status', 'latest_time'
        )

        results = []
        current_time_utc = timezone.now()
 
        for fence in fences_qs:
            if fence['latitude'] is None or fence['longitude'] is None:
                continue
            try:
                fence_lat = float(fence['latitude'])
                fence_lon = float(fence['longitude'])
                if abs(fence_lat) < 0.0001 and abs(fence_lon) < 0.0001: # Skip 0,0 coordinates
                    continue
            except (ValueError, TypeError):
                continue 

            distance_km = haversine(user_lat, user_lon, fence_lat, fence_lon)
            if distance_km > MAX_DISTANCE_KM:
                continue

            travel_time_minutes = int((distance_km / AVG_SPEED_KMH) * 60) if AVG_SPEED_KMH > 0 else float('inf')
            if travel_time_minutes > MAX_TRAVEL_MINUTES:
                continue

            ai_result = predict_jam_probability_at_arrival(
                fence_id=fence['id'],
                current_time=current_time_utc,
                travel_time_minutes=travel_time_minutes
            )
            
            fence_result = {
                'id': fence['id'],
                'name': fence['name'],
                'latitude': fence_lat,
                'longitude': fence_lon,
                'city': fence['city'] or '',
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

    except json.JSONDecodeError:
        return JsonResponse({'error': 'بيانات الطلب غير صالحة (JSON).'}, status=400)
    except (KeyError, TypeError, ValueError) as e:
        return JsonResponse({'error': f'بيانات الطلب غير كاملة أو بصيغة خاطئة: {e}'}, status=400)
    except Exception as e:
        print(f"SERVER ERROR in get_predictions_for_location: {e}")
        traceback.print_exc()
        return JsonResponse({'error': 'حدث خطأ داخلي في الخادم أثناء معالجة التوقعات.'}, status=500)