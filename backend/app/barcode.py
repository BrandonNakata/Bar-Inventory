"""Barcode -> product: validation, online lookup, and the cache that makes every barcode a one-time question."""

import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

from .taxonomy import suggest_ingredient

# Open Food Facts asks clients to identify themselves; set BAR_USER_AGENT to add a contact.
USER_AGENT = os.getenv("BAR_USER_AGENT", "BarInventory/0.3 (home bar portfolio project)")

# Fail fast so the user can type the name instead.
TIMEOUT_SECONDS = 4

# Re-ask cached misses after this long; the open databases grow.
MISS_RETRY_DAYS = 30


class InvalidBarcode(ValueError):
    """The input can't be a barcode."""


class LookupUnavailable(Exception):
    """A source couldn't be asked: network down, timeout, rate limit, 5xx."""


@dataclass
class Product:
    name: str
    brand: str | None
    source: str


# Validation

def gtin_check_digit(body: str) -> int:
    """The last digit of every retail barcode is arithmetic on the others."""
    total = sum(int(digit) * (3 if i % 2 == 0 else 1) for i, digit in enumerate(reversed(body)))
    return (10 - total % 10) % 10


def normalize_barcode(raw: str) -> str:
    """Clean up and validate a barcode, returning one canonical form."""
    digits = re.sub(r"[\s-]", "", raw or "")
    if not digits:
        raise InvalidBarcode("Enter a barcode.")
    if not digits.isdigit():
        raise InvalidBarcode("A barcode is digits only.")
    if len(digits) not in (8, 12, 13, 14):
        raise InvalidBarcode(
            f"Barcodes are 8, 12, 13 or 14 digits long; that one is {len(digits)}."
        )
    if gtin_check_digit(digits[:-1]) != int(digits[-1]):
        raise InvalidBarcode("That barcode's check digit doesn't add up; probably a typo.")
    if len(digits) == 12:
        digits = "0" + digits
    elif len(digits) == 14 and digits.startswith("0"):
        digits = digits[1:]
    return digits


# Sources

def compose_name(brand: str | None, name: str | None) -> str:
    """Join brand and product name without repeating the brand."""
    brand = (brand or "").strip()
    name = (name or "").strip()
    if not name:
        return brand
    if not brand or brand.lower() in name.lower():
        return name
    return f"{brand} {name}"


def _get_json(url: str) -> tuple[int, dict | None]:
    """GET a URL, return (status, parsed body)."""
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        # urllib raises on 404 and 429, but those are answers, not failures.
        try:
            body = json.loads(err.read().decode("utf-8"))
        except Exception:
            body = None
        return err.code, body
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as err:
        raise LookupUnavailable(str(getattr(err, "reason", err))) from err


def open_food_facts(barcode: str) -> Product | None:
    """Open Food Facts: free, no key, openly licensed (ODbL), 15 reads/min."""
    url = (
        f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
        "?fields=product_name,product_name_en,brands"
    )
    status, body = _get_json(url)
    if status == 404:
        return None
    if status != 200 or body is None:
        raise LookupUnavailable(f"Open Food Facts answered HTTP {status}")
    if body.get("status") != 1:
        return None
    product = body.get("product") or {}
    name = product.get("product_name_en") or product.get("product_name")
    brand = (product.get("brands") or "").split(",")[0].strip() or None
    if not (name or brand):
        return None
    return Product(compose_name(brand, name), brand, "openfoodfacts")


def upcitemdb(barcode: str) -> Product | None:
    """UPCitemdb's free trial endpoint: no signup, 100 lookups/day, 6/minute."""
    url = "https://api.upcitemdb.com/prod/trial/lookup?" + urllib.parse.urlencode(
        {"upc": barcode}
    )
    status, body = _get_json(url)
    if status in (400, 404):
        # 400 means an unsupported code format; treat it as not found.
        return None
    if status != 200 or body is None:
        raise LookupUnavailable(f"UPCitemdb answered HTTP {status}")
    items = body.get("items") or []
    if not items:
        return None
    title = (items[0].get("title") or "").strip()
    brand = (items[0].get("brand") or "").strip() or None
    if not (title or brand):
        return None
    return Product(compose_name(brand, title), brand, "upcitemdb")


# Tried in order.
Source = Callable[[str], "Product | None"]
SOURCES: list[tuple[str, Source]] = [
    ("Open Food Facts", open_food_facts),
    ("UPCitemdb", upcitemdb),
]


# The cache

def resolve_barcode(
    conn: sqlite3.Connection,
    barcode: str,
    sources: list[tuple[str, Source]] = SOURCES,
) -> dict:
    """What is this barcode?"""
    row = conn.execute(
        """
        SELECT barcode, product_name, brand, source, ingredient_id,
               (source = 'none'
                AND looked_up_at < datetime('now', ?)) AS stale_miss
          FROM barcode_product
         WHERE barcode = ?
        """,
        (f"-{MISS_RETRY_DAYS} days", barcode),
    ).fetchone()

    if row and not row["stale_miss"]:
        return {
            "barcode": barcode,
            "product_name": row["product_name"],
            "brand": row["brand"],
            "source": row["source"],
            "ingredient_id": row["ingredient_id"],
            "cached": True,
            "lookup_error": None,
        }

    unreachable = []
    for label, fetch in sources:
        try:
            product = fetch(barcode)
        except LookupUnavailable:
            unreachable.append(label)
            continue
        if product:
            with conn:
                conn.execute(
                    """
                    INSERT INTO barcode_product (barcode, product_name, brand, source)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(barcode) DO UPDATE SET
                        product_name = excluded.product_name,
                        brand        = excluded.brand,
                        source       = excluded.source,
                        looked_up_at = datetime('now')
                    """,
                    (barcode, product.name, product.brand, product.source),
                )
            return {
                "barcode": barcode,
                "product_name": product.name,
                "brand": product.brand,
                "source": product.source,
                "ingredient_id": row["ingredient_id"] if row else None,
                "cached": False,
                "lookup_error": None,
            }

    # Only cache a miss if every source actually answered.
    if not unreachable:
        with conn:
            conn.execute(
                """
                INSERT INTO barcode_product (barcode, product_name, source)
                VALUES (?, NULL, 'none')
                ON CONFLICT(barcode) DO UPDATE SET looked_up_at = datetime('now')
                """,
                (barcode,),
            )

    return {
        "barcode": barcode,
        "product_name": None,
        "brand": None,
        "source": "none",
        "ingredient_id": row["ingredient_id"] if row else None,
        "cached": False,
        "lookup_error": (
            f"Couldn't reach {' or '.join(unreachable)} right now." if unreachable else None
        ),
    }


def remember_barcode(
    conn: sqlite3.Connection, barcode: str, product_name: str, ingredient_id: str
) -> None:
    """After you add a bottle with a barcode, record what you confirmed."""
    conn.execute(
        """
        INSERT INTO barcode_product (barcode, product_name, source, ingredient_id)
        VALUES (?, ?, 'manual', ?)
        ON CONFLICT(barcode) DO UPDATE SET
            product_name  = excluded.product_name,
            ingredient_id = excluded.ingredient_id,
            source        = CASE WHEN barcode_product.source = 'none'
                                 THEN 'manual' ELSE barcode_product.source END
        """,
        (barcode, product_name, ingredient_id),
    )


def barcode_report(
    conn: sqlite3.Connection,
    barcode: str,
    sources: list[tuple[str, Source]] = SOURCES,
) -> dict:
    """Everything the UI needs after a scan: product, confirmed category, a guess, and matching bottles."""
    result = resolve_barcode(conn, barcode, sources)

    names = dict(conn.execute("SELECT id, name FROM ingredient").fetchall())

    suggested = None
    if not result["ingredient_id"] and result["product_name"]:
        suggested = suggest_ingredient(conn, result["product_name"])

    on_shelf = conn.execute(
        """
        SELECT b.id, b.product_name, b.ingredient_id, b.barcode, b.added_at,
               i.name AS ingredient_name
          FROM bottle b
          JOIN ingredient i ON i.id = b.ingredient_id
         WHERE b.barcode = ?
         ORDER BY b.id DESC
        """,
        (barcode,),
    ).fetchall()

    return {
        **result,
        "found": result["product_name"] is not None,
        "ingredient_name": names.get(result["ingredient_id"]),
        "suggested_ingredient_id": suggested,
        "suggested_ingredient_name": names.get(suggested),
        "on_shelf": [dict(row) for row in on_shelf],
    }


# Diagnostic

def _diagnose(raw: str) -> int:
    """Ask every source directly, skipping the cache, and print the answers."""
    try:
        barcode = normalize_barcode(raw)
    except InvalidBarcode as err:
        print(f"invalid: {err}")
        return 1
    print(f"normalised: {barcode}\nuser-agent: {USER_AGENT}\n")
    for label, fetch in SOURCES:
        try:
            product = fetch(barcode)
        except LookupUnavailable as err:
            print(f"{label:16s} UNREACHABLE  {err}")
            continue
        print(f"{label:16s} {'found' if product else 'not found':11s}  {product or ''}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m app.barcode <barcode>")
        sys.exit(2)
    sys.exit(_diagnose(sys.argv[1]))
