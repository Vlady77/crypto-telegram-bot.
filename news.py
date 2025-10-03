import os
import time
import requests
import feedparser
import pytz
from datetime import datetime
from urllib.parse import urlparse, urlunparse, parse_qsl

# --- Telegram auth ---
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT  = os.environ["TELEGRAM_CHAT_ID"]
TG    = f"https://api.telegram.org/bot{TOKEN}"

# --- RSS-Quellen ---
FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://www.theblock.co/rss",
]
MAX_ITEMS = 8   # Anzahl Headlines

# ---------- Utils ----------
def escape_html(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def clean_link(u: str) -> str:
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

def parse_ts(entry) -> int:
    for key in ("published_parsed", "updated_parsed"):
        if getattr(entry, key, None):
            return int(time.mktime(getattr(entry, key)))
    return 0

# ---------- Fetch ----------
def fetch_news():
    items = []
    for url in FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                title = (getattr(e, "title", "") or "").strip()
                link  = (getattr(e, "link", "")  or "").strip()
                if not title or not link:
                    continue
                ts = parse_ts(e)
                items.append({"title": title, "link": link, "ts": ts, "src": domain(link)})
        except Exception as ex:
            print("Feed error:", url, ex)

    seen, uniq = set(), []
    for it in items:
        key = it["link"]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    uniq.sort(key=lambda x: x["ts"], reverse=True)
    return uniq[:MAX_ITEMS]

# ---------- Build Message ----------
def build_message():
    tz = pytz.timezone("Europe/Prague")
    now = datetime.now(tz)

    headlines = fetch_news()

    header = (
        f"<b>#News</b>\n"
        f"<i>Top crypto headlines</i> <code>{now.strftime('%H:%M')}</code>\n"
        f"<code>{now.strftime('%a, %d %b %Y')}</code>\n\n"
    )

    if not headlines:
        return header + "• No fresh headlines right now. Check back later.\n\n<i>—\nDisclaimer: Not financial advice. Our analytics only.</i>"

    lines = []
    for it in headlines:
        title = escape_html(it["title"])
        if len(title) > 160:
            title = title[:157] + "…"
        link  = clean_link(it["link"])
        src   = escape_html(it["src"])

        tcode = ""
        if it["ts"]:
            t_local = datetime.fromtimestamp(it["ts"], tz).strftime("%H:%M")
            tcode = f" • {t_local}"

        block = (
            f"🆕 <b><a href=\"{link}\">{title}</a></b>\n"
            f"    <code>{src}{tcode}</code>\n"
        )
        lines.append(block)

    footer = "\n<i>—\nDisclaimer: Not financial advice. Our analytics only.</i>"
    return header + "\n".join(lines) + footer

# ---------- Send ----------
def send(text: str):
    r = requests.post(
        f"{TG}/sendMessage",
        data={
            "chat_id": CHAT,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        },
        timeout=25,
    )
    print("Telegram status:", r.status_code, r.text[:200])
    r.raise_for_status()

if __name__ == "__main__":
    send(build_message())
