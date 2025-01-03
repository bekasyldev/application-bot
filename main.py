import telebot
from telebot import types
import re
import logging
from translation import TEXTS
from excel_service import ExcelService
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Initialize bot
bot = telebot.TeleBot(os.getenv('TELEGRAM_BOT_TOKEN'))

def load_admins():
    """Load admin IDs from file"""
    try:
        with open('admins.json', 'r') as f:
            return set(json.load(f))
    except FileNotFoundError:
        # Create file with initial admin
        admin_ids = {os.getenv('ADMIN_ID')}  # Your initial admin ID
        save_admins(admin_ids)
        return admin_ids

def save_admins(admin_ids):
    """Save admin IDs to file"""
    with open('admins.json', 'w') as f:
        json.dump(list(admin_ids), f)

# Initialize admins set
ADMIN_IDS = load_admins()

# Initialize excel service
excel_service = ExcelService()

# Update is_admin function
def is_admin(user_id):
    """Check if user is admin"""
    return user_id in ADMIN_IDS

# Update admin keyboard function
def create_admin_keyboard():
    """Create keyboard for admin"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(
        types.KeyboardButton("✅ Подтвердить пользователя"),
        types.KeyboardButton("➕ Добавить админа")
    )
    keyboard.add(
        types.KeyboardButton("👥 Список админов")
    )
    return keyboard

# Update admin message handler
def handle_admin_messages(message):
    """Handle admin messages"""
    chat_id = message.chat.id
    
    if message.text == "✅ Подтвердить пользователя":
        admin_state[chat_id] = 'waiting_for_id'
        bot.send_message(
            chat_id,
            "Введите ID операции для подтверждения:"
        )
        return
    
    elif message.text == "➕ Добавить админа":
        admin_state[chat_id] = 'waiting_for_admin_id'
        bot.send_message(
            chat_id,
            "Введите Telegram ID нового администратора:"
        )
        return
        
    elif message.text == "👥 Список админов":
        show_admin_list(message)
        return
        
    if admin_state.get(chat_id) == 'waiting_for_id':
        process_admin_confirmation(message)
        return
        
    if admin_state.get(chat_id) == 'waiting_for_admin_id':
        process_add_admin(message)
        return

def process_add_admin(message):
    """Process adding new admin"""
    chat_id = message.chat.id
    try:
        new_admin_id = int(message.text.strip())
        if new_admin_id in ADMIN_IDS:
            bot.reply_to(message, "Этот пользователь уже является администратором.")
            admin_state[chat_id] = None
            return
            
        ADMIN_IDS.add(new_admin_id)
        save_admins(ADMIN_IDS)
        
        # Notify current admin
        bot.reply_to(
            message, 
            f"✅ Новый администратор (ID: {new_admin_id}) успешно добавлен"
        )
        
        # Try to notify new admin
        try:
            bot.send_message(
                new_admin_id,
                "Вам были предоставлены права администратора. Используйте /start для начала работы.",
            )
        except Exception as e:
            logger.error(f"Failed to notify new admin: {e}")
            bot.reply_to(
                message,
                "Примечание: Не ��далось отправить уведомление новому администратору. "
                "Возможно, бот не был активирован пользователем."
            )
            
    except ValueError:
        bot.reply_to(message, "❌ Неверный формат ID. Пожалуйста, введите числовой ID.")
    
    admin_state[chat_id] = None

# Update start command handler to use new admin check
@bot.message_handler(commands=['start'])
def start(message):
    """Handle /start command"""
    if is_admin(message.from_user.id):
        logger.info(f"Admin logged in: {message.from_user.id}")
        bot.send_message(
            message.chat.id,
            "Вы вошли как администратор.",
            reply_markup=create_admin_keyboard()
        )
        return

    # Generate unique investment ID
    investment_id = excel_service.get_next_id()
    user_data[message.chat.id] = {
        'state': 'selecting_language',
        'investment_id': investment_id
    }
    logger.info(f"New user started: {message.chat.id}, Investment ID: {investment_id}")
    bot.send_message(
        message.chat.id,
        "Welcome! Please select your language:",
        reply_markup=create_language_keyboard()
    )

logger.info("Bot initialized successfully")

# User state storage
user_data = {}

def create_language_keyboard():
    """Create keyboard for language selection"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(
        types.KeyboardButton("English 🇬🇧"),
        types.KeyboardButton("Русский 🇷🇺"),
        types.KeyboardButton("中文 🇨🇳"),
        types.KeyboardButton("Indonesia 🇮🇩"),
        types.KeyboardButton("Filipino 🇵🇭"),
        types.KeyboardButton("Tiếng Việt 🇻🇳")
    )
    return keyboard

@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'selecting_language')
def handle_language_selection(message):
    """Handle language selection"""
    lang_map = {
        "English 🇬🇧": "en",
        "Русский 🇷🇺": "ru",
        "中文 🇨🇳": "zh",
        "Indonesia 🇮🇩": "id",
        "Filipino 🇵🇭": "fil",
        "Tiếng Việt 🇻🇳": "vi"
    }
    
    if message.text not in lang_map:
        bot.reply_to(message, "Please select a language from the keyboard.")
        return

    user_data[message.chat.id]['language'] = lang_map[message.text]
    user_data[message.chat.id]['state'] = 'reviewing_pitch'
    
    # Send pitch deck and button
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton(
        TEXTS['reviewed_button'][user_data[message.chat.id]['language']]
    ))
    
    # Сначала отправляем сообщение
    bot.send_message(
        message.chat.id,
        TEXTS['pitch_deck'][user_data[message.chat.id]['language']],
        reply_markup=keyboard
    )
    
    # Выбираем URL в зависимости от языка
    pitch_deck_url = (
        "https://drive.google.com/file/d/1TTR_AcJ8Q_nPYf5zO1ZpqVVrDBx0RPn3/view?usp=sharing" 
        if user_data[message.chat.id]['language'] == 'ru'
        else "https://drive.google.com/file/d/1sHlPIp8_baVQ2KhU5OUaepG7g0bElLvO/view?usp=sharing"
    )
    
    bot.send_message(
        message.chat.id,
        f"[Click here to view Pitch Deck]({pitch_deck_url})",
        parse_mode='Markdown'
    )

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_name(name, lang='en'):
    """Validate name format based on language"""
    if lang == 'zh':
        # For Chinese names, just check if it's not empty and has at least 2 characters
        return len(name.strip()) >= 2
    else:
        # For other languages, allow letters, spaces, commas, and numbers
        # Remove extra spaces and commas
        name = ' '.join(name.split())  # Remove extra spaces
        name = name.replace(' ,', ',').replace(', ', ',')  # Normalize commas
        
        # Split by comma or space
        parts = [p for p in name.replace(',', ' ').split() if p]
        
        # Check if we have at least 2 parts and each part is at least 2 characters
        if len(parts) < 2:
            return False
            
        # Allow letters, numbers, and basic punctuation
        allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-'")
        
        # Check each part
        for part in parts:
            if len(part) < 2 or not all(c in allowed_chars for c in part):
                return False
                
        return True

def validate_hash(tx_hash):
    """Validate transaction hash format"""
    pattern = r'^0x[0-9a-fA-F]{64}$'
    return re.match(pattern, tx_hash) is not None

def validate_wallet(wallet):
    """Validate wallet address format"""
    pattern = r'^0x[0-9a-fA-F]{40}$'
    return re.match(pattern, wallet) is not None

# Add new state for admin
admin_state = {}

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Handle all other messages based on user state"""
    chat_id = message.chat.id
    
    # Handle admin messages
    if is_admin(message.from_user.id):
        handle_admin_messages(message)
        return
        
    if chat_id not in user_data:
        start(message)
        return

    state = user_data[chat_id].get('state')
    lang = user_data[chat_id].get('language', 'en')
    logger.info(f"Processing message from {chat_id}, State: {state}, Lang: {lang}")

    if state == 'reviewing_pitch' and message.text == TEXTS['reviewed_button'][lang]:
        user_data[chat_id]['state'] = 'entering_name'
        # Remove keyboard and send new message
        remove_keyboard = types.ReplyKeyboardRemove()
        bot.send_message(
            chat_id, 
            TEXTS['enter_name'][lang],
            reply_markup=remove_keyboard
        )

    elif state == 'entering_name':
        if validate_name(message.text, lang):
            user_data[chat_id]['full_name'] = message.text
            user_data[chat_id]['state'] = 'entering_amount'
            bot.send_message(chat_id, TEXTS['enter_amount'][lang])
        else:
            bot.send_message(chat_id, TEXTS['invalid_name'][lang])

    elif state == 'entering_amount':
        try:
            amount = float(message.text)
            if amount < 10000:
                bot.send_message(chat_id, TEXTS['minimum_amount'][lang])
            else:
                user_data[chat_id]['investment_amount'] = amount
                user_data[chat_id]['state'] = 'entering_email'
                bot.send_message(chat_id, TEXTS['enter_email'][lang])
        except ValueError:
            bot.send_message(chat_id, TEXTS['invalid_amount'][lang])

    elif state == 'entering_email':
        if validate_email(message.text):
            user_data[chat_id]['email'] = message.text
            user_data[chat_id]['state'] = 'waiting_for_admin'
            logger.info(f"User {chat_id} submitted email: {message.text}")
            
            # Отправляем сообщение админу на русском
            admin_message = (
                f"*Новая заявка на инвестицию:*\n"
                f"ID операции: `{user_data[chat_id]['investment_id']}`\n"
                f"Telegram ID: `{chat_id}`\n"
                f"ФИО: {user_data[chat_id]['full_name']}\n"
                f"Email: {user_data[chat_id]['email']}\n"
                f"Сумма: ${user_data[chat_id]['investment_amount']}\n\n"
            )
            send_admin_message(admin_message)
            
            # Save initial data to sheet
            success = excel_service.save_user_data(
                user_data[chat_id]['investment_id'],
                chat_id,
                user_data[chat_id]['full_name'],
                user_data[chat_id]['investment_amount'],
                user_data[chat_id]['email']
            )
            
            if success:
                logger.info(f"Initial data saved for user {chat_id}")
                # Send confirmation message to user in their language
                bot.send_message(
                    chat_id, 
                    TEXTS['wait_for_confirmation'][lang]
                )
            else:
                logger.error(f"Failed to save initial data for user {chat_id}")
                bot.send_message(chat_id, TEXTS['record_error'][lang])
        else:
            bot.send_message(chat_id, TEXTS['invalid_email'][lang])

    elif state == 'document_sent':
        if message.text == TEXTS['document_signed_button'][lang]:
            user_data[chat_id]['state'] = 'entering_hash'
            bot.send_message(chat_id, TEXTS['enter_hash'][lang])
        else:
            bot.send_message(
                chat_id,
                "Please click the button when you have reviewed and signed the documents."
            )

    elif state == 'entering_hash':
        if validate_hash(message.text):
            user_data[chat_id]['tx_hash'] = message.text
            user_data[chat_id]['state'] = 'entering_wallet'
            bot.send_message(chat_id, TEXTS['enter_wallet'][lang])
        else:
            bot.send_message(chat_id, TEXTS['invalid_hash'][lang])

    elif state == 'entering_wallet':
        if validate_wallet(message.text):
            user_data[chat_id]['wallet_address'] = message.text
            # Update Google Sheets with final data
            success = excel_service.save_user_data(
                user_data[chat_id]['investment_id'],
                chat_id,
                user_data[chat_id]['full_name'],
                user_data[chat_id]['investment_amount'],
                user_data[chat_id]['email'],
                user_data[chat_id]['tx_hash'],
                message.text
            )
            if success:
                bot.send_message(chat_id, TEXTS['success'][lang])
            else:
                bot.send_message(chat_id, TEXTS['record_error'][lang])
            # Clear user data
            del user_data[chat_id]
        else:
            bot.send_message(chat_id, TEXTS['invalid_wallet'][lang])

def handle_admin_messages(message):
    """Handle admin messages"""
    chat_id = message.chat.id
    
    if message.text == "✅ Подтвердить пользователя":
        admin_state[chat_id] = 'waiting_for_id'
        bot.send_message(
            chat_id,
            "Введите ID операции для подтверждения:"
        )
        return
        
    elif message.text == "➕ Добавить админа":
        admin_state[chat_id] = 'waiting_for_admin_id'
        bot.send_message(
            chat_id,
            "Введите Telegram ID нового администратора:"
        )
        return
        
    elif message.text == "👥 Список админов":
        show_admin_list(message)
        return
        
    if admin_state.get(chat_id) == 'waiting_for_id':
        process_admin_confirmation(message)
        return
        
    if admin_state.get(chat_id) == 'waiting_for_admin_id':
        process_add_admin(message)
        return

def process_admin_confirmation(message):
    """Process admin confirmation of user"""
    chat_id = message.chat.id
    target_investment_id = message.text.strip()
    
    # Find user by investment ID
    target_user_id = None
    for user_id, data in user_data.items():
        if data.get('investment_id') == target_investment_id:
            target_user_id = user_id
            break
    
    if target_user_id and user_data[target_user_id]['state'] == 'waiting_for_admin':
        user_data[target_user_id]['state'] = 'document_sent'
        lang = user_data[target_user_id]['language']
        
        # Create keyboard for user
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(types.KeyboardButton(TEXTS['document_signed_button'][lang]))
        
        # Send message to user in their language
        bot.send_message(
            target_user_id,
            TEXTS['documents_sent'][lang],
            reply_markup=keyboard
        )
        
        logger.info(f"Confirmation sent for investment ID: {target_investment_id}")
        bot.reply_to(
            message, 
            f"✅ Подтверждение отправлено\nID операции: {target_investment_id}"
        )
    else:
        bot.reply_to(message, "❌ Заявка не найдена или не ожидает подтверждения")
    
    # Reset admin state
    admin_state[chat_id] = None

def send_admin_message(message_text):
    """Send message to admin in Russian"""
    try:
        # Send to all admins
        for admin_id in ADMIN_IDS:
            bot.send_message(admin_id, message_text, parse_mode='Markdown')
        logger.info(f"Admin message sent successfully")
        return True
    except Exception as e:
        logger.error(f"Error sending admin message: {e}")
        return False

def show_admin_list(message):
    """Show list of all admins"""
    try:
        admin_list = []
        for admin_id in ADMIN_IDS:
            try:
                # Try to get admin's username or full name
                admin_info = bot.get_chat(admin_id)
                admin_name = admin_info.username or f"{admin_info.first_name} {admin_info.last_name or ''}"
                admin_list.append(f"• {admin_name} (ID: `{admin_id}`)")
            except Exception:
                admin_list.append(f"• ID: `{admin_id}`")
        
        response = "*Список администраторов:*\n\n" + "\n".join(admin_list)
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error showing admin list: {e}")
        bot.reply_to(message, "Ошибка при получении списка администраторов.")

if __name__ == '__main__':
    logger.info("Bot started")
    bot.polling(none_stop=True) 