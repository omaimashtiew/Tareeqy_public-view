import logging
from datetime import datetime, timedelta
from django.http import HttpResponse
from django.conf import settings
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from .models import Fence, FenceStatus
import asyncio
from asgiref.sync import sync_to_async
import pytz  # Import pytz for timezone handling

from .utils.normalization import normalize_name

# Setting up logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API credentials and channel
API_ID = 28313142
API_HASH = "1937d577a86353af13fbb92c82f25306"
CHANNEL_USERNAME = "@ahwalaltreq"  # Replace with your channel's username

# Define Palestine time zone
PALESTINE_TZ = pytz.timezone('Asia/Gaza')  # Use 'Asia/Hebron' if needed

# Async function to fetch and update fences
# views.py
async def fetch_and_update_fences():
    logger.info("fetch_and_update_fences function started")
    
    # Initialize the Telegram client
    client = TelegramClient("session_name", API_ID, API_HASH)
    await client.start()

    try:
        # Get the channel entity
        entity = await client.get_entity(CHANNEL_USERNAME)
        logger.info(f"Connected to channel: {CHANNEL_USERNAME}")
        
        # Define the time limit in Palestine time (1 hour ago from now)
        time_limit = datetime.now(PALESTINE_TZ) - timedelta(hours=1)
        logger.info(f"Time limit (Palestine time): {time_limit}")

        # Fetch the messages
        messages = await client(GetHistoryRequest(
            peer=entity,
            limit=500,  
            offset_date=None,
            offset_id=0,
            max_id=0,
            min_id=0,
            add_offset=0,
            hash=0
        ))
        logger.info(f"Fetched {len(messages.messages)} messages")

        # Fetch all fences from the database
        fences = await sync_to_async(list)(Fence.objects.all())
        logger.info(f"Fetched {len(fences)} fences from the database")

        # Track which fences have already been updated
        updated_fences = set()

        # Process messages in reverse order (newest first)
        for message in reversed(messages.messages):
            if not message.message:  # Skip if the message is None or empty
                logger.warning(f"Empty or None message: {message.id}")
                continue

            # Convert message date to Palestine time
            msg_date_utc = message.date.replace(tzinfo=pytz.UTC)  # Ensure message date is timezone-aware (UTC)
            msg_date = msg_date_utc.astimezone(PALESTINE_TZ)  # Convert to Palestine time
            logger.info(f"Message date (Palestine time): {msg_date}")
            logger.info(f"Message text: {message.message}")

            if msg_date > time_limit:  # Filter messages from the last hour
                message_text = message.message
                logger.info(f"[{msg_date}] {message_text}")

                if message_text.strip():  # If the message is not empty
                    # Search for fence names in the message
                    for fence in fences:
                        if fence.name in message_text:  # Check if the fence name is in the message
                            status = analyze_message(message_text)  # Determine the status
                            logger.info(f"Found fence: {fence.name}, Status: {status}")

                            if status != "Unknown" and fence.name not in updated_fences:
                                # Update the fence status and message time
                                await sync_to_async(update_fence_status)(fence, status, msg_date)
                                updated_fences.add(fence.name)  # Mark this fence as updated
                                logger.info(f"Updated fence: {fence.name}, Status: {status}, Message time: {msg_date}")
                            break  # Stop searching once a match is found
                else:
                    logger.warning(f"Empty message: {message.id}")
            else:
                logger.info(f"Message {message.id} is older than the time limit and will be skipped")

    except Exception as e:
        logger.error(f"Error fetching messages: {e}")
    finally:
        await client.disconnect()
        logger.info("Telegram client disconnected")

# views.py
def analyze_message(text):
    """Analyze the message to determine the status of the fence."""
    text = text.lower()
    for status, keywords in settings.STATUS_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return status
    return "Unknown"


def extract_fence_name(message_text):
    """Extract and normalize the fence name from the message text"""
    for fence_name in settings.FENCE_NAMES:
        if fence_name in message_text:
            # Normalize the fence name before returning it
            return normalize_name(fence_name)
    return None

# views.py
def update_fence_status(fence, status, message_time):
    """Update or create fence status in the FenceStatus model."""
    try:
        # Assign an image based on the status
        if status == "open":
            image = "/static/images/open.png"  # Path to the open image
        elif status == "closed":
            image = "/static/images/closed.png"  # Path to the closed image
        else:
            image = None  # No image for unknown status

        # Create a new FenceStatus entry for each status update
        FenceStatus.objects.create(
            fence=fence,
            status=status,
            message_time=message_time,
            image=image  # Add the image
        )
        
        logger.info(f"Updated {fence.name} status to {status} with message time {message_time}")
    except Exception as e:
        logger.error(f"Error updating fence {fence.name}: {e}")

# Django view to trigger the fetch and update process
def update_fences(request):
    # Call the async function to fetch and update fence statuses synchronously
    asyncio.run(fetch_and_update_fences())
    return HttpResponse("Fences have been updated successfully.")

# View to display fence data
from django.shortcuts import render

def fence_status(request):
    # Fetch all fences and their latest status, ordered by message_time (newest first)
    fence_statuses = []
    
    # Get the latest status for each fence
    for fence in Fence.objects.all():
        latest_status = FenceStatus.objects.filter(fence=fence).order_by('-message_time').first()
        if latest_status:
            fence_statuses.append({
                'name': fence.name,
                'latitude': fence.latitude,
                'longitude': fence.longitude,
                'status': latest_status.status,
                'message_time': latest_status.message_time,
                'image': latest_status.image,  # Add the image
            })
    
    # Sort the fence_statuses list by message_time (newest first)
    fence_statuses.sort(key=lambda x: x['message_time'], reverse=True)

    return render(request, 'fences.html', {'fences': fence_statuses})