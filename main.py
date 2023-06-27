from config import *
import telebot
import requests

secret = SECRET
token = TOKEN
url = 'https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize'
lang = 'ru-RU'
voices = ['filipp', 'ermil', 'madirus', 'zahar']
emotion = 'neutral'
speed = 1
text = ''
serviceAccountId = API_USER
Authorization = API_KEY
bot = telebot.TeleBot(token)
text_knock_knock = TEXT_KNOCK_KNOCK
text_user_denied = TEXT_USER_DENIED
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

def get_text_knock_knock(text_knock_knock, message):
    return text_knock_knock.format(
            message.from_user.id, 
            message.from_user.username, 
            message.from_user.first_name,
            message.from_user.last_name
        )

def read_user_allow():
    users_allow = []
    with open(CURREENT_DIR + '/users.allow') as f:
        lines = f.readlines()
        for line in lines:
            line = line.replace('\n', '')
            users_allow.append(line)
    return users_allow

def add_user(message):
    if(message.split()[2] != secret):
        return
    users_allow = read_user_allow()
    if isinstance(message.split(), list ) and len(message.split()) > 1 :
        user = message.split()[1] 
        users_allow.append(user)
        print(users_allow)
        with open(CURREENT_DIR + 'users.allow', "a") as f:
            f.write('\n' + user)
    else:
        return 'error add user'
    
    return ('user {} added').format(user)

def allowUser(username,id):
    users_allow = read_user_allow()
    if (username in users_allow or str(id) in users_allow ):
        return True
    else:
        return False

def get_params(message): 
    return {'lang' : lang, 'voice' : voices[0], 'emotion' : emotion, 'speed' : speed, 'text': message}

def get_speech(message):
    r = requests.post(url, params=get_params(message), headers=headers)
    return(r.content)

@bot.message_handler(content_types=['text'])
def func(message):

    if('useradd' in message.text and secret in message.text):
        answer = add_user(message.text)
        bot.send_message( message.chat.id, text=answer)
        return

    if(not allowUser(message.from_user.username, message.from_user.id)):
         bot.send_message(message.chat.id, text=text_user_denied)
         bot.send_message(149672979, text = get_text_knock_knock(text_knock_knock, message))
         return
    

    voice_message = get_speech(message.text)
    bot.send_audio(message.chat.id, voice_message, title=message.text)

bot.infinity_polling(interval=0, timeout=20)