# tareeqy/urls.py
from django.urls import path
from . import views
from django.shortcuts import redirect

app_name = 'tareeqy_app' # MUST MATCH an eventual namespace
 
urlpatterns = [
    path('welcome/', views.welcome_view, name='welcome_page'),
    path('map/', views.map_view, name='map_page'), # This name is used by {% url %}
    path('', lambda request: redirect('tareeqy_app:welcome_page', permanent=False), name='app_root_redirect'),
    # ... your API URLs ...
    path('api/get_predictions/', views.get_predictions_for_location, name='api_get_predictions'),
    path('api/search_city_or_fence/', views.search_city_or_fence, name='api_search_city_or_fence'),
    path('api/shortest-wait-by-city/', views.api_shortest_wait_by_city, name='api_shortest_wait_by_city'),

    
]