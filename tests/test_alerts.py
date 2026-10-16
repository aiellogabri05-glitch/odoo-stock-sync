from datetime import datetime, timezone

from app.alerts import build_alert_message
from app.stock import StockLevel

RUN_AT = datetime(2026, 10, 16, 9, 30, tzinfo=timezone.utc)


def item(sku: str, on_hand: float, reorder_point: int = 10) -> StockLevel:
    return StockLevel(sku=sku, name=f"Name {sku}", on_hand=on_hand, reorder_point=reorder_point)


def test_subject_counts_low_stock_products():
    subject, _ = build_alert_message([item("A", 2), item("B", 5)], products_checked=5, run_at=RUN_AT)
    assert subject == "[Stock alert] 2 product(s) at or below reorder point"


def test_body_lists_every_low_stock_sku_with_quantities():
    _, body = build_alert_message([item("A", 2), item("B", 5, 8)], products_checked=5, run_at=RUN_AT)
    assert "- A Name A: on hand 2, reorder point 10" in body
    assert "- B Name B: on hand 5, reorder point 8" in body


def test_body_sorts_lowest_stock_first():
    _, body = build_alert_message([item("B", 5), item("A", 2), item("C", -1)], products_checked=3, run_at=RUN_AT)
    lines = [line for line in body.splitlines() if line.startswith("- ")]
    assert [line.split()[1] for line in lines] == ["C", "A", "B"]


def test_body_header_has_run_time_and_counts():
    _, body = build_alert_message([item("A", 2)], products_checked=5, run_at=RUN_AT)
    assert body.splitlines()[0] == "Low-stock check at 2026-10-16 09:30 UTC"
    assert "Products checked: 5" in body
    assert "Low-stock products: 1" in body


def test_fractional_quantities_keep_decimals():
    _, body = build_alert_message([item("A", 2.5)], products_checked=1, run_at=RUN_AT)
    assert "on hand 2.5" in body
