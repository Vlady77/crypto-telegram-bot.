import os, requests, traceback
from datetime import datetime
import pytz

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT  = os.environ["TELEGRAM_CHAT_ID"]
TG    = f"https://api.telegram.org/bot{TOKEN}"

def cg(endpoint, **params):
    try:
        r = requests.get(f"https://api.coingecko.com/api/v3/{endpoint}",
                         params=params, timeout=25)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("CoinGecko error on", endpoint, "->", e)
        return None

def fmt_usd(x):
    if x is None: return "—"
    return f"${x:,.0f}" if x >= 1000 else f"${x:,.2f}"

def build():
    # aktuelle Uhrzeit in Prag
    tz = pytz.timezone("Europe/Prague")
    now = datetime.now(tz)
    if now.hour < 12:
        title = "#Daily Morning"
    else:
        title = "#Daily Evening"

    lines = [f"{title}\nCryptocurrency prices:\n"]

    # Preise abrufen
    ids = ["bitcoin","ethereum","ripple","binancecoin","solana","tether"]
    p = cg("simple/price", ids=",".join(ids), vs_currencies="usd,eur") or {}
    g = (cg("global") or {}).get("data", {}) or {}
    mc = (g.get("total_market_cap") or {}).get("usd")
    dom = (g.get("market_cap_percentage") or {}).get("btc")

    lines += [
        f"🥇 Bitcoin (BTC): {fmt_usd((p.get('bitcoin') or {}).get('usd'))}",
        f"🥈 Ethereum (ETH): {fmt_usd((p.get('ethereum') or {}).get('usd'))}",
        f"🐬 XRP (XRP): {fmt_usd((p.get('ripple') or {}).get('usd'))}",
        f"🥉 BNB (BNB): {fmt_usd((p.get('binancecoin') or {}).get('usd'))}",
        f"🌚 Solana (SOL): {fmt_usd((p.get('solana') or {}).get('usd'))}",
        f"💲 Tether (USDT): €{(p.get('tether') or {}).get('eur')}"
    ]

    lines.append("")
    if mc:  lines.append(f"▫️ Total crypto market capitalization: {fmt_usd(mc)}")
    if dom: lines.append(f"▫️ Bitcoin dominance: {dom:.2f}%")

    # Fear & Greed
    try:
        f = requests.get("https://api.alternative.me/fng/?limit=1", timeout=15).json()["data"][0]
        lines.append(f"▫️ Fear & Greed Index: {int(f['value'])} (“{f['value_classification']}”)")
    except Exception as e:
        print("FNG error:", e)

    # Top mover
    try:
        m = cg("coins/markets", vs_currency="usd", order="market_cap_desc",
               per_page=100, page=1, price_change_percentage="24h") or []
        stables = {"usdt","usdc","dai","tusd","usde","fdusd","eusd"}
        filt = [c for c in m if c.get("symbol","").lower() not in stables and c.get("price_change_percentage_24h") is not None]
        if filt:
            gainer = max(filt, key=lambda c: c["price_change_percentage_24h"])
            loser  = min(filt, key=lambda c: c["price_change_percentage_24h"])
            lines.append("")
            lines.append(f"📈 Top gainer (24h): {gainer['name']} ({gainer['symbol'].upper()}) {gainer['price_change_percentage_24h']:.2f}%")
            if loser['id'] != gainer['id']:
                lines.append(f"📉 Top loser (24h): {loser['name']} ({loser['symbol'].upper()}) {loser['price_change_percentage_24h']:.2f}%")
    except Exception as e:
        print("Movers error:", e)

    # Neuer Disclaimer
    lines.append("\n—\nDisclaimer: Not financial advice. Our analytics only.")

    return "\n".join(lines)

def send(text):
    r = requests.post(f"{TG}/sendMessage",
                      data={"chat_id": CHAT, "text": text, "disable_web_page_preview": True},
                      timeout=25)
    print("Telegram status:", r.status_code, r.text[:200])
    r.raise_for_status()

if __name__ == "__main__":
    try:
        msg = build()
        print("Preview:\n", msg[:400], "...\n")
        send(msg)
    except Exception as e:
        print("FAILED:", e)
        traceback.print_exc()
        raise
