
from django.contrib import admin
from django.urls import path, include  # *** IMPORT include ***

urlpatterns = [
    path("admin/", admin.site.urls),

    # --- THIS IS THE CORRECT WAY ---
    # Include the URL patterns from the 'tareeqy' app.
    # This makes URLs defined in 'tareeqy/urls.py' accessible from the root ('')
    path('', include('tareeqy.urls', namespace='tareeqy')),
    # --- END CORRECT WAY ---

    # --- REMOVE THE OLD, INCORRECT PATH ---
    # path('Tareeqy/', views.update_fences, name='update_fences'), # DELETE THIS LINE
    # REMOVE "from tareeqy import views" from the top if it's there.
]
