import os, requests
from datetime import datetime
import pytz

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT  = os.environ["TELEGRAM_CHAT_ID"]
TG    = f"https://api.telegram.org/bot{TOKEN}"

def send_poll():
    tz = pytz.timezone("Europe/Prague")
    now = datetime.now(tz).strftime("%d %b %Y")
    q = f"📊 Weekly poll ({now}): Is next week going to be bullish or bearish?"
    r = requests.post(
        f"{TG}/sendPoll",
        data={
            "chat_id": CHAT,
            "question": q,
            "options": '["Bullish ✅","Bearish ❌","Sideways 🤷"]',
            "is_anonymous": False,
            "allows_multiple_answers": False,
        },
        timeout=25,
    )
    print("Poll status:", r.status_code, r.text[:200])
    r.raise_for_status()

if __name__ == "__main__":
    send_poll()
