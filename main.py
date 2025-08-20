from config import *
import telebot
from telebot import types
import requests
from db import (
    get_db_path,
    get_connection,
    init_db,
    seed_from_users_allow,
    upsert_user,
    get_user,
    get_admin_ids,
    set_user_status,
    get_settings,
    update_settings,
)

secret = SECRET
token = TOKEN
url = 'https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize'
lang = 'ru-RU'
# Full list can be expanded per Yandex TTS docs
voices = ['filipp', 'ermil', 'madirus', 'zahar']
default_emotion = 'neutral'
default_speed = 1.0
text = ''
serviceAccountId = API_USER
Authorization = API_KEY
bot = telebot.TeleBot(token)
text_knock_knock = TEXT_KNOCK_KNOCK
text_user_denied = TEXT_USER_DENIED
db_conn = None
headers = {
    "Authorization": 'Api-Key ' + Authorization,
    "serviceAccountId" : serviceAccountId, 
    "Content-Length" : "0",
    "Host" : "tts.api.cloud.yandex.net",
    "User-Agent" : "Python/Telebot",
    "Accept" : "*/*",
    "Accept-Encoding" : "gzip,deflate,br",
    "Connection" : "keep-alive"
}

def init_database():
    global db_conn
    db_path = get_db_path(CURREENT_DIR)
    db_conn = get_connection(db_path)
    init_db(db_conn)
    seed_from_users_allow(db_conn, CURREENT_DIR)

def get_text_knock_knock(text_knock_knock, message):
    return text_knock_knock.format(
            message.from_user.id, 
            message.from_user.username, 
            message.from_user.first_name,
            message.from_user.last_name
        )

def add_user_cmd(message):
    parts = message.split()
    if len(parts) < 3:
        return 'usage: useradd <id_or_username> <secret>'
    if parts[2] != secret:
        return 'wrong secret'
    user_key = parts[1]
    # Append to users.allow for backward compatibility
    try:
        with open(CURREENT_DIR + '/users.allow', 'a', encoding='utf-8') as f:
            f.write('\n' + user_key)
    except Exception:
        pass
    # Also reflect in DB if numeric id
    if user_key.isdigit():
        upsert_user(db_conn, int(user_key), username=None, is_admin=False, status='approved')
    return ('user {} added').format(user_key)

def is_user_allowed(user_id):
    user = get_user(db_conn, user_id)
    return bool(user and user.get('status') == 'approved')

def get_params(message, settings): 
    return {
        'lang' : lang,
        'voice' : settings.get('voice', voices[0]),
        'emotion' : settings.get('emotion', default_emotion),
        'speed' : settings.get('speed', default_speed),
        'text': message
    }

def get_speech(message, settings):
    r = requests.post(url, params=get_params(message, settings), headers=headers)
    return(r.content)

def notify_admins_new_request(message):
    admins = get_admin_ids(db_conn)
    if not admins:
        # fallback to legacy admin if any
        try:
            legacy_admin = 149672979
            admins = [legacy_admin]
        except Exception:
            admins = []
    kb = types.InlineKeyboardMarkup()
    approve_btn = types.InlineKeyboardButton(text='✅ Принять', callback_data=f'approve:{message.from_user.id}')
    deny_btn = types.InlineKeyboardButton(text='🚫 Отклонить', callback_data=f'deny:{message.from_user.id}')
    kb.add(approve_btn, deny_btn)
    for admin_id in admins:
        try:
            bot.send_message(admin_id, text=get_text_knock_knock(text_knock_knock, message), reply_markup=kb)
        except Exception:
            continue

def send_settings_menu(chat_id, user_id):
    settings = get_settings(db_conn, user_id, default_voice=voices[0], default_speed=default_speed, default_emotion=default_emotion)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton('🎙 Голос', callback_data='menu_voice'))
    kb.add(types.InlineKeyboardButton('⏩ Темп речи', callback_data='menu_speed'))
    kb.add(types.InlineKeyboardButton('🙂 Настроение', callback_data='menu_emotion'))
    text = f"Текущие настройки:\n- голос: {settings['voice']}\n- темп: {settings['speed']}\n- настроение: {settings['emotion']}"
    bot.send_message(chat_id, text=text, reply_markup=kb)

def send_voice_menu(chat_id):
    kb = types.InlineKeyboardMarkup()
    buttons = [types.InlineKeyboardButton(v, callback_data=f'set_voice:{v}') for v in voices]
    # arrange in rows of 2
    for i in range(0, len(buttons), 2):
        kb.row(*buttons[i:i+2])
    kb.add(types.InlineKeyboardButton('⬅️ Назад', callback_data='back_settings'))
    bot.send_message(chat_id, text='Выберите голос:', reply_markup=kb)

def send_speed_menu(chat_id):
    kb = types.InlineKeyboardMarkup()
    speed_options = ['0.8', '1.0', '1.2', '1.4']
    buttons = [types.InlineKeyboardButton(s, callback_data=f'set_speed:{s}') for s in speed_options]
    for i in range(0, len(buttons), 3):
        kb.row(*buttons[i:i+3])
    kb.add(types.InlineKeyboardButton('⬅️ Назад', callback_data='back_settings'))
    bot.send_message(chat_id, text='Выберите темп речи:', reply_markup=kb)

def send_emotion_menu(chat_id):
    kb = types.InlineKeyboardMarkup()
    emotion_options = ['neutral', 'good', 'evil']
    buttons = [types.InlineKeyboardButton(e, callback_data=f'set_emotion:{e}') for e in emotion_options]
    kb.row(*buttons)
    kb.add(types.InlineKeyboardButton('⬅️ Назад', callback_data='back_settings'))
    bot.send_message(chat_id, text='Выберите настроение:', reply_markup=kb)

@bot.message_handler(content_types=['text'])
def func(message):
    # Lazy init DB on first use
    global db_conn
    if db_conn is None:
        init_database()

    text_lower = (message.text or '').strip().lower()

    if text_lower.startswith('/start'):
        # Ensure user exists in DB
        user = get_user(db_conn, message.from_user.id)
        if not user:
            # New user -> create pending and notify admins
            upsert_user(db_conn, message.from_user.id, message.from_user.username, is_admin=False, status='pending')
            bot.send_message(message.chat.id, text='Заявка на доступ отправлена администратору. Ожидайте решения.')
            notify_admins_new_request(message)
            return
        if user.get('status') != 'approved':
            bot.send_message(message.chat.id, text='Ваш статус: ' + user.get('status') + '. Ожидайте решения администратора.')
            return
        send_settings_menu(message.chat.id, message.from_user.id)
        return

    if ('useradd' in text_lower and secret in message.text):
        answer = add_user_cmd(message.text)
        bot.send_message(message.chat.id, text=answer)
        return

    if not is_user_allowed(message.from_user.id):
        # Auto-create pending user if not known
        user = get_user(db_conn, message.from_user.id)
        if not user:
            upsert_user(db_conn, message.from_user.id, message.from_user.username, is_admin=False, status='pending')
            notify_admins_new_request(message)
        bot.send_message(message.chat.id, text=text_user_denied)
        return

    # Approved: synthesize with per-user settings
    settings = get_settings(db_conn, message.from_user.id, default_voice=voices[0], default_speed=default_speed, default_emotion=default_emotion)
    voice_message = get_speech(message.text, settings)
    bot.send_audio(message.chat.id, voice_message, title=message.text)


@bot.callback_query_handler(func=lambda call: True)
def callbacks(call: types.CallbackQuery):
    global db_conn
    data = call.data or ''
    chat_id = call.message.chat.id if call.message else None

    if data.startswith('approve:'):
        try:
            target_id = int(data.split(':', 1)[1])
            set_user_status(db_conn, target_id, 'approved')
            bot.answer_callback_query(call.id, 'Пользователь одобрен')
            bot.send_message(target_id, text='Доступ к боту предоставлен. Отправьте текст для озвучивания или откройте /start для настроек.')
        except Exception:
            bot.answer_callback_query(call.id, 'Ошибка')
        return

    if data.startswith('deny:'):
        try:
            target_id = int(data.split(':', 1)[1])
            set_user_status(db_conn, target_id, 'denied')
            bot.answer_callback_query(call.id, 'Пользователь отклонен')
            bot.send_message(target_id, text='Заявка отклонена.')
        except Exception:
            bot.answer_callback_query(call.id, 'Ошибка')
        return

    if data == 'menu_voice':
        if chat_id is not None:
            send_voice_menu(chat_id)
        bot.answer_callback_query(call.id)
        return

    if data == 'menu_speed':
        if chat_id is not None:
            send_speed_menu(chat_id)
        bot.answer_callback_query(call.id)
        return

    if data == 'menu_emotion':
        if chat_id is not None:
            send_emotion_menu(chat_id)
        bot.answer_callback_query(call.id)
        return

    if data == 'back_settings':
        if chat_id is not None and call.from_user:
            send_settings_menu(chat_id, call.from_user.id)
        bot.answer_callback_query(call.id)
        return

    if data.startswith('set_voice:'):
        voice = data.split(':', 1)[1]
        update_settings(db_conn, call.from_user.id, voice=voice)
        bot.answer_callback_query(call.id, f'Голос: {voice}')
        if chat_id is not None:
            send_settings_menu(chat_id, call.from_user.id)
        return

    if data.startswith('set_speed:'):
        try:
            speed = float(data.split(':', 1)[1])
        except Exception:
            speed = default_speed
        update_settings(db_conn, call.from_user.id, speed=speed)
        bot.answer_callback_query(call.id, f'Темп: {speed}')
        if chat_id is not None:
            send_settings_menu(chat_id, call.from_user.id)
        return

    if data.startswith('set_emotion:'):
        emotion = data.split(':', 1)[1]
        update_settings(db_conn, call.from_user.id, emotion=emotion)
        bot.answer_callback_query(call.id, f'Настроение: {emotion}')
        if chat_id is not None:
            send_settings_menu(chat_id, call.from_user.id)
        return

init_database()
bot.infinity_polling(interval=0, timeout=20)