import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


API_ID = 28313142 
API_HASH = "1937d577a8635af13fbb92c82f25306"  
CHANNEL_USERNAME = "@ahwalaltreq"  


DATABASE_PATH = "TareeqyDB.db"

def get_db_connection():
    return sqlite3.connect(DATABASE_PATH)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT,
            message TEXT,
            status TEXT,
            time TEXT
        )
    ''')
    conn.commit()
    conn.close()

async def fetch_recent_messages():
    init_db()
    client = TelegramClient("session_name", API_ID, API_HASH)
    await client.start()

    try:
        entity = await client.get_entity(CHANNEL_USERNAME)
        time_limit = datetime.utcnow() - timedelta(hours=2)

        messages = await client(GetHistoryRequest(
            peer=entity,
            limit=50,
            offset_date=None,
            offset_id=0,
            max_id=0,
            min_id=0,
            add_offset=0,
            hash=0
        ))

        conn = get_db_connection()
        cursor = conn.cursor()

        for message in messages.messages:
            msg_date = message.date.replace(tzinfo=None)  
            if msg_date > time_limit:
                message_text = message.message  
                logger.info(f"[{msg_date}] {message_text}")

                if message_text.strip(): 
                    status = analyze_message(message_text)
                    logger.info(f"Inserting: {CHANNEL_USERNAME}, {message_text[:50]}..., {status}, {msg_date}")

                    try:
                        cursor.execute('''
                            INSERT INTO Messages (channel, message, status, time)
                            VALUES (?, ?, ?, ?)
                        ''', (CHANNEL_USERNAME, message_text, status, msg_date.isoformat()))
                        conn.commit()
                        logger.info("Insert successful")
                    except sqlite3.Error as e:
                        logger.error(f"Database error: {e}")
                        conn.rollback()
                else:
                    logger.warning(f"Empty message: {message.id}")

        conn.close()

    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await client.disconnect()

def analyze_message(text):
    text = text.lower()
    if 'مغلق' in text or 'مواجهات' in text:
        return 'Closed'
    elif 'مفتوح' in text or 'سالك' in text:
        return 'Open'
    else:
        return 'Unknown'

if __name__ == "__main__":
    asyncio.run(fetch_recent_messages())