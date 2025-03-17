from django.urls import path
from .consumers import FenceConsumer

websocket_urlpatterns = [
    path("ws/fences/", FenceConsumer.as_asgi()),
]
