"""Crypto price ticker for the BUSY Bar.

Fetches prices from CoinGecko and renders `BTC $60,542` style tickers
on the front display. Configure via environment variables:

  COINS      comma-separated CoinGecko coin IDs (default: bitcoin)
  VS         fiat currency code (default: usd)
  INTERVAL   fetch interval in seconds (default: 120; CoinGecko free
             tier allows ~5-15 calls/min, one call covers all coins)
  ROTATE     seconds each coin stays on screen when multiple (default: 10)
  SHOW_EVERY how often to show the ticker, in seconds (default: 60).
             Between showings the display is released so the bar's own
             clock/apps are visible. Set to 0 for always-on.
  BUSYBAR    bar API base (default: http://172.31.3.134/api)
"""
import asyncio
import os
from datetime import datetime

import httpx
from fastapi import FastAPI
from contextlib import asynccontextmanager

# Default is the BUSY Bar's fixed address when connected over USB.
# For Wi-Fi, set BUSYBAR to your bar's IP, e.g. http://192.168.1.50/api
BUSYBAR = os.environ.get("BUSYBAR", "http://10.0.4.20/api")
APP_NAME = "crypto"
PRIORITY = 15

COINS = [c.strip() for c in os.environ.get("COINS", "bitcoin").split(",") if c.strip()]
VS = os.environ.get("VS", "usd").lower()
INTERVAL = int(os.environ.get("INTERVAL", "120"))
ROTATE = int(os.environ.get("ROTATE", "10"))
SHOW_EVERY = int(os.environ.get("SHOW_EVERY", "60"))

COINGECKO = "https://api.coingecko.com/api/v3"

# ASCII-only display: $ works, other fiats get their ISO code as suffix
FIAT_PREFIX = {"usd": "$"}

UP_COLOR = "#00FF66FF"
DOWN_COLOR = "#FF3344FF"
FLAT_COLOR = "#FFFFFFFF"
SYMBOL_COLOR = "#FFAA00FF"


class State:
    def __init__(self):
        # coin id -> {"symbol": "BTC", "price": 64996.0, "change": 0.08}
        self.prices: dict = {}
        self.last_fetch: datetime | None = None
        self.error: str | None = None


state = State()


def format_price(value: float) -> str:
    if value >= 1000:
        return f"{value:,.0f}"
    if value >= 1:
        return f"{value:,.2f}"
    return f"{value:.4f}"


def ticker_text(coin_id: str) -> tuple[str, str]:
    """Returns (text, color) for a coin."""
    info = state.prices[coin_id]
    prefix = FIAT_PREFIX.get(VS, "")
    suffix = "" if VS in FIAT_PREFIX else f" {VS.upper()}"
    text = f"{info['symbol']} {prefix}{format_price(info['price'])}{suffix}"
    change = info.get("change") or 0
    color = UP_COLOR if change > 0.05 else DOWN_COLOR if change < -0.05 else FLAT_COLOR
    return text, color


async def fetch_symbols(client: httpx.AsyncClient):
    """One-time lookup of ticker symbols for configured coin ids."""
    for coin_id in COINS:
        r = await client.get(f"{COINGECKO}/coins/{coin_id}",
                             params={"localization": "false", "tickers": "false",
                                     "market_data": "false", "community_data": "false",
                                     "developer_data": "false", "sparkline": "false"})
        r.raise_for_status()
        state.prices[coin_id] = {"symbol": r.json()["symbol"].upper(),
                                 "price": None, "change": None}


async def fetch_prices(client: httpx.AsyncClient):
    r = await client.get(f"{COINGECKO}/simple/price",
                         params={"ids": ",".join(COINS), "vs_currencies": VS,
                                 "include_24hr_change": "true"})
    r.raise_for_status()
    data = r.json()
    for coin_id in COINS:
        if coin_id in data:
            state.prices[coin_id]["price"] = data[coin_id][VS]
            state.prices[coin_id]["change"] = data[coin_id].get(f"{VS}_24h_change")
    state.last_fetch = datetime.now()
    state.error = None


async def draw_ticker(coin_id: str):
    text, color = ticker_text(coin_id)
    payload = {
        "application_name": APP_NAME,
        "priority": PRIORITY,
        "elements": [{
            "id": "ticker",
            "type": "text",
            "text": text,
            "font": "bold",
            "color": color,
            "x": 36,
            "y": 4,
            "align": "center",
            "timeout": ROTATE + 2,
            "display": "front",
        }],
    }
    async with httpx.AsyncClient() as client:
        try:
            await client.post(f"{BUSYBAR}/display/draw", json=payload, timeout=5)
        except httpx.RequestError:
            pass


async def clear():
    async with httpx.AsyncClient() as client:
        try:
            await client.request("DELETE", f"{BUSYBAR}/display/draw",
                                 json={"application_name": APP_NAME}, timeout=5)
        except httpx.RequestError:
            pass


async def fetch_loop():
    async with httpx.AsyncClient(timeout=15) as client:
        while not all(v.get("symbol") for v in state.prices.values()) or not state.prices:
            try:
                await fetch_symbols(client)
            except (httpx.HTTPError, KeyError) as e:
                state.error = f"symbol lookup: {e}"
                await asyncio.sleep(30)

        while True:
            try:
                await fetch_prices(client)
            except httpx.HTTPError as e:
                state.error = str(e)
            await asyncio.sleep(INTERVAL)


async def render_loop():
    while True:
        ready = [c for c in COINS if state.prices.get(c, {}).get("price") is not None]
        if not ready:
            await asyncio.sleep(2)
            continue
        for coin_id in ready:
            await draw_ticker(coin_id)
            await asyncio.sleep(ROTATE)
        if SHOW_EVERY > 0:
            # Release the display so the bar's own clock shows through,
            # then come back for the next showing.
            await clear()
            await asyncio.sleep(max(SHOW_EVERY - ROTATE * len(ready), 5))


@asynccontextmanager
async def lifespan(app):
    tasks = [asyncio.create_task(fetch_loop()),
             asyncio.create_task(render_loop())]
    yield
    for t in tasks:
        t.cancel()
    await clear()


app = FastAPI(lifespan=lifespan)


@app.get("/status")
async def get_status():
    return {
        "coins": COINS,
        "vs": VS,
        "prices": state.prices,
        "last_fetch": state.last_fetch.isoformat(timespec="seconds") if state.last_fetch else None,
        "error": state.error,
    }
