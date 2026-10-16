from datetime import datetime, timezone
from pathlib import Path

import pytest

import app.sync as sync
from app.config import Product, Settings
from app.odoo_client import OdooProduct
from app.sync import format_log_line, run_sync

RUN_AT = datetime(2026, 10, 16, 9, 30, tzinfo=timezone.utc)


class FakeOdoo:
    """Stands in for OdooClient so the sync logic is tested without a network."""

    def __init__(self, products: dict[str, float]):
        self._products = {sku: OdooProduct(sku, f"Name {sku}", qty) for sku, qty in products.items()}

    def fetch_products(self, skus):
        return {sku: self._products[sku] for sku in skus if sku in self._products}


def make_settings(channel: str = "slack") -> Settings:
    return Settings(
        odoo_url="http://unused",
        odoo_db="db",
        odoo_user="u",
        odoo_password="p",
        products=(
            Product("A", 10),
            Product("B", 10),
            Product("GONE", 5),
            Product("C", 3),
        ),
        alert_channel=channel,
        slack_webhook_url="https://hooks.example/unused",
        smtp_host="",
        smtp_port=587,
        smtp_user="",
        smtp_password="",
        alert_from="",
        alert_to="",
        log_path=Path("unused.log"),
    )


def test_run_sync_finds_low_stock_and_missing_skus(monkeypatch):
    sent = []
    monkeypatch.setattr(sync, "send_slack", lambda url, subject, body: sent.append((url, subject, body)))

    result = run_sync(make_settings(), FakeOdoo({"A": 4, "B": 50, "C": 3}), RUN_AT)

    assert result.products_checked == 3
    assert result.products_missing == ("GONE",)
    assert [level.sku for level in result.low_stock] == ["A", "C"]
    assert result.alerts_sent == 1
    assert len(sent) == 1 and "2 product(s)" in sent[0][1]


def test_run_sync_sends_nothing_when_all_stock_is_healthy(monkeypatch):
    sent = []
    monkeypatch.setattr(sync, "send_slack", lambda *args: sent.append(args))

    result = run_sync(make_settings(), FakeOdoo({"A": 40, "B": 50, "C": 30}), RUN_AT)

    assert result.low_stock == ()
    assert result.alerts_sent == 0
    assert sent == []


def test_channel_none_never_sends(monkeypatch):
    sent = []
    monkeypatch.setattr(sync, "send_slack", lambda *args: sent.append(args))

    result = run_sync(make_settings(channel="none"), FakeOdoo({"A": 0, "B": 0, "C": 0}), RUN_AT)

    assert len(result.low_stock) == 3
    assert result.alerts_sent == 0
    assert sent == []


def test_log_line_has_timestamp_checked_count_and_alerts_sent():
    result = sync.SyncResult(
        products_checked=5,
        products_missing=("X",),
        low_stock=(),
        alerts_sent=0,
    )
    line = format_log_line(RUN_AT, result, "slack")
    assert line.startswith("2026-10-16T09:30:00+00:00 status=ok ")
    assert "products_checked=5" in line
    assert "alerts_sent=0" in line
    assert "missing_skus=X" in line
    assert "low_stock_skus=-" in line


@pytest.mark.parametrize("missing_env", ["ODOO_URL", "ODOO_DB", "ODOO_USER", "ODOO_PASSWORD"])
def test_load_settings_requires_odoo_env(tmp_path, missing_env):
    from app.config import load_settings

    config = tmp_path / "config.toml"
    config.write_text('[alerts]\nchannel = "none"\n[[products]]\nsku = "A"\nreorder_point = 1\n', encoding="utf-8")
    env = {"ODOO_URL": "u", "ODOO_DB": "d", "ODOO_USER": "x", "ODOO_PASSWORD": "p"}
    del env[missing_env]
    with pytest.raises(ValueError, match=missing_env):
        load_settings(config, env)
