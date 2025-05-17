# tareeqy/views.py

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import OuterRef, Subquery, Q
import json
from datetime import datetime # Keep this for current_time_utc type hints
import math
import traceback

from .models import Fence, FenceStatus

# --- AI Predictor Imports (Ensure this block is correctly set up for your project) ---
try:
    # Point to the new XGBoost predictor
    from .ai_prediction.xgboost_predictor import (
        predict_wait_time, # Renamed function
        load_prediction_artifacts,
        setup_django as predictor_setup_django
    )
    print("Attempting XGBoost predictor setup and artifact load from views.py...")
    if predictor_setup_django(): # Call the setup function
        if load_prediction_artifacts(): # Load the new artifacts
            print("XGBoost predictor setup and artifact load successful from views.py.")
        else:
            print("CRITICAL: XGBoost artifact loading failed from views.py. AI features will be impacted.")
    else:
        print("CRITICAL: Django setup failed in XGBoost predictor - AI features will be unstable or disabled.")
except ImportError as e:
    print(f"CRITICAL ERROR: Cannot import XGBoost predictor module: {e}. AI features disabled.")
    # Define a fallback function if import fails
    def predict_wait_time(*args, **kwargs):
        print("Warning: XGBoost predictor called, but module was not loaded due to import error.")
        return {'success': False, 'error': 'XGBoost predictor module not available.', 'predicted_wait_minutes': None}
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
                continue 
            
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


def search_city_or_fence(request):
    """AJAX endpoint to search for fences by city name OR fence name, prioritizing starts-with."""
    try:
        query = request.GET.get('q', '').strip()
        if not query:
            return JsonResponse([], safe=False)

        # Allow search from 1 character for suggestions
        # The frontend JS will also handle this change.
        # if len(query) < 1: # Changed from 2 to 1
        #    return JsonResponse({'message': 'يرجى إدخال حرف واحد على الأقل للبحث.'}, status=400, safe=False)


        latest_status_sq = FenceStatus.objects.filter(
            fence_id=OuterRef('pk')
        ).order_by('-message_time')

        # Prioritize 'istartswith' for name, then 'icontains' for name, then city matches
        # This makes the search feel more like "search as you type from beginning"

        # Name starts with
        name_starts_with_qs = Fence.objects.filter(name__istartswith=query)
        # City starts with (less common for users to type city first, but possible)
        city_starts_with_qs = Fence.objects.filter(city__istartswith=query)
        
        # Name contains (if not already covered by starts with)
        name_contains_qs = Fence.objects.filter(name__icontains=query).exclude(name__istartswith=query)
        # City contains (if not already covered by starts with)
        city_contains_qs = Fence.objects.filter(city__icontains=query).exclude(city__istartswith=query)

        # Combine querysets, ensuring no duplicates and prioritizing
        # We use .union() but it requires same number of annotations or values.
        # A simpler way for small result sets is to fetch IDs and then re-query, or combine in Python.
        # For now, let's do a simpler combination and rely on Python to sort/limit.

        # Fetch a slightly larger pool and then sort/limit in Python if complex ordering is needed.
        # Or, use distinct and specific ordering.
        
        # More efficient approach: Annotate match type and order by it.
        # This is more advanced. Let's stick to a simpler union for now and limit results.

        # We'll combine them and use Python to ensure uniqueness and order preference.
        # This isn't the most highly performant for huge datasets but fine for modest numbers of fences.
        
        # Fetching all possible matches up to a certain limit, then refining
        # This can be inefficient if query is very generic.
        # A better way is often to use database-level ranking if available, or weighted unions.

        # Let's try a simpler approach: fetch distinct results from combined Q objects
        # and then rely on the inherent (often primary key based) ordering or add a specific order_by.
        
        fences_found_qs = Fence.objects.filter(
            Q(name__istartswith=query) | 
            Q(city__istartswith=query) |
            Q(name__icontains=query) | 
            Q(city__icontains=query)
        ).distinct().annotate(
            latest_status=Subquery(latest_status_sq.values('status')[:1]),
            latest_time=Subquery(latest_status_sq.values('message_time')[:1]),
            latest_image=Subquery(latest_status_sq.values('image')[:1])
        )
        # Order results: name starting with query, then city starting with, then name containing, then city containing
        # This requires more complex annotation or multiple queries.
        # For simplicity with current structure, we fetch and then can sort in python if needed,
        # but the database's distinct() and then slicing should be reasonably effective.
        # The frontend will receive up to 7 results.

        # To give preference:
        results_list = []
        processed_ids = set()

        # 1. Name starts with
        for f in fences_found_qs.filter(name__istartswith=query).values(
            'id', 'name', 'city', 'latitude', 'longitude',
            'latest_status', 'latest_time', 'latest_image'
        ):
            if f['id'] not in processed_ids:
                results_list.append(f)
                processed_ids.add(f['id'])
            if len(results_list) >= 7: break
        
        # 2. City starts with
        if len(results_list) < 7:
            for f in fences_found_qs.filter(city__istartswith=query).values(
                'id', 'name', 'city', 'latitude', 'longitude',
                'latest_status', 'latest_time', 'latest_image'
            ):
                if f['id'] not in processed_ids:
                    results_list.append(f)
                    processed_ids.add(f['id'])
                if len(results_list) >= 7: break

        # 3. Name contains
        if len(results_list) < 7:
            for f in fences_found_qs.filter(name__icontains=query).values(
                'id', 'name', 'city', 'latitude', 'longitude',
                'latest_status', 'latest_time', 'latest_image'
            ):
                if f['id'] not in processed_ids:
                    results_list.append(f)
                    processed_ids.add(f['id'])
                if len(results_list) >= 7: break
        
        # 4. City contains
        if len(results_list) < 7:
            for f in fences_found_qs.filter(city__icontains=query).values(
                'id', 'name', 'city', 'latitude', 'longitude',
                'latest_status', 'latest_time', 'latest_image'
            ):
                if f['id'] not in processed_ids:
                    results_list.append(f)
                    processed_ids.add(f['id'])
                if len(results_list) >= 7: break

        final_results_data = []
        for fence in results_list[:7]: # Ensure we only take up to 7
            try:
                lat = float(fence['latitude']) if fence['latitude'] is not None else None
                lon = float(fence['longitude']) if fence['longitude'] is not None else None
            except (ValueError, TypeError):
                lat, lon = None, None

            if lat is None or lon is None or (abs(lat) < 0.0001 and abs(lon) < 0.0001):
                continue

            final_results_data.append({
                'id': fence['id'],
                'name': fence['name'],
                'city': fence['city'] or '',
                'latitude': lat,
                'longitude': lon,
                'status': fence['latest_status'] or 'unknown',
                'message_time': fence['latest_time'].isoformat() if fence['latest_time'] else None,
                'image': fence['latest_image'] or ''
            })
        return JsonResponse(final_results_data, safe=False)

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
        return float('inf') 
    
    R = 6371 
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = (math.sin(dLat / 2) * math.sin(dLat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dLon / 2) * math.sin(dLon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    return distance


@require_POST 
def get_predictions_for_location(request):
    """ API endpoint called by JS to get predictions for nearby fences. """
    try:
        data = json.loads(request.body)
        user_lat = float(data['latitude'])
        user_lon = float(data['longitude'])
        
        MAX_DISTANCE_KM = 75 # Fences within this radius will be considered for prediction
        # AVG_SPEED_KMH = 40 # No longer needed for wait time prediction at current time
        # MAX_TRAVEL_MINUTES = 360 # No longer needed

        latest_status_sq = FenceStatus.objects.filter(
            fence_id=OuterRef('pk')
        ).order_by('-message_time')

        # Get all fences and their latest status
        # We are predicting wait time AT THE FENCE, not at arrival.
        # So travel time isn't an input to the model for *this* specific XGBoost model.
        fences_qs = Fence.objects.annotate(
            latest_status=Subquery(latest_status_sq.values('status')[:1]),
            latest_time=Subquery(latest_status_sq.values('message_time')[:1])
        ).values(
            'id', 'name', 'latitude', 'longitude', 'city',
            'latest_status', 'latest_time'
        )

        results = []
        current_time_utc = timezone.now() # Use a consistent time for all predictions in this request
 
        for fence in fences_qs:
            if fence['latitude'] is None or fence['longitude'] is None:
                continue
            try:
                fence_lat = float(fence['latitude'])
                fence_lon = float(fence['longitude'])
                if abs(fence_lat) < 0.0001 and abs(fence_lon) < 0.0001: 
                    continue
            except (ValueError, TypeError):
                continue 

            distance_km = haversine(user_lat, user_lon, fence_lat, fence_lon)
            if distance_km > MAX_DISTANCE_KM: # Only predict for reasonably nearby fences
                continue

            # The XGBoost model predicts current wait time at the fence.
            # It needs fence details and current time.
            # The provided XGBoost script's `predict_all_fences` uses current_time,
            # not an "arrival time".
            
            ai_result = predict_wait_time( # Call the new predictor function
                fence_id=fence['id'],
                current_time_utc=current_time_utc,
                fence_latitude=fence_lat,
                fence_longitude=fence_lon,
                fence_city=fence['city'] or "unknown", # Pass city, default to "unknown"
                current_status_str=fence['latest_status'] or 'unknown' # Pass current status
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
                # 'estimated_travel_minutes': travel_time_minutes if travel_time_minutes != float('inf') else None, # No longer primary
                
                # New prediction fields from XGBoost model
                'prediction_success': ai_result.get('success', False),
                'predicted_wait_minutes': ai_result.get('predicted_wait_minutes') if ai_result.get('success') else None,
                'prediction_error': ai_result.get('error') if not ai_result.get('success') else None,
                'prediction_debug_info': ai_result.get('debug_info') # Optional
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