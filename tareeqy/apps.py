from django.apps import AppConfig
import asyncio
import threading
import logging
import os

logger = logging.getLogger(__name__)

class TareeqyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tareeqy'

    def ready(self):
        """Run when Django starts"""
        if not hasattr(self, '_already_run'):
            self._already_run = True

            # Only run listener when server is started (not during migrations or shell)
            if os.environ.get('RUN_MAIN') == 'true' or 'gunicorn' in os.environ.get('SERVER_SOFTWARE', ''):
                def run_listener():
                    loop = None
                    try:
                        # Windows compatibility — must be set before new_event_loop
                        if os.name == 'nt':
                            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

                        # Create and set a new event loop for this thread
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                        logger.info("Starting Telegram listener...")

                        # Now it's safe to import anything that might use asyncio
                        from tareeqy.telegram_listener import start_client

                        # Run the async Telegram client
                        loop.run_until_complete(start_client())

                    except Exception as e:
                        logger.error(f"Telegram listener error: {e}")
                    finally:
                        if loop:
                            try:
                                loop.close()
                            except Exception as e:
                                logger.error(f"Error closing loop: {e}")

                thread = threading.Thread(
                    target=run_listener,
                    daemon=True,
                    name="TelegramListenerThread"
                )
                thread.start()
