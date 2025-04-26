# tareeqy/urls.py

from django.urls import path
# Import views from the current app directory (tareeqy/views.py)
from . import views

app_name = 'tareeqy'

urlpatterns = [
    # Path for the main map page view.
    # Since it's included at '', this handles http://127.0.0.1:8000/
    # Make sure 'views.map_view' exists in views.py
    path('', views.map_view, name='map_view'),

    # Path for the prediction API endpoint
    # This handles http://127.0.0.1:8000/api/get_predictions/
    path('api/get_predictions/', views.get_predictions_for_location, name='get_fence_predictions'),
]