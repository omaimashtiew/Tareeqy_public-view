import os
import sys
from pathlib import Path
import logging
import hashlib
import pytz
import re
from fuzzywuzzy import fuzz, process
from telethon import TelegramClient, events
from asgiref.sync import sync_to_async
from django.conf import settings
from datetime import datetime
import time
from telethon.errors import RPCError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# إعداد المسارات والبيئة
BASE_DIR = Path(__file__).resolve().parent.parent  # يشير إلى: tareeqy_tracker
sys.path.insert(0, str(BASE_DIR))  # Add path where manage.py and settings.py are

print(f"🟢 BASE_DIR: {BASE_DIR}")
print(f"🟢 Python Path: {sys.path}")

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tareeqy_tracker.settings')

logger.info(f"🟢 BASE_DIR: {BASE_DIR}")
logger.info(f"🟢 Python Path: {sys.path}")

try:
    import django
    django.setup()
    logger.info("✅ تم تحميل إعدادات Django بنجاح")
except Exception as e:
    logger.info(f"🔥 خطأ في إعدادات Django: {e}")
    logger.info("🔴 تأكد من:")
    logger.info("1. وجود ملف settings.py في tareeqy_tracker/tareeqy_tracker/")
    logger.info("2. وجود __init__.py في كل مجلد")
    raise

# استيرادات بعد إعداد Django
from tareeqy.models import Fence, FenceStatus, TelegramMessage

API_ID = settings.TELEGRAM_API_ID
API_HASH = settings.TELEGRAM_API_HASH
CHANNEL_USERNAME = settings.TELEGRAM_CHANNEL

print(f"✅ Current directory: {os.getcwd()}")
print(f"✅ Script path: {os.path.abspath(__file__)}")
print(f"✅ Session path: {os.path.abspath('tareeqy/tareeqy_session')}")

PALESTINE_TZ = pytz.timezone('Asia/Gaza')
COMMON_PREFIXES = r'^(ال|ل|لل|بال|ول|في|عن|من|عند|وال)'

SESSION_PATH = os.path.join(BASE_DIR,"tareeqy_tracker","tareeqy","tareeqy_session")
os.makedirs(os.path.dirname(SESSION_PATH), exist_ok=True)  # تأكد أن المجلد موجود

client = TelegramClient(SESSION_PATH, API_ID, API_HASH)

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
    for status, keywords in settings.STATUS_KEYWORDS.items():
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
        parts = [p.strip() for p in re.split(r'[،\.\n]', normalized_msg) if p.strip()]
    else:
        parts = [normalized_msg]
    
    for part in parts:
        # 1. Exact matches
        for norm_name, fence in fence_map.items():
            if norm_name in part:
                found.add(fence)
        
        # 2. Fuzzy matching if no exact found
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

def update_fence_status(fence, status, message_time, telegram_message):
    """Always create new status record for history linked to TelegramMessage"""
    try:
        image = {
            "open": "/static/images/open.png",
            "closed": "/static/images/closed.png",
            "sever_traffic_jam": "/static/images/traffic.png"
        }.get(status)
        
        FenceStatus.objects.create(
            fence=fence,
            status=status,
            message_time=message_time,
            image=image,
            telegram_message=telegram_message
        )
        logger.info(f"Recorded {fence.name} status: {status} at {message_time}")
    except Exception as e:
        logger.error(f"Error updating {fence.name}: {e}")


def get_message_hash(text):
    """Compute sha256 hash of message text"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

async def process_new_message(message):
    if message and message.text:
        try:
            msg_date = message.date.replace(tzinfo=pytz.UTC).astimezone(PALESTINE_TZ)
            message_text = message.text
            status = analyze_message(message_text)
            msg_hash = get_message_hash(message_text)

            obj, created = await sync_to_async(TelegramMessage.objects.update_or_create)(
                message_id=message.id,
                defaults={
                    'text': message_text,
                    'message_time': msg_date,
                    'source': CHANNEL_USERNAME,
                    'hash': msg_hash,
                    'is_modified': False,
                    'checked_at': None,
                }
            )

            if status != "Unknown":
                fences = await sync_to_async(list)(Fence.objects.all())
                matching_fences = await sync_to_async(find_fences_in_message)(message_text, fences)

                for fence in matching_fences:
                    await sync_to_async(update_fence_status)(fence, status, msg_date, obj)

        except Exception as e:
            logger.error(f"Error processing message: {e}")


@client.on(events.NewMessage(chats=CHANNEL_USERNAME))
async def new_message_handler(event):
    logger.info(f"📩 New message received: {event.message.text[:50]}...")  # جزء من الرسالة للتأكد
    await process_new_message(event.message)

async def start_client():
    while True:
        try:
            await client.connect()
            if not await client.is_user_authorized():
                logger.info("🔴 جلسة التليجرام غير مصرّحة! تأكد من تسجيل الدخول أولاً.")
                return
            
            logger.info("✅ تم الاتصال بنجاح وجاري الاستماع للرسائل...")
            print("✅ Telegram client connected")

            await client.run_until_disconnected()
            
        except RPCError as e:
            logger.info(f"🔴 خطأ في الاتصال: {e} - جاري إعادة المحاولة خلال 30 ثانية...")
            await client.disconnect()
            time.sleep(30)
            
        except Exception as e:
            logger.info(f"🔥 خطأ غير متوقع: {e}")
            await client.disconnect()
            time.sleep(60)

if __name__ == "__main__":
    import asyncio
    asyncio.run(start_client())