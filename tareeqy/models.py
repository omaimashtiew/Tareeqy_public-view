from django.db import models

class Fence(models.Model):
    name = models.CharField(max_length=100)
    status = models.CharField(max_length=20)
    message_time = models.DateTimeField(null=True, blank=True)  # Add this line

    def __str__(self):
        return self.name