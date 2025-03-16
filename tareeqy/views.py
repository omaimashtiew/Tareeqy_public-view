import logging
from datetime import datetime, timedelta
from django.http import HttpResponse
from django.conf import settings
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from .models import Fence
import asyncio
from asgiref.sync import sync_to_async

# Setting up logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API credentials and channel
API_ID = 28313142
API_HASH = "1937d577a86353af13fbb92c82f25306"
CHANNEL_USERNAME = "@ahwalaltreq"  # Replace with your channel's username

# Async function to fetch and update fences
async def fetch_and_update_fences():
    # Initialize the Telegram client
    client = TelegramClient("session_name", API_ID, API_HASH)
    await client.start()

    try:
        # Get the channel entity
        entity = await client.get_entity(CHANNEL_USERNAME)
        time_limit = datetime.utcnow() - timedelta(hours=20)

        # Fetch the messages
        messages = await client(GetHistoryRequest(
            peer=entity,
            limit=1000,  
            offset_date=None,
            offset_id=0,
            max_id=0,
            min_id=0,
            add_offset=0,
            hash=0
        ))

        # Dictionary to store the latest status for each fence
        latest_fence_updates = {}

        # Process messages in chronological order (oldest first)
        for message in messages.messages:
            msg_date = message.date.replace(tzinfo=None)  # Remove timezone info
            if msg_date > time_limit:  # Filter messages from the last 20 hours
                message_text = message.message
                logger.info(f"[{msg_date}] {message_text}")

                if message_text.strip():  # If the message is not empty
                    # Extract fence name and status
                    fence_name = extract_fence_name(message_text)
                    status = analyze_message(message_text)

                    if fence_name and status != "Unknown":
                        # Store the latest status and message time for each fence
                        latest_fence_updates[fence_name] = (status, msg_date)
                    else:
                        logger.warning(f"No valid fence name or status found in message: {message_text[:50]}...")
                else:
                    logger.warning(f"Empty message: {message.id}")

        # Update the database with the latest status for each fence
        for fence_name, (status, msg_date) in latest_fence_updates.items():
            await sync_to_async(update_fence_status)(fence_name, status, msg_date)

    except Exception as e:
        logger.error(f"Error fetching messages: {e}")
    finally:
        await client.disconnect()

def analyze_message(text):
    """Analyze the message to determine the status of the fence"""
    text = text.lower()
    for status, keywords in settings.STATUS_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return status
    return "Unknown"

def extract_fence_name(message_text):
    """Extract the fence name from the message text"""
    for fence_name in settings.FENCE_NAMES:
        if fence_name in message_text:
            return fence_name
    return None

def update_fence_status(fence_name, status, message_time):
    """Update or create fence status in the database"""
    try:
        fence, created = Fence.objects.get_or_create(name=fence_name)
        fence.status = status
        fence.message_time = message_time  # Save the message timestamp
        fence.save()
        logger.info(f"Updated {fence_name} status to {status} with message time {message_time}")
    except Exception as e:
        logger.error(f"Error updating fence {fence_name}: {e}")

# Django view to trigger the fetch and update process
def update_fences(request):
    # Call the async function to fetch and update fence statuses synchronously
    asyncio.run(fetch_and_update_fences())
    return HttpResponse("Fences have been updated successfully.")

# View to display fence data
from django.shortcuts import render

def fence_status(request):
    fences = Fence.objects.all().order_by('-message_time')  # Sort by message_time in descending order
    return render(request, 'fences.html', {'fences': fences})