from telethon.sync import TelegramClient

api_id = 28313142
api_hash = "1937d577a86353af13fbb92c82f25306"
phone_number = '+970597141788'

with TelegramClient("tareeqy_session", api_id, api_hash) as client:
    client.start(phone_number)
    print("✅ Session created successfully.")
