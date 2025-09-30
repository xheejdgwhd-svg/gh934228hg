import requests
import time
import asyncio
import re
from datetime import datetime, timedelta
import json
import os

# Настройки Discord
DISCORD_CHANNEL_ID = "1407975317682917457"
DISCORD_USER_TOKEN = os.getenv('DISCORD_TOKEN')

def get_latest_discord_message():
    headers = {
        'Authorization': DISCORD_USER_TOKEN,
        'Content-Type': 'application/json',
    }
    
    url = f'https://discord.com/api/v9/channels/{DISCORD_CHANNEL_ID}/messages?limit=1'
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            messages = response.json()
            if messages:
                return messages[0]
        return None
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return None

def monitor_discord():
    print("🕵️ Запускаем мониторинг Discord канала...")
    
    last_message_id = None
    
    while True:
        try:
            message = get_latest_discord_message()
            
            if message:
                current_message_id = message['id']
                
                if current_message_id != last_message_id:
                    print(f"🆕 ОБНАРУЖЕНО НОВОЕ СООБЩЕНИЕ: {current_message_id}")
                    last_message_id = current_message_id
                    
                    embeds = message.get('embeds', [])
                    for embed in embeds:
                        if embed.get('title') == 'SEEDS SHOP RESTOCK!':
                            print("🎯 НАЙДЕН СТОК В EMBED!")
                            # Здесь можно добавить логику уведомлений
            
            time.sleep(10)
            
        except Exception as e:
            print(f"❌ Ошибка мониторинга: {e}")
            time.sleep(30)

if __name__ == "__main__":
    monitor_discord()
