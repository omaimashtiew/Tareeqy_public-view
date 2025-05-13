#newrecord.py
import asyncio
from telethon.sync import TelegramClient
import os
import sys
from datetime import datetime
from django.utils import timezone
from asgiref.sync import sync_to_async

# إعداد Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tareeqy_tracker.settings")

import django
django.setup()

from django.conf import settings
from tareeqy.models import FenceStatus, Fence


# بيانات من settings.py
api_id = settings.TELEGRAM_API_ID
api_hash = settings.TELEGRAM_API_HASH
channel_username = settings.TELEGRAM_CHANNEL
STATUS_KEYWORDS = settings.STATUS_KEYWORDS

# الحواجز المستهدفة
TARGET_KEYWORDS = [
    "اريحا", "العيزرية", "عناتا", "النشاش", "روابي", "سلفيت", "بزاريا", "كفر لاقف",
    "كانا", "شافي شمرون", "عقربا", "بيت جالا", "جماعين", "الخضر", "بيت ليد", "النفق",
    "صره", "دير شرف", "عين سينيا", "جبع", "المربعه", "بورين", "عورتا", "الحمرا",
    "الكونتينر", "يتسهار", "زعترة", "الفندق", "النبي يونس", "ترمسعيا", "قلنديا",
    "الزعيم", "حواره", "الباذان", "النبي صالح", "حارس", "بديا", "الساوية"
]

start_date = timezone.make_aware(datetime(2025, 5, 13))
end_date = timezone.make_aware(datetime(2025, 5, 12))


def classify_status(text):
    for status, keywords in STATUS_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return status
    return None
# أضف هذا
@sync_to_async
def get_fence_by_keyword(keyword):
    return Fence.objects.filter(name__icontains=keyword).first()

def get_status_image(status):
    if status == "open":
        return "/static/images/open.png"
    elif status == "closed":
        return "/static/images/closed.png"
    elif status == "sever_traffic_jam":
        return "/static/images/traffic.png"
    return ""


# استخدام sync_to_async
@sync_to_async
def save_fence_status(fence_id, status, message_time, image):
    try:
        # تحقق مما إذا كانت الحالة موجودة مسبقًا
        exists = FenceStatus.objects.filter(
            fence_id=fence_id,
            status=status,
            message_time=message_time
        ).exists()

        if exists:
            print(f"⏩ تم تجاهل التكرار: الحاجز {fence_id} - الحالة '{status}' - الوقت {message_time}")
            return

        # إذا لم تكن موجودة، احفظها
        FenceStatus.objects.create(
            fence_id=fence_id,
            status=status,
            message_time=message_time,
            image=image
        )
        #print(f"✔️ تم حفظ حالة '{status}' لحاجز {fence_id} في {message_time}")
    except Exception as e:
        print(f"⚠️ خطأ أثناء الحفظ: {e}")



async def fetch_messages():
    async with TelegramClient("session", api_id, api_hash) as client:
        entity = await client.get_entity(channel_username)

        async for message in client.iter_messages(entity, offset_date=end_date, reverse=True):
            if message.date < start_date:
                break
            if not message.message:
                continue

            message_text = message.message

            for keyword in TARGET_KEYWORDS:
                if keyword in message_text:
                    status = classify_status(message_text)
                    if status:
                        fence = await get_fence_by_keyword(keyword)
                        if fence:
                            await save_fence_status(
                                fence.id, status, message.date, get_status_image(status)
                            )


if __name__ == "__main__":
    asyncio.run(fetch_messages())
