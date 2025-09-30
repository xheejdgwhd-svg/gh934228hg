import requests
import time
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from telegram import ReplyKeyboardMarkup, KeyboardButton
import threading
import asyncio
import re
from datetime import datetime, timedelta
import json
import os

# === НАСТРОЙКИ ===
DISCORD_CHANNEL_ID = "1407975317682917457"
DISCORD_USER_TOKEN = os.getenv('DISCORD_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# === НОВЫЕ НАСТРОЙКИ ДЛЯ ПОДПИСКИ ===
CHANNEL_USERNAME = "@PlantsVersusBrainrotsSTOCK"
CHANNEL_ID = "-1003166042604"

# Растения
PLANTS_RARITY = {
    "Cactus": "RARE", "Strawberry": "RARE", "Pumpkin": "EPIC", "Sunflower": "EPIC",
    "Dragon Fruit": "LEGENDARY", "Eggplant": "LEGENDARY", "Watermelon": "MYTHIC",
    "Grape": "MYTHIC", "Cocotank": "GODLY", "Carnivorous Plant": "GODLY",
    "Mr Carrot": "SECRET", "Tomatrio": "SECRET", "Shroombino": "SECRET"
}

PLANTS_EMOJI = {
    "Cactus": "🌵", "Strawberry": "🍓", "Pumpkin": "🎃", "Sunflower": "🌻",
    "Dragon Fruit": "🐉", "Eggplant": "🍆", "Watermelon": "🍉", "Grape": "🍇",
    "Cocotank": "🥥", "Carnivorous Plant": "🌿", "Mr Carrot": "🥕",
    "Tomatrio": "🍅", "Shroombino": "🍄"
}

current_stock = {}
last_restock_time = None
last_message_id = None
user_chat_ids = set()

USERS_FILE = "users.json"

telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()
telegram_bot = telegram_app.bot

keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("🎯УЗНАТЬ СТОК🎯")]],
    resize_keyboard=True
)

async def check_subscription(user_id):
    try:
        member = await telegram_bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        else:
            return False
    except Exception as e:
        print(f"❌ Ошибка проверки подписки для пользователя {user_id}: {e}")
        return True

def create_subscription_message():
    text = """
🔒 Для доступа к стоку нужно подписаться на канал. В канале все уведомления о новостях Plants Vs Brainrots

📢 Подпишитесь на наш канал и получайте:
• Мгновенные уведомления о новом стоке
• Актуальную информацию о растениях
• Первыми узнавайте о обновлениях
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Подписаться на канал", url="https://t.me/PlantsVersusBrainrotsSTOCK")],
        [InlineKeyboardButton("✅ Проверить подписку", callback_data="check_subscription")]
    ])
    
    return text, keyboard

async def show_current_stock(user_id, context):
    print("🎯 Показываем сток пользователю после подтверждения подписки")
    
    latest_message = get_latest_discord_message()
    
    if latest_message:
        embeds = latest_message.get('embeds', [])
        for embed in embeds:
            if embed.get('title') == 'SEEDS SHOP RESTOCK!':
                message_timestamp = latest_message.get('timestamp')
                stock_data, time_info = extract_stock_info_from_embed(embed, message_timestamp)
                
                if stock_data:
                    global current_stock, last_restock_time
                    current_stock = stock_data
                    last_restock_time = time_info
                    
                    telegram_message = create_telegram_message(stock_data, time_info, is_alert=False)
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=telegram_message,
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
                    print("✅ Отправлен актуальный сток")
                    return
        
        await context.bot.send_message(
            chat_id=user_id,
            text="📭 В последнем сообщении нет стока",
            reply_markup=keyboard
        )
    else:
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Не удалось получить сообщение",
            reply_markup=keyboard
        )

async def handle_subscription_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    is_subscribed = await check_subscription(user_id)
    
    if is_subscribed:
        try:
            await query.message.delete()
        except:
            pass
        
        add_user(user_id)
        await show_current_stock(user_id, context)
        
    else:
        text, reply_markup = create_subscription_message()
        await query.edit_message_text(
            "❌ Подписка не найдена. Пожалуйста, подпишитесь на канал и попробуйте снова.\n\n" + text,
            reply_markup=reply_markup
        )

def load_users():
    global user_chat_ids
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                data = json.load(f)
                user_chat_ids = set(data.get('users', []))
                print(f"📊 Загружено {len(user_chat_ids)} пользователей")
    except Exception as e:
        print(f"❌ Ошибка загрузки пользователей: {e}")
        user_chat_ids = set()

def save_users():
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump({'users': list(user_chat_ids)}, f)
        print(f"💾 Сохранено {len(user_chat_ids)} пользователей")
    except Exception as e:
        print(f"❌ Ошибка сохранения пользователей: {e}")

def add_user(chat_id):
    if chat_id not in user_chat_ids:
        user_chat_ids.add(chat_id)
        save_users()
        print(f"👤 Добавлен новый пользователь: {chat_id}")

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

def convert_to_msk(discord_time_str):
    try:
        if "@" in discord_time_str:
            date_part, time_part = discord_time_str.split('@')
            day, month, year = date_part.strip().split('/')
            hour, minute = time_part.strip().replace('GMT', '').strip().split(':')
            
            dt_utc = datetime(int(year), int(month), int(day), int(hour), int(minute))
            dt_msk = dt_utc + timedelta(hours=3)
            return dt_msk.strftime("%d/%m/%Y %H:%M")
        else:
            return discord_time_str
    except Exception as e:
        print(f"❌ Ошибка конвертации времени: {e}")
        return discord_time_str

def extract_stock_info_from_embed(embed, message_timestamp):
    stock_data = {}
    current_time = ""
    
    author = embed.get('author', {})
    if author and 'name' in author:
        author_name = author['name']
        if "⏳" in author_name:
            discord_time = author_name.replace('⏳', '').strip()
            current_time = convert_to_msk(discord_time)
            print(f"⏰ Время из Discord: {discord_time} -> МСК: {current_time}")
    
    if not current_time:
        current_time = datetime.now().strftime("%d/%m/%Y %H:%M")
        print(f"⏰ Используем текущее время МСК: {current_time}")
    
    fields = embed.get('fields', [])
    for field in fields:
        plant_name = field.get('name', '')
        plant_value = field.get('value', '')
        
        clean_plant_name = re.sub(r'[^\w\s]', '', plant_name).strip()
        
        stock_match = re.search(r'\+\d+', plant_value)
        if stock_match:
            stock_count = int(stock_match.group(0).replace('+', ''))
            
            for known_plant in PLANTS_RARITY.keys():
                if known_plant.lower() in clean_plant_name.lower():
                    stock_data[known_plant] = stock_count
                    print(f"✅ {known_plant}: {stock_count} шт")
                    break
    
    return stock_data, current_time

def create_telegram_message(stock_data, time_info, is_alert=False):
    if not stock_data:
        return "📭 В последнем сообщении нет данных о стоке"
    
    if is_alert:
        message_text = "🔥 **НОВЫЙ СТОК ОБНАРУЖЕН!** 🔥\n\n"
    else:
        message_text = "☔️ **АКТУАЛЬНЫЙ СТОК** ☔️\n\n"
    
    message_text += f"⏰ *Обновлено: {time_info} МСК*\n\n"
    message_text += "🎯 **ДОСТУПНЫЕ РАСТЕНИЯ:**\n\n"
    
    rarity_groups = {}
    for plant, stock in stock_data.items():
        rarity = PLANTS_RARITY.get(plant)
        if rarity not in rarity_groups:
            rarity_groups[rarity] = []
        rarity_groups[rarity].append((plant, stock))
    
    rarity_order = ["RARE", "EPIC", "LEGENDARY", "MYTHIC", "GODLY", "SECRET"]
    
    for rarity in rarity_order:
        if rarity in rarity_groups and rarity_groups[rarity]:
            message_text += f"🌟 **{rarity}**\n"
            for plant, stock in rarity_groups[rarity]:
                emoji = PLANTS_EMOJI.get(plant, "🌱")
                message_text += f"├─ {emoji} {plant} ×{stock}\n"
            message_text += "\n"
    
    message_text += "⚡ Успей приобрести!\n\n"
    message_text += "📢 *Присоединяйтесь к нашему сообществу:*\n"
    message_text += "👉 Канал: @PlantsVersusBrainrotsSTOCK\n"
    message_text += "💬 Чат: @PlantsVersusBrainrotSTOCKCHAT"
    
    return message_text

async def send_telegram_alert_to_all(message):
    if not user_chat_ids:
        print("📭 Нет пользователей для рассылки")
        return
    
    sent_count = 0
    error_count = 0
    
    print(f"📤 Начинаем рассылку для {len(user_chat_ids)} пользователей...")
    
    for chat_id in list(user_chat_ids):
        try:
            is_subscribed = await check_subscription(chat_id)
            if is_subscribed:
                await telegram_bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode='Markdown'
                )
                sent_count += 1
                print(f"✅ Отправлено пользователю {chat_id}")
            else:
                print(f"⚠️ Пользователь {chat_id} не подписан на канал, уведомление не отправлено")
        except Exception as e:
            print(f"❌ Ошибка отправки пользователю {chat_id}: {e}")
            error_count += 1
            user_chat_ids.discard(chat_id)
    
    save_users()
    print(f"📊 Итог рассылки: отправлено {sent_count}, ошибок: {error_count}")

def monitor_discord():
    global current_stock, last_restock_time, last_message_id
    
    print("🕵️ Запускаем мониторинг Discord канала...")
    
    initial_message = get_latest_discord_message()
    if initial_message:
        last_message_id = initial_message['id']
        print(f"📝 Начальное сообщение: {last_message_id}")
    
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
                            
                            message_timestamp = message.get('timestamp')
                            stock_data, time_info = extract_stock_info_from_embed(embed, message_timestamp)
                            
                            if stock_data:
                                print(f"📊 ОБНАРУЖЕН НОВЫЙ СТОК! Растения: {list(stock_data.keys())}")
                                
                                current_stock = stock_data
                                last_restock_time = time_info
                                
                                telegram_message = create_telegram_message(stock_data, time_info, is_alert=True)
                                
                                print("🚀 Запускаем рассылку всем пользователям...")
                                
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                loop.run_until_complete(send_telegram_alert_to_all(telegram_message))
                                loop.close()
                                
                            else:
                                print("📭 В embed нет данных о растениях")
            
            time.sleep(10)
            
        except Exception as e:
            print(f"❌ Ошибка мониторинга: {e}")
            time.sleep(30)

async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("🎯 Запрос текущего стока от пользователя")
    
    user_id = update.effective_user.id
    is_subscribed = await check_subscription(user_id)
    
    if not is_subscribed:
        text, reply_markup = create_subscription_message()
        await update.message.reply_text(text, reply_markup=reply_markup)
        return
    
    add_user(update.message.chat_id)
    
    latest_message = get_latest_discord_message()
    
    if latest_message:
        embeds = latest_message.get('embeds', [])
        for embed in embeds:
            if embed.get('title') == 'SEEDS SHOP RESTOCK!':
                message_timestamp = latest_message.get('timestamp')
                stock_data, time_info = extract_stock_info_from_embed(embed, message_timestamp)
                
                if stock_data:
                    global current_stock, last_restock_time
                    current_stock = stock_data
                    last_restock_time = time_info
                    
                    telegram_message = create_telegram_message(stock_data, time_info, is_alert=False)
                    await update.message.reply_text(
                        telegram_message, 
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
                    print("✅ Отправлен актуальный сток")
                    return
        
        await update.message.reply_text("📭 В последнем сообщении нет стока", reply_markup=keyboard)
    else:
        await update.message.reply_text("❌ Не удалось получить сообщение", reply_markup=keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_subscribed = await check_subscription(user_id)
    
    if not is_subscribed:
        text, reply_markup = create_subscription_message()
        await update.message.reply_text(
            "👋 Добро пожаловать в бот Plants Vs Brainrots!\n\n" + text,
            reply_markup=reply_markup
        )
        return
    
    add_user(update.message.chat_id)
    
    welcome_text = """
🤖 Бот для отслеживания стока Plants Vs Brainrots

📊 Автоматически отслеживает обновления стока
🔔 Присылает уведомления при новом стоке
🎯 Нажми кнопку чтобы узнать текущий сток

📢 Наш канал: @PlantsVersusBrainrotsSTOCK
💬 Наш чат: @PlantsVersusBrainrotSTOCKCHAT
    """
    await update.message.reply_text(welcome_text, reply_markup=keyboard)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_subscribed = await check_subscription(user_id)
    
    if not is_subscribed:
        text, reply_markup = create_subscription_message()
        await update.message.reply_text(text, reply_markup=reply_markup)
        return
    
    add_user(update.message.chat_id)
    
    if update.message.text == "🎯УЗНАТЬ СТОК🎯":
        await handle_button_click(update, context)
    else:
        await update.message.reply_text("Используй кнопку для проверки стока 🎯", reply_markup=keyboard)

def run_telegram_bot():
    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    telegram_app.add_handler(CallbackQueryHandler(handle_subscription_check, pattern="check_subscription"))
    print("📱 Запускаем Telegram бота...")
    telegram_app.run_polling()

def main():
    print("🚀 Запускаем бота...")
    
    load_users()
    print(f"👥 Загружено {len(user_chat_ids)} пользователей")
    
    discord_thread = threading.Thread(target=monitor_discord, daemon=True)
    discord_thread.start()
    
    run_telegram_bot()

if __name__ == "__main__":
    main()
