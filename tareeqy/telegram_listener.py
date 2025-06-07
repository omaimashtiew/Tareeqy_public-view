import logging
import asyncio
import sys
import os
from pathlib import Path

# أضف مسار المشروع إلى sys.path
BASE_DIR = Path(__file__).resolve().parent.parent  # تغيير من parent.parent.parent إلى parent.parent
sys.path.insert(0, str(BASE_DIR))  # استخدام insert بدلاً من append

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tareeqy_tracker.settings')

import django
django.setup()

# بقية الاستيرادات بعد setup()
from datetime import datetime
import pytz
import re
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
from telethon import TelegramClient, events
from asgiref.sync import sync_to_async
from django.conf import settings

from tareeqy.models import Fence, FenceStatus


# Setting up logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from django.conf import settings
API_ID = settings.TELEGRAM_API_ID
API_HASH = settings.TELEGRAM_API_HASH
CHANNEL_USERNAME = settings.TELEGRAM_CHANNEL

# Define Palestine time zone
PALESTINE_TZ = pytz.timezone('Asia/Gaza')
COMMON_PREFIXES = r'^(ال|ل|لل|بال|ول|في|عن|من|عند|وال)'

# Initialize the Telegram Client
client = TelegramClient("tareeqy_tracker/tareeqy_session", API_ID, API_HASH)

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

def analyze_message(text):
    """Analyze the message to determine the status of the fence."""
    text = text.lower()
    for status, keywords in settings.STATUS_KEYWORDS.items():  # Use settings from Django
        for keyword in keywords:
            if keyword in text:
                return status
    return "Unknown"

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

# Event handler for new messages
# telegram_listener.py
async def process_new_message(message):
    """Handle incoming messages."""
    if message and message.text:
        try:
            msg_date = message.date.replace(tzinfo=pytz.UTC).astimezone(PALESTINE_TZ)
            message_text = message.text
            status = analyze_message(message_text)
            
            if status != "Unknown":
                fences = await sync_to_async(list)(Fence.objects.all())
                matching_fences = await sync_to_async(find_fences_in_message)(message_text, fences)
                
                for fence in matching_fences:
                    await sync_to_async(update_fence_status)(fence, status, msg_date)
                    logger.info(f"Updated {fence.name} to {status} at {msg_date}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            
# Set up the event handler to listen for new messages
@client.on(events.NewMessage(chats=CHANNEL_USERNAME))
async def new_message_handler(event):
    await process_new_message(event)


async def start_client():
    try:
        print("🟢 Entering start_client()")
        logger.info("Attempting to start Telegram client")
        
        # تحقق من اتصال العميل أولاً
        print("🟠 Attempting client.connect()")
        await client.connect()
        print("🟢 Client connected")
        
        # تحقق من المصادقة
        if not await client.is_user_authorized():
            error_msg = "Client is not authorized. Please login first."
            print(f"🔴 {error_msg}")
            logger.error(error_msg)
            return
            
        print("🟢 Client is authorized")
        logger.info("Client is authorized")
        
        # تحقق من القناة
        try:
            entity = await client.get_entity(CHANNEL_USERNAME)
            success_msg = f"Successfully accessed channel: {entity.title}"
            print(f"✅ {success_msg}")
            logger.info(success_msg)
        except Exception as e:
            error_msg = f"Cannot access channel {CHANNEL_USERNAME}: {e}"
            print(f"🔴 {error_msg}")
            logger.error(error_msg)
            return
            
        print("✅ Telegram Listener is UP and running")
        logger.info("Telegram listener is UP and listening for new messages")
        await client.run_until_disconnected()
        
    except Exception as e:
        error_msg = f"Telegram client critical error: {e}"
        print(f"🔥 {error_msg}")
        logger.error(error_msg, exc_info=True)
        raise

# Start the client
if __name__ == "__main__":
    asyncio.run(start_client())
