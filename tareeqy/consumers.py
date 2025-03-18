# consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import FenceStatus

class FenceStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Accept the WebSocket connection
        await self.accept()

        # Send initial data to the client
        await self.send_initial_data()

        # Add the client to a group for real-time updates
        await self.channel_layer.group_add("fence_updates", self.channel_name)

    async def disconnect(self, close_code):
        # Remove the client from the group
        await self.channel_layer.group_discard("fence_updates", self.channel_name)

    async def send_initial_data(self):
        # Fetch the latest fence statuses
        fences = FenceStatus.objects.all().order_by('-message_time')
        fence_data = [
            {
                'name': fence.fence.name,
                'status': fence.status,
                'message_time': fence.message_time.strftime('%Y-%m-%d %H:%M:%S'),
                'image': fence.image,
            }
            for fence in fences
        ]

        # Send the data to the client
        await self.send(text_data=json.dumps({
            'type': 'initial_data',
            'fences': fence_data,
        }))

    async def fence_update(self, event):
        # Send real-time updates to the client
        await self.send(text_data=json.dumps(event))