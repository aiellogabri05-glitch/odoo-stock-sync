"""STAND-IN for a local Odoo, used only when Docker cannot run Odoo.

It speaks the same XML-RPC endpoints the sync uses (/xmlrpc/2/common and /xmlrpc/2/object) and
answers the one call the sync makes: product.product search_read on default_code.
Stock is read from fake_odoo_data.json on every request, so editing that file changes stock
the way a stock move in Odoo would. It is NOT Odoo and is not a substitute for the Docker test.

    python scripts/fake_odoo_server.py --port 8069
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from xmlrpc.server import SimpleXMLRPCRequestHandler, SimpleXMLRPCServer

DATA_FILE = Path(__file__).with_name("fake_odoo_data.json")
DB = "odoo_test"
USER = "admin"
PASSWORD = "admin"
UID = 2


def authenticate(db, user, password, _context):
    return UID if (db, user, password) == (DB, USER, PASSWORD) else False


def execute_kw(db, uid, password, model, method, args, kwargs=None):
    if (db, uid, password) != (DB, UID, PASSWORD):
        raise PermissionError("access denied")
    if model != "product.product" or method != "search_read":
        raise NotImplementedError(f"stand-in only supports product.product.search_read, got {model}.{method}")
    domain = args[0]
    wanted = None
    for clause in domain:
        if clause[0] == "default_code" and clause[1] == "in":
            wanted = set(clause[2])
    products = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    rows = [p for p in products if wanted is None or p["default_code"] in wanted]
    fields = (kwargs or {}).get("fields")
    if fields:
        rows = [{key: row[key] for key in fields} for row in rows]
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8069)
    args = parser.parse_args()

    class Handler(SimpleXMLRPCRequestHandler):
        # Same endpoints and method names as a real Odoo: /xmlrpc/2/common and /xmlrpc/2/object.
        rpc_paths = ("/xmlrpc/2/common", "/xmlrpc/2/object")

    server = SimpleXMLRPCServer(("127.0.0.1", args.port), Handler, allow_none=True, logRequests=False)
    server.register_function(authenticate, "authenticate")
    server.register_function(execute_kw, "execute_kw")
    print(f"stand-in Odoo XML-RPC on http://127.0.0.1:{args.port} (db={DB}, user={USER})", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
