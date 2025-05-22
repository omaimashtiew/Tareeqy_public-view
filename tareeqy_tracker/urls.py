# tareeqy_tracker/urls.py

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path("admin/", admin.site.urls),

    # 1. Redirect the absolute root of your site ('/') to the app's welcome page.
    #    This uses the namespace 'tareeqy_app' and the name 'welcome_page' from your app's urls.py.
    path('', lambda request: redirect('tareeqy_app:welcome_page', permanent=False)),

    # 2. Include your 'tareeqy' app's URLs under a prefix, e.g., '/app/'.
    #    This means all URLs from 'tareeqy.urls' will start with '/app/'.
    #    The namespace 'tareeqy_app' is crucial for using {% url %} tags.
    path('Tareeqy/app/', include('tareeqy.urls', namespace='tareeqy_app')),
] 