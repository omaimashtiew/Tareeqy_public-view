# tareeqy/models.py
from django.db import models

class Fence(models.Model):
    name = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    city = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.name

class FenceStatus(models.Model):
    fence = models.ForeignKey(Fence, on_delete=models.CASCADE, related_name='statuses')
    status = models.CharField(max_length=50)
    message_time = models.DateTimeField()
    image = models.CharField(max_length=255, blank=True, null=True)
    
    class Meta:
        ordering = ['-message_time']
    
    def __str__(self):
        return f"{self.fence.name} - {self.status}"