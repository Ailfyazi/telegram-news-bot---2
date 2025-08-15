import os
import telebot

# گرفتن توکن از GitHub Secrets
TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "ربات با موفقیت راه افتاد 🚀")

# پیام تست
def send_test_message():
    chat_id = 5832108489
    bot.send_message(chat_id, "ربات شما فعال است ✅")

if __name__ == "__main__":
    send_test_message()
    bot.polling()
