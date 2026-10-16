"""Load settings: non-secret values from config.toml, secrets from environment variables."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Product:
    sku: str
    reorder_point: int


@dataclass(frozen=True)
class Settings:
    odoo_url: str
    odoo_db: str
    odoo_user: str
    odoo_password: str
    products: tuple[Product, ...]
    alert_channel: str  # "slack", "smtp" or "none"
    slack_webhook_url: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    alert_from: str
    alert_to: str
    log_path: Path


def load_settings(config_path: Path, env: dict[str, str] | None = None) -> Settings:
    env = dict(os.environ) if env is None else env
    with config_path.open("rb") as fh:
        raw = tomllib.load(fh)

    products = tuple(Product(sku=p["sku"], reorder_point=int(p["reorder_point"])) for p in raw.get("products", []))
    if not products:
        raise ValueError(f"{config_path} lists no products under [[products]]")

    alerts = raw.get("alerts", {})
    channel = alerts.get("channel", "none")
    if channel not in {"slack", "smtp", "none"}:
        raise ValueError(f"alerts.channel must be slack, smtp or none, got {channel!r}")

    def required(name: str) -> str:
        value = env.get(name, "")
        if not value:
            raise ValueError(f"environment variable {name} is required")
        return value

    if channel == "slack" and not env.get("SLACK_WEBHOOK_URL"):
        raise ValueError("SLACK_WEBHOOK_URL is required when alerts.channel = 'slack'")

    log_path = Path(raw.get("logging", {}).get("path", "logs/sync.log"))
    if not log_path.is_absolute():
        log_path = config_path.parent / log_path

    return Settings(
        odoo_url=required("ODOO_URL"),
        odoo_db=required("ODOO_DB"),
        odoo_user=required("ODOO_USER"),
        odoo_password=required("ODOO_PASSWORD"),
        products=products,
        alert_channel=channel,
        slack_webhook_url=env.get("SLACK_WEBHOOK_URL", ""),
        smtp_host=env.get("SMTP_HOST", ""),
        smtp_port=int(env.get("SMTP_PORT", "587")),
        smtp_user=env.get("SMTP_USER", ""),
        smtp_password=env.get("SMTP_PASSWORD", ""),
        alert_from=env.get("ALERT_FROM", ""),
        alert_to=env.get("ALERT_TO", ""),
        log_path=log_path,
    )
