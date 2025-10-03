import os, requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT = os.environ["TELEGRAM_CHAT_ID"]
TG = f"https://api.telegram.org/bot{TOKEN}"

def cg(endpoint, **params):
    r = requests.get(f"https://api.coingecko.com/api/v3/{endpoint}", params=params, timeout=20)
    r.raise_for_status(); return r.json()

def fmt_usd(x): 
    return f"${x:,.0f}" if x >= 1000 else f"${x:,.2f}"

def build():
    ids = ["bitcoin","ethereum","ripple","binancecoin","solana","tether"]
    p = cg("simple/price", ids=",".join(ids), vs_currencies="usd,eur")  # <— jetzt EUR statt RUB
    g = cg("global")["data"]
    mc = g["total_market_cap"]["usd"]; dom = g["market_cap_percentage"]["btc"]

    try:
        f = requests.get("https://api.alternative.me/fng/?limit=1", timeout=15).json()["data"][0]
        fng_v, fng_c = int(f["value"]), f["value_classification"]
    except Exception:
        fng_v, fng_c = None, None

    m = cg("coins/markets", vs_currency="usd", order="market_cap_desc",
           per_page=100, page=1, price_change_percentage="24h")
    stables = {"usdt","usdc","dai","tusd","usde","fdusd","eusd"}
    filt = [c for c in m if c["symbol"].lower() not in stables and c.get("price_change_percentage_24h") is not None]
    gainer = max(filt, key=lambda c: c["price_change_percentage_24h"])
    loser = min(filt, key=lambda c: c["price_change_percentage_24h"])

    lines = []
    lines.append(f"#Daily\nCryptocurrency prices this morning:\n")
    lines.append(f"🥇 Bitcoin (BTC): {fmt_usd(p['bitcoin']['usd'])}")
    lines.append(f"🥈 Ethereum (ETH): {fmt_usd(p['ethereum']['usd'])}")
    lines.append(f"🐬 XRP (XRP): {fmt_usd(p['ripple']['usd'])}")
    lines.append(f"🥉 BNB (BNB): {fmt_usd(p['binancecoin']['usd'])}")
    lines.append(f"🌚 Solana (SOL): {fmt_usd(p['solana']['usd'])}")
    lines.append(f"💲 Tether (USDT): €{p['tether']['eur']}")   # <— EUR

    lines.append("")
    lines.append(f"▫️ Total crypto market capitalization: {fmt_usd(mc)}")
    lines.append(f"▫️ Bitcoin dominance: {dom:.2f}%")
    if fng_v: 
        lines.append(f"▫️ Fear & Greed Index: {fng_v} (“{fng_c}”)\n")

    lines.append(f"📈 Top gainer (24h): {gainer['name']} ({gainer['symbol'].upper()}) {gainer['price_change_percentage_24h']:.2f}%")
    lines.append(f"📉 Top loser (24h): {loser['name']} ({loser['symbol'].upper()}) {loser['price_change_percentage_24h']:.2f}%")

    # Neuer Disclaimer
    lines.append("\n—\nDisclaimer: Not financial advice. Our analytics only.")

    return "\n".join(lines)

def send(msg):
    r = requests.post(f"{TG}/sendMessage", data={"chat_id": CHAT, "text": msg})
    r.raise_for_status()

if __name__ == "__main__":
    send(build())
