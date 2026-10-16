# Odoo stock sync and low-stock alerts

A small Python job that reads on-hand quantities from Odoo over XML-RPC, compares each product with its reorder point, sends one alert listing the low-stock products (Slack webhook or email), and writes one log line per run.

Only the local test instance is used. Never point `ODOO_URL` at a company Odoo while testing.

## Setup (local Odoo with Docker)

1. Install Docker Desktop and Python 3.12+. Copy `.env.example` to `.env` and set `SLACK_WEBHOOK_URL`, or set `alerts.channel = "none"` in `config.toml` to only log.
2. Start the local Odoo: `docker compose up -d db odoo`. Wait about 2 minutes, then open http://localhost:8069 and log in as `admin` / `admin`.
3. Install the dev dependencies: `pip install -r requirements-dev.txt`.
4. Load `.env` into the shell (`set -a; . ./.env; set +a` in Bash) and seed five test products: `python scripts/odoo_stock.py seed`.
5. Check the stock: `python scripts/odoo_stock.py list`.
6. Run the sync once: `python -m app.sync --config config.toml`. With the seeded stock, expect `status=ok` and `alerts_sent=0`.
7. Lower one product below its reorder point: `python scripts/odoo_stock.py set TEST-1002 4`.
8. Run the sync again. The alert arrives in Slack, and `logs/sync.log` gets a line with `alerts_sent=1`.
9. Run the tests with `python -m pytest`. To run the sync on a schedule, `docker compose up -d sync` repeats it every `SYNC_INTERVAL_SECONDS`.

## Status

- **Verified on Odoo 17 in Docker (one run, 5 test products):**
  - `docker compose up -d db odoo` starts Postgres 16 and Odoo 17. Odoo loaded 34 modules in about 28 s and the registry in about 47 s.
  - Login over XML-RPC with the `admin` account succeeds.
  - `scripts/odoo_stock.py seed` created the 5 test products and their stock. `list` shows the expected quantities.
  - Sync run 1 with healthy stock: 5 products checked, 0 low, 0 alerts, about 1.0 s wall-clock.
  - After `set TEST-1002 4` in Odoo, sync run 2: 5 products checked, 1 low (TEST-1002, on hand 4, reorder point 10), 1 alert, about 0.9 s wall-clock.
  - The alert reached a local webhook sink (`scripts/slack_sink.py`) on the host. The sink is a stand-in for Slack, not Slack itself.
  - Both runs are in `logs/sync.log`, one line each.
- **Verified earlier:** 20 pytest tests pass. The sync also ran against the stand-in XML-RPC server.
- **Not yet verified:**
  - A real Slack incoming webhook.
  - SMTP delivery.
  - The `sync` service in Docker Compose. It reads `.env`, and that path has not been run.
  - Scheduled runs over time.
- **Known issue fixed during this run:** `docker-compose.yml` passed `--admin-passwd`, which Odoo 17 rejects, so the container exited. The flag was removed. The seed script also failed on `action_apply_inventory` because Odoo cannot serialise its `None` return value over XML-RPC. The count is applied anyway, so the script now accepts that specific fault and then checks the quantity by reading it back.

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
