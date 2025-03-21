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

# Setting up logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API credentials and channel
API_ID = 28313142
API_HASH = "1937d577a86353af13fbb92c82f25306"
CHANNEL_USERNAME = "@ahwalaltreq"  # Replace with your channel's username

# Define Palestine time zone
PALESTINE_TZ = pytz.timezone('Asia/Gaza')  # Use 'Asia/Hebron' if needed

# Normalization mapping
NAME_MAPPING = {
    "صرة": "صره",  
    "صره": "صره",  
    "العيزريه": "العيزرية",  
    "العيزرية": "العيزرية", 
    "عين سينا": "عين سينيا",  
    "عين سينيا": "عين سينيا",  
    "زعترا": "زعترة",  
    "زعترة": "زعترة", 
    "زعتره": "زعترة", 
    "الساوية": "الساوية",
    "الساويه": "الساوية",
    "المربعه": "المربعة",  
    "المربعة": "المربعة",  
    "حواره": "حوارة",  
    "حوارة": "حوارة", 
}

def normalize_name(name):
    """Normalize a name using the NAME_MAPPING dictionary."""
    # Replace "ة" with "ه" for consistency
    name = name.replace("ة", "ه")
    normalized_name = name.strip()
    return NAME_MAPPING.get(normalized_name, normalized_name)

def normalize_names(names):
    """Normalize a list of names."""
    return list(set(normalize_name(name) for name in names))

# Async function to fetch and update fences
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
                    # Normalize the message text
                    normalized_message_text = normalize_name(message_text)
                    logger.info(f"Normalized message text: {normalized_message_text}")

                    # Search for fence names in the message
                    for fence in fences:
                        # Normalize the fence name from the database
                        normalized_fence_name = normalize_name(fence.name)
                        logger.info(f"Normalized fence name: {normalized_fence_name}")

                        # Check if the normalized fence name is in the normalized message text
                        if normalized_fence_name in normalized_message_text:
                            status = analyze_message(message_text)  # Determine the status
                            logger.info(f"Found fence: {normalized_fence_name}, Status: {status}")

                            if status != "Unknown" and normalized_fence_name not in updated_fences:
                                # Update the fence status and message time
                                await sync_to_async(update_fence_status)(fence, status, msg_date)
                                updated_fences.add(normalized_fence_name)  # Mark this fence as updated
                                logger.info(f"Updated fence: {normalized_fence_name}, Status: {status}, Message time: {msg_date}")
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


def analyze_message(text):
    """Analyze the message to determine the status of the fence."""
    text = text.lower()
    for status, keywords in settings.STATUS_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return status
    return "Unknown"

def update_fence_status(fence, status, message_time):
    """Update or create fence status in the FenceStatus model."""
    try:
        # Get the latest status for this fence
        latest_status = FenceStatus.objects.filter(fence=fence).order_by('-message_time').first()
        
        # Only create a new entry if the status has changed or if there is no previous status
        if not latest_status or latest_status.status != status:
            # Assign an image based on the status
            if status == "open":
                image = "/static/images/open.png"  # Path to the open image
            elif status == "closed":
                image = "/static/images/closed.png"  # Path to the closed image
            elif status == "sever_traffic_jam":
                image = "/static/images/traffic.png"  # Path to the traffic image
            else:
                image = None  # No image for unknown status

            # Create a new FenceStatus entry
            FenceStatus.objects.create(
                fence=fence,
                status=status,
                message_time=message_time,
                image=image  # Add the image
            )
            
            logger.info(f"Updated {fence.name} status to {status} with message time {message_time}")
        else:
            logger.info(f"No change in status for {fence.name}. Skipping update.")
    except Exception as e:
        logger.error(f"Error updating fence {fence.name}: {e}")


# Django view to trigger the fetch and update process
from django.shortcuts import render
from django.core.serializers import serialize
from .models import Fence, FenceStatus
import json

def update_fences(request):
    # Call the async function to fetch and update fence statuses
    asyncio.run(fetch_and_update_fences())

    # Fetch all fences and their latest status
    fences_data = []
    for fence in Fence.objects.all():
        latest_status = FenceStatus.objects.filter(fence=fence).order_by('-message_time').first()
        if latest_status:
            fences_data.append({
                'name': fence.name,
                'latitude': fence.latitude,
                'longitude': fence.longitude,
                'status': latest_status.status,
            })

    # Convert the fence data to JSON
    fences_json = json.dumps(fences_data)

    # Render the update_fences.html template with the fence data
    return render(request, 'update_fences.html', {'fences_json': fences_json})

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