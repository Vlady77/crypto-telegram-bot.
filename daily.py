# daily.py
# Posts daily crypto prices to Telegram with a time-aware greeting
# (morning / afternoon / evening for Europe/Prague)

import os
import requests
import pytz
from datetime import datetime

# --- Telegram setup ---
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT  = os.environ["TELEGRAM_CHAT_ID"]
TG    = f"https://api.telegram.org/bot{TOKEN}"

# --- Helpers ---
def cg(endpoint, **params):
    """Call CoinGecko v3 endpoint."""
    r = requests.get(f"https://api.coingecko.com/api/v3/{endpoint}", params=params, timeout=25)
    r.raise_for_status()
    return r.json()

def fmt_usd(x):
    """Format number in USD style used in the channel."""
    if x is None:
        return "—"
    return f"${x:,.0f}" if x >= 1000 else f"${x:,.2f}"

def build_message():
    # --- Local time for greeting ---
    tz = pytz.timezone("Europe/Prague")
    now = datetime.now(tz)
    h = now.hour
    if h < 12:
        part = "this morning"
    elif h < 18:
        part = "this afternoon"
    else:
        part = "this evening"

    # --- Prices for majors (USD), USDT in EUR ---
    ids = ["bitcoin", "ethereum", "ripple", "binancecoin", "solana", "tether"]
    prices = cg("simple/price", ids=",".join(ids), vs_currencies="usd,eur")

    # --- Global data ---
    g = cg("global")["data"]
    mc_usd = g["total_market_cap"]["usd"]
    btc_dom = g["market_cap_percentage"]["btc"]

    # --- Fear & Greed ---
    try:
        fng = requests.get("https://api.alternative.me/fng/?limit=1", timeout=20).json()["data"][0]
        fng_v, fng_c = int(fng["value"]), fng["value_classification"]
    except Exception:
        fng_v, fng_c = None, None

    # --- Top gainer/loser (exclude stables) ---
    markets = cg(
        "coins/markets",
        vs_currency="usd",
        order="market_cap_desc",
        per_page=250,
        page=1,
        price_change_percentage="24h",
    )
    stables = {"usdt", "usdc", "dai", "tusd", "usde", "fdusd", "eurt", "eusd"}
    filtered = [
        c for c in markets
        if c.get("symbol", "").lower() not in stables
        and c.get("price_change_percentage_24h") is not None
    ]
    gainer = max(filtered, key=lambda c: c["price_change_percentage_24h"]) if filtered else None
    loser  = min(filtered, key=lambda c: c["price_change_percentage_24h"]) if filtered else None

    # --- Text ---
    lines = []
    lines.append("#Daily")
    lines.append(f"Cryptocurrency prices {part}:\n")

    lines.append(f"🥇 Bitcoin (BTC): {fmt_usd(prices['bitcoin']['usd'])}")
    lines.append(f"🥈 Ethereum (ETH): {fmt_usd(prices['ethereum']['usd'])}")
    lines.append(f"🐬 XRP (XRP): {fmt_usd(prices['ripple']['usd'])}")
    lines.append(f"🥉 BNB (BNB): {fmt_usd(prices['binancecoin']['usd'])}")
    lines.append(f"🌚 Solana (SOL): {fmt_usd(prices['solana']['usd'])}")
    lines.append(f"💲 Tether (USDT): {prices['tether']['eur']:.2f} EUR")

    lines.append("")
    lines.append(f"▫️ Total crypto market capitalization: {fmt_usd(mc_usd)}")
    lines.append(f"▫️ Bitcoin dominance: {btc_dom:.2f}%")
    if fng_v is not None:
        lines.append(f"▫️ Fear & Greed Index: {fng_v} (“{fng_c}”)")

    if gainer and loser:
        lines.append("")
        lines.append(
            f"📈 Top gainer (24h): {gainer['name']} ({gainer['symbol'].upper()}) "
            f"{gainer['price_change_percentage_24h']:.2f}%"
        )
        lines.append(
            f"📉 Top loser (24h): {loser['name']} ({loser['symbol'].upper()}) "
            f"{loser['price_change_percentage_24h']:.2f}%"
        )

    lines.append("\n—")
    lines.append("Disclaimer: Not financial advice. Our analytics only.")
    return "\n".join(lines)

def send_to_telegram(text: str):
    r = requests.post(
        f"{TG}/sendMessage",
        data={
            "chat_id": CHAT,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=25,
    )
    print("Telegram:", r.status_code, r.text[:200])
    r.raise_for_status()

if __name__ == "__main__":
    send_to_telegram(build_message())
