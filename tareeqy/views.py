from django.shortcuts import render

from .models import Welcome

def welcome_view(request):
    # Fetch the first welcome message from the database
    welcome_message = Welcome.objects.first()

    # Pass the message to the template
    return render(request, 'welcome.html', {'welcome_message': welcome_message})