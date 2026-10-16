"""Stock comparison: which products are at or below their reorder point."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class StockLevel:
    sku: str
    name: str
    on_hand: float
    reorder_point: int


def is_low_stock(level: StockLevel) -> bool:
    """A product is low when on-hand is at or below its reorder point."""
    return level.on_hand <= level.reorder_point


def find_low_stock(levels: Iterable[StockLevel]) -> list[StockLevel]:
    """Return the levels that trigger an alert, in the order given."""
    return [level for level in levels if is_low_stock(level)]
