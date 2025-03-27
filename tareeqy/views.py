
import logging
from datetime import datetime, timedelta
from django.http import HttpResponse
from django.conf import settings
from django.db.models import Max  # Added missing import
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from .models import Fence, FenceStatus
import asyncio
from asgiref.sync import sync_to_async
import pytz 
import re
from fuzzywuzzy import fuzz
from fuzzywuzzy import process

# Setting up logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API credentials and channel
API_ID = 28313142
API_HASH = "1937d577a86353af13fbb92c82f25306"
CHANNEL_USERNAME = "@ahwalaltreq"

# Define Palestine time zone
PALESTINE_TZ = pytz.timezone('Asia/Gaza')
COMMON_PREFIXES = r'^(ال|ل|لل|بال|ول|في|عن|من|عند|وال)'

def normalize_text(text):
    """Normalize Arabic text for matching"""
    if not text:
        return ""
    
    text = re.sub(COMMON_PREFIXES, '', text.strip())
    text = text.replace("ة", "ه")
    text = text.replace("أ", "ا")
    text = text.replace("إ", "ا")
    text = text.replace("آ", "ا")
    return text.strip()

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

def find_fences_in_message(message_text, fences):
    """
    Find ALL fences mentioned in a message, handling both short and long messages.
    Returns list of matched Fence objects.
    """
    fence_map = {normalize_text(f.name): f for f in fences}
    found = set()
    normalized_msg = normalize_text(message_text)
    
    # Split message into meaningful parts if it's long
    if len(normalized_msg) > 100:
        # Split by common Arabic separators (comma, period, newline)
        parts = [p.strip() for p in re.split(r'[،\.\n]', normalized_msg) if p.strip()]
    else:
        parts = [normalized_msg]
    
    # Process each part separately
    for part in parts:
        # 1. First try exact matches in this part
        for norm_name, fence in fence_map.items():
            if norm_name in part:
                found.add(fence)
        
        # 2. If no exact matches, try fuzzy matching for this part
        if not found:
            matches = process.extract(
                part,
                fence_map.keys(),
                scorer=fuzz.token_set_ratio,
                limit=3
            )
            for match, score in matches:
                if score >= 70:
                    found.add(fence_map[match])
    
    return list(found)

async def fetch_and_update_fences():
    logger.info("fetch_and_update_fences function started")
    client = TelegramClient("session_name", API_ID, API_HASH)
    await client.start()

    try:
        entity = await client.get_entity(CHANNEL_USERNAME)
        time_limit = datetime.now(PALESTINE_TZ) - timedelta(hours=1)
        
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
        
        fences = await sync_to_async(list)(Fence.objects.all())
        processed_messages = 0
        matched_messages = 0
        
        for message in reversed(messages.messages):
            if not message.message:
                continue
                
            processed_messages += 1  # Moved inside message processing loop
            msg_date = message.date.replace(tzinfo=pytz.UTC).astimezone(PALESTINE_TZ)
            if msg_date > time_limit:
                message_text = message.message
                status = analyze_message(message_text)
                
                if status != "Unknown":
                    matching_fences = await sync_to_async(find_fences_in_message)(
                        message_text,
                        fences
                    )
                    
                    if matching_fences:  # Only count if we found matches
                        matched_messages += len(matching_fences)
                        for fence in matching_fences:
                            await sync_to_async(update_fence_status)(
                                fence, status, msg_date
                            )
                    else:
                        logger.warning(f"No fence matched for message: {message_text}")
        
        logger.info(
            f"Processed {processed_messages} messages, "
            f"matched {matched_messages} fences ({matched_messages/max(1,processed_messages)*100:.1f}%)"
        )
        
    except Exception as e:
        logger.error(f"Error in fetch_and_update_fences: {str(e)}")
    finally:
        await client.disconnect()

def analyze_message(text):
    """Analyze the message to determine the status of the fence."""
    text = text.lower()
    for status, keywords in settings.STATUS_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return status
    return "Unknown"

def update_fence_status(fence, status, message_time):
    """Always create new status record for history"""
    try:
        # Assign image based on status
        image = {
            "open": "/static/images/open.png",
            "closed": "/static/images/closed.png",
            "sever_traffic_jam": "/static/images/traffic.png"
        }.get(status)
        
        FenceStatus.objects.create(
            fence=fence,
            status=status,
            message_time=message_time,
            image=image
        )
        logger.info(f"Recorded {fence.name} status: {status} at {message_time}")
    except Exception as e:
        logger.error(f"Error updating {fence.name}: {e}")


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
    # Get only the most recent status for each fence
    latest_statuses = FenceStatus.objects.filter(
        id__in=FenceStatus.objects.values('fence')
            .annotate(max_id=Max('id'))
            .values('max_id')
    ).select_related('fence')
    
    fence_statuses = [{
        'name': status.fence.name,
        'latitude': status.fence.latitude,
        'longitude': status.fence.longitude,
        'status': status.status,
        'message_time': status.message_time,
        'image': status.image,
    } for status in latest_statuses]
    
    return render(request, 'fences.html', {'fences': fence_statuses})