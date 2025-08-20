# Telegram TTS Voice Bot (Yandex TTS)

Бот Telegram, который озвучивает текст с помощью сервиса Yandex Cloud TTS. Поддерживает:
- выбор голоса, темпа речи и «настроения» (emotion) пользователем через меню;
- хранение настроек на пользователя в SQLite;
- модерацию доступа: заявки от новых пользователей и их одобрение/отклонение администраторами;
- белый список и администраторы, задаваемые в файле `users.allow`.

### 1. Требования
- Linux/Unix (проверено на Ubuntu/Debian)
- Python 3.10+ (из-за использования аннотаций вида `str | None`)
- pip

Рекомендуется изолировать зависимости в виртуальном окружении:
```bash
sudo apt update
sudo apt install -y python3-venv python3-pip
```

### 2. Подготовка проекта
Склонируйте или скопируйте проект в желаемую директорию, например:
```bash
sudo mkdir -p /opt/ya-tts-voice-bot/
sudo chown -R "$USER":"$USER" /opt/ya-tts-voice-bot/
cp -r . /opt/ya-tts-voice-bot
cd /opt/ya-tts-voice-bot/
```

Создайте и активируйте виртуальное окружение (рекомендуется):
```bash
python3 -m venv venv
source venv/bin/activate
```

Установите зависимости:
```bash
pip install -r requirements.txt
```

### 3. Настройка Yandex Cloud TTS
Вам потребуются:
- API Key (статический ключ доступа);
- serviceAccountId (ID сервисного аккаунта с правами на TTS).

См. документацию Yandex Cloud TTS по получению ключей (`tts.api.cloud.yandex.net`).

### 4. Настройка Telegram Bot
1. Создайте бота у `@BotFather` и получите `TOKEN`.
2. Скопируйте `example.config.py` в `config.py` и заполните поля:

```bash
cp example.config.py config.py
```

В файле `config.py` заполните:
- `TOKEN` — токен вашего телеграм-бота;
- `API_KEY` — Yandex Cloud API Key;
- `API_USER` — serviceAccountId;
- `SECRET` — секретная фраза, используемая в команде `useradd`;
- `CURREENT_DIR` — абсолютный путь к директории проекта (для systemd особенно важно), например `'/var/opt/voice-bot'`.

Пример:
```
CURREENT_DIR = '/opt/ya-tts-voice-bot/'
```

### 5. Файл users.allow (белый список и администраторы)
В файле `users.allow` можно перечислить разрешённых пользователей и администраторов. Поддерживаемые форматы строк:
- обычный пользователь: `123456789` или `@username` или `username`
- администратор: `admin:123456789` или `admin:@username` или `admin:username`

Пример:
```
admin:413097979
@user_one
user_two
123456700
```

Администраторы получают заявки на доступ от новых пользователей и могут их принять/отклонить.

### 6. Запуск локально (в foregound)
```bash
source venv/bin/activate  # если используете venv
python main.py
```

После запуска:
- Отправьте боту `/start` — если вы новый пользователь, админы получат заявку на доступ.
- После одобрения используйте меню, чтобы выбрать голос/темп/настроение, и отправляйте текст для озвучивания.

Данные и настройки пользователей хранятся в SQLite-файле `voicebot.sqlite3` в директории `CURREENT_DIR`.

### 7. Запуск как systemd-сервис
Отредактируйте `ya-tts-voice-bot.service` под вашу машину:
- `WorkingDirectory` должен указывать на директорию проекта, например `/opt/ya-tts-voice-bot/`;
- `ExecStart` — путь к интерпретатору Python (рекомендуется использовать интерпретатор вашего venv) и `main.py`.

Рекомендуемый вариант для venv:
```
ExecStart=/opt/ya-tts-voice-bot/venv/bin/python /opt/ya-tts-voice-bot/main.py
```

Установите и запустите сервис:
```bash
sudo cp ya-tts-voice-bot.service /etc/systemd/system/ya-tts-voice-bot.service
sudo systemctl daemon-reload
sudo systemctl enable ya-tts-voice-bot.service
sudo systemctl start ya-tts-voice-bot.service
```

Проверка статуса и логов:
```bash
sudo systemctl status ya-tts-voice-bot
sudo journalctl -u ya-tts-voice-bot -f
```

Если сервис не стартует, проверьте:
- корректность путей в `ya-tts-voice-bot.service` (особенно `WorkingDirectory` и `ExecStart`);
- что `config.py` заполнен и находится в рабочей директории;
- права доступа на директорию и файлы (у пользователя systemd должно быть право читать/исполнять);
- доступ к сети и корректные креды Yandex Cloud.

### 8. Обновление и резервное копирование
- Для обновления кода остановите сервис, замените файлы, выполните `daemon-reload` и запустите сервис снова.
- Резервируйте файл БД `voicebot.sqlite3` (горячее копирование обычно безопасно, но лучше останавливать сервис для консистентности при больших объемах).

### 9. Команды и поведение бота
- `/start` — если вы новый пользователь, отправляется заявка администраторам; если одобрены — открывается меню настроек.
- Меню настроек: выбор голоса, темпа и настроения.
- Текстовые сообщения — озвучиваются с использованием ваших текущих настроек.
- `useradd <id_or_username> <SECRET>` — добавляет пользователя в `users.allow` (и в БД, если указан числовой ID). Полезно для быстрого вручного добавления.

### 10. Заметки по безопасности
- Храните `API_KEY`, `TOKEN`, `SECRET` в `config.py` и ограничивайте на него права доступа.
- Не публикуйте публично содержимое `config.py` и `voicebot.sqlite3`.