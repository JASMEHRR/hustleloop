"""
Optional Gumroad publishing.

Never runs unless GUMROAD_API_KEY is set in the environment -- without it,
generated files just stay in output/ for manual review, which is the
intended default until you trust the pipeline's picks.

A result is only ever marked "published" if Gumroad's API actually
returned success. No silent fake-success, per the loop's core rule.
"""

from __future__ import annotations

import os

import requests

GUMROAD_API_BASE = "https://api.gumroad.com/v2"


def is_configured() -> bool:
    return bool(os.environ.get("GUMROAD_API_KEY"))


def publish_product(name: str, price_cents: int, file_path: str, description: str) -> dict:
    """
    Creates a Gumroad product from a generated file.
    Returns {"status": "published"|"skipped"|"failed", ...details}.
    """
    api_key = os.environ.get("GUMROAD_API_KEY")
    if not api_key:
        return {"status": "skipped", "reason": "GUMROAD_API_KEY not set"}

    try:
        with open(file_path, "rb") as f:
            resp = requests.post(
                f"{GUMROAD_API_BASE}/products",
                data={
                    "access_token": api_key,
                    "name": name[:100],
                    "price": price_cents,
                    "description": description[:500],
                },
                files={"file": f},
                timeout=30,
            )
        data = resp.json()
        if resp.status_code == 200 and data.get("success"):
            return {"status": "published", "product_id": data.get("product", {}).get("id")}
        return {"status": "failed", "reason": data.get("message", f"HTTP {resp.status_code}")}
    except Exception as e:  # noqa: BLE001 -- publishing failures must not crash the run
        return {"status": "failed", "reason": str(e)}
