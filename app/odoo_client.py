"""Read on-hand quantities from Odoo over XML-RPC."""

from __future__ import annotations

import xmlrpc.client
from collections.abc import Iterable
from dataclasses import dataclass


class OdooError(RuntimeError):
    """Raised when Odoo rejects the login or a call fails."""


@dataclass(frozen=True)
class OdooProduct:
    sku: str
    name: str
    on_hand: float


class OdooClient:
    def __init__(self, url: str, db: str, user: str, password: str) -> None:
        self._db = db
        self._password = password
        self._common = xmlrpc.client.ServerProxy(f"{url.rstrip('/')}/xmlrpc/2/common", allow_none=True)
        self._models = xmlrpc.client.ServerProxy(f"{url.rstrip('/')}/xmlrpc/2/object", allow_none=True)
        self._uid = self._common.authenticate(db, user, password, {})
        if not self._uid:
            raise OdooError(f"Odoo login failed for user {user!r} on database {db!r}")

    def fetch_products(self, skus: Iterable[str]) -> dict[str, OdooProduct]:
        """Return the on-hand quantity (all warehouses) for each SKU that exists in Odoo.

        SKUs that Odoo does not know about are simply absent from the result.
        """
        sku_list = list(skus)
        if not sku_list:
            return {}
        try:
            records = self._models.execute_kw(
                self._db,
                self._uid,
                self._password,
                "product.product",
                "search_read",
                [[["default_code", "in", sku_list]]],
                {"fields": ["default_code", "name", "qty_available"]},
            )
        except xmlrpc.client.Fault as exc:
            raise OdooError(f"Odoo call failed: {exc.faultString}") from exc
        products = {}
        for record in records:
            sku = record["default_code"]
            products[sku] = OdooProduct(sku=sku, name=record["name"], on_hand=float(record["qty_available"]))
        return products
