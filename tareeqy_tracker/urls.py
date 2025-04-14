from django.contrib import admin
from django.urls import path
from tareeqy import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path('Tareeqy/', views.update_fences, name='update_fences'),
]