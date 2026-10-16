"""One sync run: read Odoo, find low stock, alert, log. Run once or in a loop."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.alerts import build_alert_message, send_email, send_slack
from app.config import Settings, load_settings
from app.odoo_client import OdooClient
from app.stock import StockLevel, find_low_stock

log = logging.getLogger("stock_sync")


@dataclass(frozen=True)
class SyncResult:
    products_checked: int
    products_missing: tuple[str, ...]
    low_stock: tuple[StockLevel, ...]
    alerts_sent: int


def run_sync(settings: Settings, client: OdooClient, run_at: datetime | None = None) -> SyncResult:
    run_at = run_at or datetime.now(timezone.utc)
    by_sku = client.fetch_products([p.sku for p in settings.products])

    levels = []
    missing = []
    for product in settings.products:
        odoo_product = by_sku.get(product.sku)
        if odoo_product is None:
            missing.append(product.sku)
            continue
        levels.append(
            StockLevel(
                sku=product.sku,
                name=odoo_product.name,
                on_hand=odoo_product.on_hand,
                reorder_point=product.reorder_point,
            )
        )

    low = find_low_stock(levels)
    alerts_sent = 0
    if low and settings.alert_channel != "none":
        subject, body = build_alert_message(low, products_checked=len(levels), run_at=run_at)
        if settings.alert_channel == "slack":
            send_slack(settings.slack_webhook_url, subject, body)
        else:
            send_email(
                host=settings.smtp_host,
                port=settings.smtp_port,
                user=settings.smtp_user,
                password=settings.smtp_password,
                sender=settings.alert_from,
                recipient=settings.alert_to,
                subject=subject,
                body=body,
            )
        alerts_sent = 1

    return SyncResult(
        products_checked=len(levels),
        products_missing=tuple(missing),
        low_stock=tuple(low),
        alerts_sent=alerts_sent,
    )


def format_log_line(run_at: datetime, result: SyncResult, channel: str) -> str:
    skus = ",".join(level.sku for level in result.low_stock) or "-"
    missing = ",".join(result.products_missing) or "-"
    return (
        f"{run_at.isoformat(timespec='seconds')} status=ok products_checked={result.products_checked} "
        f"products_missing={len(result.products_missing)} missing_skus={missing} "
        f"low_stock={len(result.low_stock)} low_stock_skus={skus} "
        f"alerts_sent={result.alerts_sent} channel={channel}"
    )


def append_log(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def run_once(settings: Settings) -> str:
    run_at = datetime.now(timezone.utc)
    try:
        client = OdooClient(settings.odoo_url, settings.odoo_db, settings.odoo_user, settings.odoo_password)
        result = run_sync(settings, client, run_at)
        line = format_log_line(run_at, result, settings.alert_channel)
    except Exception as exc:  # keep the loop alive; record the failure in the log
        line = f"{run_at.isoformat(timespec='seconds')} status=error error={type(exc).__name__}: {exc}"
        log.exception("sync run failed")
    print(line, flush=True)
    append_log(settings.log_path, line)
    return line


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync Odoo stock and send low-stock alerts.")
    parser.add_argument("--config", default=os.environ.get("SYNC_CONFIG", "config.toml"))
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=int(os.environ.get("SYNC_INTERVAL_SECONDS", "0")),
        help="Repeat every N seconds. 0 (default) runs once and exits.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = load_settings(Path(args.config))

    if args.interval_seconds <= 0:
        line = run_once(settings)
        return 0 if " status=ok " in line else 1

    while True:
        run_once(settings)
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    sys.exit(main())
