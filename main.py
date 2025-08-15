import os
import requests

TOKEN = os.environ[8425355916:AAGc6-zek0min7lTD4qg4OHly5pdTw15cZI]
CHAT_ID = os.environ[ @news_iran_daily]

def send_message(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    requests.post(url, data=payload)

if __name__ == "__main__":
    send_message("ربات با موفقیت اجرا شد 🚀")
