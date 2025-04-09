from django.shortcuts import render
from django.http import HttpResponse
import asyncio
from .telegram_listener import start_client
from .models import Fence, FenceStatus  # Import your models here

# Make the view asynchronous
async def update_fences(request):
    """Trigger the process to fetch and update fences"""
    # Start the Telegram client asynchronously
    await start_client()  # Ensure the start_client function is async
    return render(request, 'update_fences.html')

def fence_status(request):
    """Display the status of fences"""
    fences = Fence.objects.all()  # Get all fences from the database
    statuses = FenceStatus.objects.all()  # Get all statuses from the database
    context = {
        'fences': fences,
        'statuses': statuses
    }
    return render(request, 'fences.html', context)  # Render the fences.html template with the fence data
