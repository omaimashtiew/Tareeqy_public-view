from django.contrib import admin
from tareeqy import views 
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path('update_fences/', views.update_fences, name='update_fences'),
    path('fence_status/', views.fence_status, name='fence_status'), 

]
