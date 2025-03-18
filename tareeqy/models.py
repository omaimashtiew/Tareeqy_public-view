from django.db import models

class Fence(models.Model):
    name = models.CharField(max_length=100)
    latitude = models.FloatField(default=0.0)  # Default value for latitude
    longitude = models.FloatField(default=0.0)  # Default value for longitude

    def __str__(self):
        return self.name

    



class FenceStatus(models.Model):
    fence = models.ForeignKey(Fence, on_delete=models.CASCADE, related_name="statuses")
    status = models.CharField(max_length=20)  # e.g., "Active", "Inactive"
    message_time = models.DateTimeField(auto_now_add=True)  # Stores when the status changed

    def __str__(self):
        return f"{self.fence.name} - {self.status} at {self.message_time}"

