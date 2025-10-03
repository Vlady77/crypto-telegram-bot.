import os, time, requests, feedparser
from datetime import datetime
import pytz
from urllib.parse import urlparse

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT  = os.environ["TELEGRAM_CHAT_ID"]
TG    = f"https://api.telegram.org/bot{TOKEN}"

# ➜ Hier kannst du Quellen hinzufügen/entfernen (RSS)
FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://www.theblock.co/rss"  # einige Artikel ggf. paywalled, Headlines gehen
]

MAX_ITEMS = 6  # wie viele Überschriften posten

def domain(url: str) -> str:
    try:
        d = urlparse(url).netloc.replace("www.", "")
        return d
    except Exception:
        return "source"

def fetch_news():
    items = []
    for url in FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                title = (e.title or "").strip()
                link  = (e.link or "").strip()
                if not title or not link:
                    continue
                # Timestamp (best effort)
                ts = None
                for key in ("published_parsed", "updated_parsed"):
                    if getattr(e, key, None):
                        ts = time.mktime(getattr(e, key))
                        break
                items.append({
                    "title": title,
                    "link": link,
                    "ts": ts or 0,
                    "src": domain(link),
                })
        except Exception as ex:
            print("Feed error:", url, ex)

    # Dedupe nach Link (oder Titel) & sortieren nach Zeit
    seen = set()
    uniq = []
    for it in items:
        k = it["link"]
        if k in seen:
            continue
        seen.add(k)
        uniq.append(it)
    uniq.sort(key=lambda x: x["ts"], reverse=True)
    return uniq[:MAX_ITEMS]

def build_message():
    tz = pytz.timezone("Europe/Prague")
    now = datetime.now(tz).strftime("%H:%M")
    headlines = fetch_news()

    lines = [f"#News\nTop crypto headlines ({now}):\n"]
    if not headlines:
        lines.append("• No fresh headlines right now. Check back later.")
    else:
        for it in headlines:
            # Titel auf eine sinnvolle Länge kürzen
            title = it["title"].strip()
            if len(title) > 140:
                title = title[:137] + "..."
            lines.append(f"• {title} — {it['src']}\n{it['link']}")
    lines.append("\n—\nDisclaimer: Not financial advice. Our analytics only.")
    return "\n".join(lines)

def send(text: str):
    r = requests.post(
        f"{TG}/sendMessage",
        data={"chat_id": CHAT, "text": text, "disable_web_page_preview": True},
        timeout=25,
    )
    print("Telegram status:", r.status_code, r.text[:200])
    r.raise_for_status()

if __name__ == "__main__":
    send(build_message())
