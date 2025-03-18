from django.db import models

# models.py

from .utils.normalization import normalize_name  # Import the normalization utility

class Fence(models.Model):
    name = models.CharField(max_length=100)
    latitude = models.FloatField(default=0.0)  # Default value for latitude
    longitude = models.FloatField(default=0.0)  # Default value for longitude

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Normalize the name before saving
        self.name = normalize_name(self.name)
        super().save(*args, **kwargs)


class FenceStatus(models.Model):
    fence = models.ForeignKey(Fence, on_delete=models.CASCADE, related_name="statuses")
    status = models.CharField(max_length=20)  # e.g., "open", "closed"
    message_time = models.DateTimeField(auto_now_add=True)  # Stores when the status changed
    image = models.CharField(max_length=255, blank=True, null=True)  # URL or path to the image

    def __str__(self):
        return f"{self.fence.name} - {self.status} at {self.message_time}"
