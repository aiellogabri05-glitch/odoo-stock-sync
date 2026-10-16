# Odoo stock sync and low-stock alerts

A small Python job that reads on-hand quantities from Odoo over XML-RPC, compares each product with its reorder point, sends one alert listing the low-stock products (Slack webhook or email), and writes one log line per run.

Only the local test instance is used. Never point `ODOO_URL` at a company Odoo while testing.

## Setup (local Odoo with Docker)

1. Install Docker Desktop and Python 3.12+.
2. `cp .env.example .env` and set `SLACK_WEBHOOK_URL` (or set `alerts.channel = "none"` in `config.toml` to only log).
3. `docker compose up -d db odoo` and wait about 2 minutes for Odoo to create `odoo_test` with the Inventory app. Open http://localhost:8069 and log in as `admin` / `admin` to check.
4. `pip install -r requirements-dev.txt`
5. Seed five test products with stock: `python scripts/odoo_stock.py seed` (reads `.env`; export the variables or use `set -a; . ./.env; set +a` first).
6. Check the stock: `python scripts/odoo_stock.py list`
7. Run the sync once: `python -m app.sync --config config.toml`. Expect `status=ok` and `alerts_sent=0` with the seeded stock.
8. Lower a product below its reorder point: `python scripts/odoo_stock.py set TEST-1002 4`
9. Run again. The alert arrives in Slack, and `logs/sync.log` gets a new line with `alerts_sent=1`.
10. Run the tests: `python -m pytest`. To run as a scheduled service, `docker compose up -d sync` repeats every `SYNC_INTERVAL_SECONDS`.

## Files

- `app/odoo_client.py`: XML-RPC login and `product.product` read (`qty_available`, all warehouses).
- `app/stock.py`: the threshold rule. A product is low when on-hand is **at or below** its reorder point.
- `app/alerts.py`: alert message builder, Slack webhook and SMTP senders.
- `app/sync.py`: one run (read, compare, alert, log). `--interval-seconds` repeats it.
- `config.toml`: alert channel, log path, and the product list with reorder points.
- `scripts/odoo_stock.py`: seed and update test stock in the local Odoo (refuses non-local URLs).
- `tests/`: pytest tests for the threshold rule, the alert builder, the sync logic and config loading.

## Log format

Each run appends one line to `logs/sync.log`:

```
2026-10-16T12:14:25+00:00 status=ok products_checked=5 products_missing=0 missing_skus=- low_stock=2 low_stock_skus=TEST-1002,TEST-1004 alerts_sent=1 channel=slack
```

## Known limits

- Alerts repeat on every run while a product stays low. There is no de-duplication yet.
- SMTP sending is implemented but was not run against a real mail server.
- Only the `qty_available` figure is used, so stock is summed across all warehouses.
