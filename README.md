# BUSY Bar Crypto Ticker

Show live cryptocurrency prices on your [BUSY Bar](https://busy.app)'s front display.

```
BTC $64,996      <- green when up, red when down (24h change)
```

Prices come from the [CoinGecko API](https://docs.coingecko.com/) (free, no API key).
Any of CoinGecko's thousands of coin IDs work — `bitcoin`, `ethereum`, `monero`, ...
Multiple coins rotate on screen. Between showings the ticker releases the display
so your bar's clock and other apps show through.

## Quick start

Requires Docker or Podman with compose.

```bash
git clone <this-repo>
cd busybar-crypto
# edit compose.yaml: set BUSYBAR to your bar's address, pick your COINS
docker compose up -d --build
```

Check it's working:

```bash
curl http://localhost:8091/status
```

## Configuration

All via environment variables in `compose.yaml`:

| Variable     | Default                  | Meaning |
|--------------|--------------------------|---------|
| `BUSYBAR`    | `http://10.0.4.20/api`   | Bar API base. `10.0.4.20` is the fixed USB address; use your bar's IP for Wi-Fi. |
| `COINS`      | `bitcoin`                | Comma-separated [CoinGecko coin IDs](https://api.coingecko.com/api/v3/coins/list). |
| `VS`         | `usd`                    | Fiat currency: `usd`, `eur`, `gbp`, ... |
| `INTERVAL`   | `120`                    | Seconds between price fetches. One request covers all coins; free tier is fine at 60+. |
| `SHOW_EVERY` | `60`                     | Show the ticker once per this many seconds, releasing the display in between. `0` = always on. |
| `ROTATE`     | `10`                     | Seconds each coin stays on screen. |

Example — Bitcoin and Ethereum in euros, always on:

```yaml
environment:
  - COINS=bitcoin,ethereum
  - VS=eur
  - SHOW_EVERY=0
```

## Notes

- The bar's bitmap fonts are ASCII-only, so currency symbols like `€`/`£` can't be
  rendered. USD shows as `$64,996`; other fiats show as `64,996 EUR`.
- Color reflects 24h change: green up, red down, white flat.
- The ticker draws at priority 15 — above the bar's built-in clock (10), below
  focus sessions (90), so an active BUSY session always wins.
- If the bar is unreachable the ticker retries quietly; `GET /status` (port 8091)
  shows the last fetch and any errors.

## Unofficial

Community project, not affiliated with Flipper Devices / BUSY. "BUSY Bar" is
their trademark; for the hardware and official apps see [busy.app](https://busy.app).
