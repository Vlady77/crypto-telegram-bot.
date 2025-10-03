import os, time, re, requests, feedparser, pytz
from datetime import datetime
from urllib.parse import urlparse, urlunparse, parse_qsl

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT  = os.environ["TELEGRAM_CHAT_ID"]
TG    = f"https://api.telegram.org/bot{TOKEN}"

FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://www.theblock.co/rss",
]
MAX_ITEMS = 8

# ---------- helpers ----------
def escape_html(s: str) -> str:
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def clean_link(u: str) -> str:
    try:
        p = urlparse(u)
        keep = [(k,v) for k,v in parse_qsl(p.query, keep_blank_values=True)
                if not k.lower().startswith(("utm_","ref","ref_"))]
        q = "&".join(f"{k}={v}" for k,v in keep) if keep else ""
        return urlunparse((p.scheme,p.netloc,p.path,"",q,""))
    except Exception:
        return u

def domain(u: str) -> str:
    try: return urlparse(u).netloc.replace("www.","") or "source"
    except Exception: return "source"

def ts_of(e) -> int:
    for k in ("published_parsed","updated_parsed"):
        if getattr(e,k,None): return int(time.mktime(getattr(e,k)))
    return 0

# ---------- classification & highlighting ----------
CATS = [
    ("Regulation", "⚖️",  r"\b(SEC|regulat|ban|law|legal|lawsuit|ETF)\b"),
    ("Hack",       "🚨",   r"\b(hack|exploit|breach|stolen|drain|vuln)\b"),
    ("Market",     "📈",   r"\b(pump|rally|surge|dump|crash|ATH|all[- ]time high|price|market)\b"),
    ("Partnership","🤝",   r"\b(partner|integration|collaborat|listing|lists|adds)\b"),
    ("Institutions","🏦",  r"\b(BlackRock|Fidelity|bank|ETF|fund|institution)\b"),
    ("DeFi",       "🧩",   r"\b(DeFi|staking|liquidity|DEX|protocol)\b"),
]

HIGHLIGHTS = [
    (r"\b(BTC|Bitcoin)\b", "strong"),
    (r"\b(ETH|Ethereum)\b", "strong"),
    (r"\b(ETF|approval|approved)\b", "strong"),
    (r"\b(SEC|lawsuit|ban)\b", "strong"),
    (r"\b(hack|exploit|breach)\b", "strong"),
]

def classify(title: str):
    t = title.lower()
    for name, emoji, pattern in CATS:
        if re.search(pattern, t, re.I): return emoji
    return "🆕"  # default

def highlight_html(text: str) -> str:
    s = escape_html(text)
    for pat,_ in HIGHLIGHTS:
        s = re.sub(pat, lambda m: f"<b>{escape_html(m.group(0))}</b>", s, flags=re.I)
    return s

# ---------- fetch headlines ----------
def fetch_news():
    items=[]
    for url in FEEDS:
        try:
            feed=feedparser.parse(url)
            for e in feed.entries:
                title=(getattr(e,"title","") or "").strip()
                link =(getattr(e,"link","")  or "").strip()
                if not title or not link: continue
                items.append({"title":title,"link":link,"ts":ts_of(e),"src":domain(link)})
        except Exception as ex:
            print("Feed error:", url, ex)
    seen=set(); uniq=[]
    for it in items:
        if it["link"] in seen: continue
        seen.add(it["link"]); uniq.append(it)
    uniq.sort(key=lambda x:x["ts"], reverse=True)
    return uniq[:MAX_ITEMS]

# ---------- optional: top movers (evening only) ----------
def top_movers_block():
    try:
        m = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params=dict(vs_currency="usd", order="market_cap_desc",
                        per_page=150, page=1, price_change_percentage="24h"),
            timeout=25).json()
        stables={"usdt","usdc","dai","tusd","usde","fdusd","eusd"}
        filt=[c for c in m if c.get("symbol","").lower() not in stables and c.get("price_change_percentage_24h") is not None]
        if not filt: return ""
        gainer=max(filt, key=lambda c:c["price_change_percentage_24h"])
        loser =min(filt, key=lambda c:c["price_change_percentage_24h"])
        lines = [
            "<b>Top movers (24h)</b>",
            f"🟢 {escape_html(gainer['name'])} ({gainer['symbol'].upper()}) <b>{gainer['price_change_percentage_24h']:.2f}%</b>",
            f"🔴 {escape_html(loser['name'])} ({loser['symbol'].upper()}) <b>{loser['price_change_percentage_24h']:.2f}%</b>",
        ]
        return "\n".join(lines)
    except Exception as e:
        print("Movers error:", e)
        return ""

# ---------- sentiment ----------
BULL = re.compile(r"\b(pump|rally|surge|ath|approval|win|bull|breakout)\b", re.I)
BEAR = re.compile(r"\b(dump|crash|fall|hack|ban|lawsuit|bear)\b", re.I)

def sentiment_summary(headlines):
    score=0
    for it in headlines:
        t=it["title"]
        score += bool(BULL.search(t)) - bool(BEAR.search(t))
    if score > 1: tag="😃 Bullish"
    elif score < -1: tag="😡 Bearish"
    else: tag="😐 Neutral"
    return f"<b>Sentiment:</b> {tag}"

# ---------- build & send ----------
def build_message():
    tz=pytz.timezone("Europe/Prague")
    now=datetime.now(tz)
    headlines=fetch_news()

    header = (
        f"<b>#News</b>\n"
        f"<i>Top crypto headlines</i> <code>{now.strftime('%H:%M')}</code>\n"
        f"<code>{now.strftime('%a, %d %b %Y')}</code>\n\n"
    )

    if not headlines:
        return header + "• No fresh headlines right now. Check back later.\n\n<i>—\nDisclaimer: Not financial advice. Our analytics only.</i>"

    lines=[]
    for it in headlines:
        emoji = classify(it["title"])
        title = highlight_html(it["title"])
        if len(title) > 160: title = title[:157] + "…"
        link  = clean_link(it["link"])
        src   = escape_html(it["src"])
        tcode = f" • {datetime.fromtimestamp(it['ts'], tz).strftime('%H:%M')}" if it["ts"] else ""
        lines.append(f"{emoji} <b><a href=\"{link}\">{title}</a></b>\n    <code>{src}{tcode}</code>")

    # Evening extras (>=18:00)
    if now.hour >= 18:
        lines.append("")  # spacer
        lines.append(sentiment_summary(headlines))
        movers = top_movers_block()
        if movers:
            lines.append(movers)

    footer = "\n\n<i>—\nDisclaimer: Not financial advice. Our analytics only.</i>"
    return header + "\n".join(lines) + footer

def send(text):
    r=requests.post(f"{TG}/sendMessage",
        data={"chat_id":CHAT,"text":text,"parse_mode":"HTML","disable_web_page_preview":True},
        timeout=25)
    print("Telegram status:", r.status_code, r.text[:200])
    r.raise_for_status()

if __name__=="__main__":
    send(build_message())
