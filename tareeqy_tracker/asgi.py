import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path
from tareeqy.consumers import FenceConsumer

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tareeqy_tracker.settings")

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": URLRouter([
        path("ws/fences/", FenceConsumer.as_asgi()),  # WebSocket route
    ]),
})