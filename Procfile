web: python manage.py migrate && gunicorn tareeqy_tracker.wsgi:application
listener: while true; do python tareeqy_tracker/tareeqy/telegram_listener.py; sleep 30; done