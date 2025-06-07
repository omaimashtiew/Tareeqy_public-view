web: python manage.py migrate && gunicorn tareeqy_tracker.wsgi:application
listener: cd tareeqy_tracker && while true; do python -u tareeqy/telegram_listener.py 2>&1; sleep 30; done