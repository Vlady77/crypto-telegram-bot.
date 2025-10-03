import os, json, requests, pytz, pathlib
from datetime import datetime, timedelta

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT  = os.environ["TELEGRAM_CHAT_ID"]
TG    = f"https://api.telegram.org/bot{TOKEN}"

STATE_PATH = pathlib.Path("state/weekly.json")

# ---------- Helpers ----------
def fmt_usd(x):
    if x is None: return "—"
    return f"${x:,.0f}" if x >= 1000 else f"${x:,.2f}"

def fmt_pct(x):
    if x is None: return "—"
    arrow = "⬆️" if x >= 0 else "⬇️"
    return f"{arrow} {abs(x):.2f}%"

def tg_send(text):
    r = requests.post(
        f"{TG}/sendMessage",
        json={"chat_id": CHAT,"text": text,"parse_mode": "HTML","disable_web_page_preview": True},
        timeout=25,
    )
    print("Telegram:", r.status_code, r.text[:200])
    r.raise_for_status()

# ---------- Data fetch ----------
def coingecko(url, **params):
    r = requests.get(f"https://api.coingecko.com/api/v3/{url}", params=params, timeout=25)
    r.raise_for_status()
    return r.json()

def get_prices_7d():
    ids = "bitcoin,ethereum,ripple,binancecoin,solana"
    data = coingecko("coins/markets", vs_currency="usd", ids=ids, price_change_percentage="7d")
    out = {}
    for c in data:
        sym = c["symbol"].upper()
        out[sym] = {"price": c["current_price"], "pct7d": c.get("price_change_percentage_7d_in_currency")}
    return out

def get_global():
    g = coingecko("global")["data"]
    return {"mc_usd": g["total_market_cap"]["usd"], "btc_dom": g["market_cap_percentage"]["btc"]}

def get_fng():
    try:
        f = requests.get("https://api.alternative.me/fng/?limit=1", timeout=20).json()["data"][0]
        return int(f["value"]), f["value_classification"]
    except Exception:
        return None, None

def top_movers_7d():
    stables = {"usdt","usdc","dai","tusd","usde","fdusd","eusd"}
    m = coingecko(
        "coins/markets",
        vs_currency="usd",
        order="market_cap_desc",
        per_page=250, page=1,
        price_change_percentage="7d",
    )
    filt = [c for c in m if c.get("symbol","").lower() not in stables
            and c.get("price_change_percentage_7d_in_currency") is not None]
    if not filt: return None, None
    gainer = max(filt, key=lambda c: c["price_change_percentage_7d_in_currency"])
    loser  = min(filt, key=lambda c: c["price_change_percentage_7d_in_currency"])
    return gainer, loser

# ---------- State (persist last week's market cap) ----------
def load_state():
    if not STATE_PATH.exists(): return None
    try:
        with STATE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def save_state(mc_usd: float, now_iso: str):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STATE_PATH.open("w", encoding="utf-8") as f:
        json.dump({"date": now_iso, "mc_usd": mc_usd}, f, ensure_ascii=False, indent=2)

# ---------- Build message ----------
def build_message():
    tz = pytz.timezone("Europe/Prague")
    now = datetime.now(tz)
    start = (now - timedelta(days=7)).strftime("%d %b")
    end   = now.strftime("%d %b %Y")

    majors = get_prices_7d()
    glob   = get_global()
    fng_v, fng_c = get_fng()
    gainer, loser = top_movers_7d()

    # Weekly market cap change (computed from saved state)
    prev = load_state()
    mc_change_line = ""
    if prev and isinstance(prev.get("mc_usd"), (int, float)) and prev["mc_usd"] > 0:
        pct = (glob["mc_usd"] - prev["mc_usd"]) / prev["mc_usd"] * 100.0
        mc_change_line = f" ({fmt_pct(pct)})"
    else:
        # First run (no previous state) → no % shown
        mc_change_line = ""

    lines = [
        f"<b>#Weekly Summary</b>",
        f"<code>{start} → {end}</code>",
        "",
        "<b>Market</b>",
        f"🌍 Total market cap: <b>{fmt_usd(glob['mc_usd'])}</b>{mc_change_line}",
        f"🟠 BTC dominance: <b>{glob['btc_dom']:.2f}%</b>",
        "",
        "<b>Majors (7d)</b>",
        f"🥇 Bitcoin (BTC): <b>{fmt_usd(majors['BTC']['price'])}</b> ({fmt_pct(majors['BTC']['pct7d'])})",
        f"🥈 Ethereum (ETH): <b>{fmt_usd(majors['ETH']['price'])}</b> ({fmt_pct(majors['ETH']['pct7d'])})",
        f"🐬 XRP (XRP): <b>{fmt_usd(majors['XRP']['price'])}</b> ({fmt_pct(majors['XRP']['pct7d'])})",
        f"🥉 BNB (BNB): <b>{fmt_usd(majors['BNB']['price'])}</b> ({fmt_pct(majors['BNB']['pct7d'])})",
        f"🌚 Solana (SOL): <b>{fmt_usd(majors['SOL']['price'])}</b> ({fmt_pct(majors['SOL']['pct7d'])})",
        "",
        f"🧠 Fear & Greed Index: <b>{fng_v}</b> (“{fng_c}”)" if fng_v is not None else "🧠 Fear & Greed Index: —",
    ]

    if gainer and loser:
        lines += [
            "",
            "<b>Top movers this week</b>",
            f"🟢 {gainer['name']} ({gainer['symbol'].upper()}) "
            f"<b>{gainer['price_change_percentage_7d_in_currency']:.2f}%</b>",
            f"🔴 {loser['name']} ({loser['symbol'].upper()}) "
            f"<b>{loser['price_change_percentage_7d_in_currency']:.2f}%</b>",
        ]

    lines += ["", "<i>—", "Disclaimer: Not financial advice. Our analytics only.</i>"]

    # Save current market cap for next week
    save_state(glob["mc_usd"], datetime.utcnow().isoformat())

    return "\n".join(lines)

if __name__ == "__main__":
    tg_send(build_message())
