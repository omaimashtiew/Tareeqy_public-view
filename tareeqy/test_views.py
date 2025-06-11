from django.http import HttpResponse
from tareeqy.models import FenceStatus

def show_latest_status(request):
    fs = FenceStatus.objects.last()
    return HttpResponse(f"Encrypted: {fs._status}<br>Decrypted: {fs.status}")