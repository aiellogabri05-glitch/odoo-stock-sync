"""Seed test products in a LOCAL Odoo, or set the on-hand quantity of one product.

Only point this at the local docker-compose Odoo (http://localhost:8069). It refuses any other URL.

    python scripts/odoo_stock.py seed
    python scripts/odoo_stock.py list
    python scripts/odoo_stock.py set TEST-1001 4
"""

from __future__ import annotations

import argparse
import os
import sys
import xmlrpc.client
from urllib.parse import urlparse

SEED_PRODUCTS = [
    ("TEST-1001", "Test Widget Blue", 40),
    ("TEST-1002", "Test Widget Red", 12),
    ("TEST-1003", "Test Gasket Pack", 30),
    ("TEST-1004", "Test Bracket Small", 8),
    ("TEST-1005", "Test Cable Tie 100pk", 60),
]

LOCAL_HOSTS = {"localhost", "127.0.0.1"}


class Odoo:
    def __init__(self) -> None:
        url = os.environ.get("ODOO_URL", "http://localhost:8069").rstrip("/")
        if urlparse(url).hostname not in LOCAL_HOSTS:
            sys.exit(f"Refusing to run against {url}: this script is for the local test Odoo only.")
        self.db = os.environ["ODOO_DB"]
        self.password = os.environ["ODOO_PASSWORD"]
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
        self.uid = common.authenticate(self.db, os.environ["ODOO_USER"], self.password, {})
        if not self.uid:
            sys.exit("Login failed. Check ODOO_DB, ODOO_USER and ODOO_PASSWORD.")
        self.models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)

    def call(self, model, method, args, kwargs=None):
        return self.models.execute_kw(self.db, self.uid, self.password, model, method, args, kwargs or {})

    def find_product(self, sku):
        ids = self.call("product.product", "search", [[["default_code", "=", sku]]], {"limit": 1})
        return ids[0] if ids else None

    def create_product(self, sku, name):
        return self.call("product.product", "create", [{"default_code": sku, "name": name, "type": "product"}])

    def internal_location(self):
        ids = self.call("stock.location", "search", [[["usage", "=", "internal"]]], {"limit": 1})
        if not ids:
            sys.exit("No internal stock location found. Is the Inventory app installed?")
        return ids[0]

    def set_on_hand(self, product_id, qty):
        """Set on-hand by counting the product in the internal location and applying the count."""
        location_id = self.internal_location()
        quant_ctx = {"inventory_mode": True}
        quant_ids = self.call(
            "stock.quant",
            "search",
            [[["product_id", "=", product_id], ["location_id", "=", location_id]]],
            {"limit": 1},
        )
        if quant_ids:
            quant_id = quant_ids[0]
            self.models.execute_kw(
                self.db, self.uid, self.password, "stock.quant", "write",
                [[quant_id], {"inventory_quantity": qty}], {"context": quant_ctx},
            )
        else:
            quant_id = self.models.execute_kw(
                self.db, self.uid, self.password, "stock.quant", "create",
                [{"product_id": product_id, "location_id": location_id, "inventory_quantity": qty}],
                {"context": quant_ctx},
            )
        try:
            self.models.execute_kw(
                self.db, self.uid, self.password, "stock.quant", "action_apply_inventory",
                [[quant_id]], {"context": quant_ctx},
            )
        except xmlrpc.client.Fault as exc:
            # Odoo 17 applies the count, then fails to marshal its None return value over XML-RPC.
            # Only accept that specific fault; anything else is a real error.
            if "cannot marshal None" not in exc.faultString:
                raise
        applied = self.call("stock.quant", "read", [[quant_id]], {"fields": ["quantity"]})[0]["quantity"]
        if float(applied) != float(qty):
            sys.exit(f"Stock for product {product_id} is {applied}, expected {qty}: count was not applied.")


def cmd_seed(odoo: Odoo) -> None:
    for sku, name, qty in SEED_PRODUCTS:
        product_id = odoo.find_product(sku) or odoo.create_product(sku, name)
        odoo.set_on_hand(product_id, qty)
        print(f"seeded {sku} {name} on_hand={qty}")


def cmd_list(odoo: Odoo) -> None:
    rows = odoo.call(
        "product.product",
        "search_read",
        [[["default_code", "like", "TEST-"]]],
        {"fields": ["default_code", "name", "qty_available"], "order": "default_code"},
    )
    print(f"{'Internal Reference':<20}{'Product':<26}{'On hand':>8}")
    for row in rows:
        print(f"{row['default_code']:<20}{row['name']:<26}{row['qty_available']:>8g}")


def cmd_set(odoo: Odoo, sku: str, qty: float) -> None:
    product_id = odoo.find_product(sku)
    if product_id is None:
        sys.exit(f"No product with Internal Reference {sku}. Run 'seed' first.")
    odoo.set_on_hand(product_id, qty)
    print(f"set {sku} on_hand={qty:g}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed")
    sub.add_parser("list")
    set_parser = sub.add_parser("set")
    set_parser.add_argument("sku")
    set_parser.add_argument("qty", type=float)
    args = parser.parse_args()

    odoo = Odoo()
    if args.command == "seed":
        cmd_seed(odoo)
    elif args.command == "list":
        cmd_list(odoo)
    else:
        cmd_set(odoo, args.sku, args.qty)


if __name__ == "__main__":
    main()
