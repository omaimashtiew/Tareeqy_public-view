web: python manage.py migrate && gunicorn tareeqy_tracker.wsgi:application
listener: bash -c "while true; do python -u tareeqy/telegram_listener.py 2>&1 | tee -a listener.log; sleep 30; done"