from django.db import models

class Fence(models.Model):
    name = models.CharField(max_length=100, unique=True)
    latitude = models.DecimalField(max_digits=20, decimal_places=15, default=0)
    longitude = models.DecimalField(max_digits=20, decimal_places=15, default=0)

    def __str__(self):
        return self.name

class FenceStatus(models.Model):
    fence = models.ForeignKey(Fence, on_delete=models.CASCADE, related_name="statuses")
    status = models.CharField(max_length=20)
    message_time = models.DateTimeField()
    image = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.fence.name} - {self.status} at {self.message_time}"
