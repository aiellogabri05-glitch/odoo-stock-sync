"""Build the low-stock alert message and send it by Slack webhook or SMTP."""

from __future__ import annotations

import json
import smtplib
import urllib.request
from collections.abc import Sequence
from datetime import datetime
from email.message import EmailMessage

from app.stock import StockLevel


def build_alert_message(low_items: Sequence[StockLevel], products_checked: int, run_at: datetime) -> tuple[str, str]:
    """Return (subject, body) listing every low-stock product, lowest stock first."""
    subject = f"[Stock alert] {len(low_items)} product(s) at or below reorder point"
    lines = [
        f"Low-stock check at {run_at:%Y-%m-%d %H:%M} UTC",
        f"Products checked: {products_checked}",
        f"Low-stock products: {len(low_items)}",
        "",
    ]
    for item in sorted(low_items, key=lambda level: (level.on_hand, level.sku)):
        lines.append(
            f"- {item.sku} {item.name}: on hand {_fmt_qty(item.on_hand)}, reorder point {item.reorder_point}"
        )
    return subject, "\n".join(lines)


def _fmt_qty(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def send_slack(webhook_url: str, subject: str, body: str) -> None:
    payload = json.dumps({"text": f"*{subject}*\n```\n{body}\n```"}).encode("utf-8")
    request = urllib.request.Request(
        webhook_url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status >= 300:
            raise RuntimeError(f"Slack webhook returned HTTP {response.status}")


def send_email(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
) -> None:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        smtp.starttls()
        if user:
            smtp.login(user, password)
        smtp.send_message(message)
