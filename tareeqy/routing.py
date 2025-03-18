# routing.py

from django.urls import path
from .consumers import FenceStatusConsumer

websocket_urlpatterns = [
    path('ws/fences/', FenceStatusConsumer.as_asgi()),
]