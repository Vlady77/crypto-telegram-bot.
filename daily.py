import os
import time
import requests
import feedparser
import pytz
from datetime import datetime
from urllib.parse import urlparse, urlunparse, parse_qsl

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT  = os.environ["TELEGRAM_CHAT_ID"]
TG    = f"https://api.telegram.org/bot{TOKEN}"

# === RSS-Quellen (frei erweiterbar) ===
FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://www.theblock.co/rss",
]
MAX_ITEMS = 6  # wie viele Headlines posten

# ---------- Utils ----------
def escape_html(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def clean_link(u: str) -> str:
    """Entfernt UTM/Tracking-Parameter, behält https://host/path bei."""
    try:
        p = urlparse(u)
        keep = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                if not k.lower().startswith(("utm_", "ref", "ref_"))]
        q = "&".join(f"{k}={v}" for k, v in keep) if keep else ""
        return urlunparse((p.scheme, p.netloc, p.path, "", q, ""))
    except Exception:
        return u

def domain(u: str) -> str:
    try:
        return urlparse(u).netloc.replace("www.", "") or "source"
    except Exception:
        return "source"

# ---------- Fetch & Build ----------
def fetch_news():
    items = []
    for url in FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                title = (getattr(e, "title", "") or "").strip()
                link  = (getattr(e, "link", "") or "").strip()
                if not title or not link:
                    continue
                ts = 0
                for key in ("published_parsed", "updated_parsed"):
                    if getattr(e, key, None):
                        ts = time.mktime(getattr(e, key))
                        break
                items.append({"title": title, "link": link, "ts": ts, "src": domain(link)})
        except Exception as ex:
            print("Feed error:", url, ex)

    # Dedupe nach Link & sortieren
    seen, uniq = set(), []
    for it in items:
        if it["link"] in seen:
            continue
        seen.add(it["link"])
        uniq.append(it)
    uniq.sort(key=lambda x: x["ts"], reverse=True)
    return uniq[:MAX_ITEMS]

def build_message():
    tz = pytz.timezone("Europe/Prague")
    now = datetime.now(tz).strftime("%H:%M")
    headlines = fetch_news()

    lines = [f"<b>#News</b>\nTop crypto headlines <code>{now}</code>:\n"]

    if not headlines:
        lines.append("• No fresh headlines right now. Check back later.")
    else:
        for i, it in enumerate(headlines, 1):
            title = escape_html(it["title"])
            if len(title) > 140:
                title = title[:137] + "…"
            link = clean_link(it["link"])
            src  = escape_html(it["src"])
            lines.append(f"{i}. <a href=\"{link}\">{title}</a>  <code>{src}</code>")

    lines.append("\n<i>—\nDisclaimer: Not financial advice. Our analytics only.</i>")
    return "\n".join(lines)

# ---------- Send ----------
def send(text: str):
    r = requests.post(
        f"{TG}/sendMessage",
        data={
            "chat_id": CHAT,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=25,
    )
    print("Telegram status:", r.status_code, r.text[:200])
    r.raise_for_status()

if __name__ == "__main__":
    send(build_message())
