# models.py
from django.db import models

class Fence(models.Model):
    name = models.CharField(max_length=100, unique=True)  # Name of the fence (e.g., "صره")
    latitude = models.FloatField(default=0.0)  # Optional: Latitude for mapping
    longitude = models.FloatField(default=0.0)  # Optional: Longitude for mapping

    def __str__(self):
        return self.name

class FenceStatus(models.Model):
    fence = models.ForeignKey(Fence, on_delete=models.CASCADE, related_name="statuses")
    status = models.CharField(max_length=20)  # e.g., "open", "closed"
    message_time = models.DateTimeField()  # Timestamp of the status update
    image = models.CharField(max_length=255, blank=True, null=True)  # Optional: Image URL

    def __str__(self):
        return f"{self.fence.name} - {self.status} at {self.message_time}"