from django.core.management.base import BaseCommand
from django.core.mail import send_mail, BadHeaderError
from django.conf import settings
from tareeqy.models import TelegramMessage
import hashlib
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Check if any Telegram messages have been modified (based on SHA256 hash)'

    def handle(self, *args, **kwargs):
        modified = 0
        total = 0
        modified_ids = []

        for msg in TelegramMessage.objects.all():
            total += 1
            current_hash = hashlib.sha256(msg.text.encode()).hexdigest()
            if current_hash != msg.hash:
                modified += 1
                modified_ids.append(str(msg.message_id))
                self.stdout.write(self.style.WARNING(f"⚠️ Message ID {msg.message_id} تم تعديله!"))

        self.stdout.write(self.style.SUCCESS(f"✅ تم فحص {total} رسالة. عدد الرسائل المعدّلة: {modified}"))

        if modified > 0:
            subject = 'تحذير: تم تعديل رسائل Telegram'
            message = f'⚠️ تم اكتشاف {modified} رسالة معدلة من أصل {total}.\nIDs: {", ".join(modified_ids)}'
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = settings.ADMINS_EMAILS

            send_mail(subject, message, from_email, recipient_list)
