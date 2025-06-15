from django.db import models

class Fence(models.Model):
    name = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    city = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.name


class FenceStatus(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('sever_traffic_jam', 'Severe Traffic Jam'),
    ]

    fence = models.ForeignKey(Fence, on_delete=models.CASCADE, related_name='statuses')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    message_time = models.DateTimeField()
    image = models.CharField(max_length=255, blank=True, null=True)
    telegram_message = models.ForeignKey('TelegramMessage', on_delete=models.CASCADE, null=True, blank=True)


    class Meta:
        ordering = ['-message_time']
        unique_together = ('fence', 'message_time')  # يمنع تكرار الحالة لنفس الوقت والموقع

    def __str__(self):
        return f"{self.fence.name} - {self.status}"


class SecretData(models.Model):
    text = models.TextField()

    def __str__(self):
        return self.text


class TelegramMessage(models.Model):
    message_id = models.BigIntegerField(primary_key=True)
    text = models.TextField()
    message_time = models.DateTimeField()
    source = models.CharField(max_length=255, blank=True, null=True)  # مثل اسم القناة أو المستخدم
    hash = models.CharField(max_length=64)  # sha256 hash من نص الرسالة
    is_modified = models.BooleanField(default=False)  # علم لو تم تعديل الرسالة لاحقًا
    checked_at = models.DateTimeField(null=True, blank=True)  # آخر وقت تم التحقق منه

    def __str__(self):
        return f"Message {self.message_id} at {self.message_time}"
