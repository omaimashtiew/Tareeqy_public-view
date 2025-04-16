from django.shortcuts import render
from .models import Fence, FenceStatus
import json
from django.core.serializers.json import DjangoJSONEncoder
from datetime import datetime

class CustomJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        return super().default(obj)

def fence_status(request):
    """Display the status of fences"""
    fences = Fence.objects.all().prefetch_related('statuses')
    
    # Prepare fence data with latest status
    fence_data = []
    for fence in fences:
        latest_status = fence.statuses.order_by('-message_time').first()
        if latest_status and latest_status.status in ['open', 'closed', 'sever_traffic_jam']:
            fence_data.append({
                'name': fence.name,
                'status': latest_status.status,
                'message_time': latest_status.message_time.strftime('%Y-%m-%d %H:%M:%S'),
                'image': latest_status.image,
                'latitude': fence.latitude,
                'longitude': fence.longitude
            })
    
    context = {
        'fences': fence_data,
        'fences_json': json.dumps(fence_data, cls=CustomJSONEncoder)
    }
    return render(request, 'fences.html', context)  # Render the fences.html template with the fence data
