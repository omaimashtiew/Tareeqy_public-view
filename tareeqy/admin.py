from django.contrib import admin
from .models import Fence, FenceStatus

@admin.register(Fence)
class FenceAdmin(admin.ModelAdmin):
    list_display = ('name', 'latitude', 'longitude')
    search_fields = ('name',)

@admin.register(FenceStatus)
class FenceStatusAdmin(admin.ModelAdmin):
    list_display = ('fence', 'status', 'message_time')
    list_filter = ('status',)
    search_fields = ('fence__name',)