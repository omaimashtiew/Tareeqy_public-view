import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import Fence

class FenceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        await self.send_fence_data()

    async def send_fence_data(self):
        fences = await sync_to_async(list)(Fence.objects.all().order_by('-message_time'))
        fence_data = [
            {"name": f.name, "status": f.status, "message_time": f.message_time.strftime('%Y-%m-%d %H:%M:%S')}
            for f in fences
        ]
        await self.send(text_data=json.dumps({"fences": fence_data}))

    async def disconnect(self, close_code):
        pass
