"""The iPad's Shots reel: what it can land on."""

import re
import sqlite3

from .panel import panel_card
from .recipes import MAKEABLE, load_recipes, shopping_list
from .taxonomy import chain

MIN_UNIQUE = 3

# Liqueurs people drink as straight shots; all spirits count automatically.
SHOOTABLE = {
    "irish-cream", "coffee-liqueur", "jagermeister", "fernet",
    "peppermint-schnapps", "cinnamon-schnapps", "butterscotch-schnapps",
    "sambuca", "anise-liqueur", "rumchata", "southern-comfort", "amaretto",
    "limoncello", "green-chartreuse",
}


def _label(name: str) -> str:
    """'Cinnamon Whisky (Fireball)' -> 'Cinnamon Whisky'."""
    return re.sub(r"\s*\(.*?\)\s*", " ", name).strip()


def basic_type(ingredient_id: str) -> str | None:
    """Which reel entry a bottle belongs to, as an ingredient id, or None if it isn't something you'd shoot."""
    path = chain(ingredient_id)          # nearest first: [node, parent, ..., root]
    if "flavored-spirit" in path:
        return ingredient_id
    if "spirit" in path:
        top = path[path.index("spirit") - 1] if path.index("spirit") > 0 else None
        return top
    for node in path:
        if node in SHOOTABLE:
            return node
    return None


def basic_pool(conn: sqlite3.Connection) -> list[dict]:
    """One entry per shootable type on the shelf, with your bottle names."""
    rows = conn.execute(
        "SELECT product_name, ingredient_id FROM bottle ORDER BY product_name"
    ).fetchall()
    names = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM ingredient")}
    grouped: dict[str, list[str]] = {}
    for row in rows:
        entry = basic_type(row["ingredient_id"])
        if entry is None:
            continue
        bottles = grouped.setdefault(entry, [])
        if row["product_name"] not in bottles:
            bottles.append(row["product_name"])
    return sorted(
        ({"name": _label(names[node]), "bottles": bottles} for node, bottles in grouped.items()),
        key=lambda e: e["name"].lower(),
    )


def panel_shots(conn: sqlite3.Connection) -> dict:
    """Everything the Shots reel needs, in one response."""
    shots = load_recipes(conn, kind="shot")
    unique = [panel_card(r) for r in shots if r["status"] == MAKEABLE]
    suggestions = []
    if len(unique) < MIN_UNIQUE:
        suggestions = [
            {"ingredient_name": s["ingredient_name"], "unlocks": s["unlocks"],
             "recipes": s["recipes"]}
            for s in shopping_list(conn, limit=4, kind="shot")
        ]
    return {
        "basic": basic_pool(conn),
        "unique": unique,
        "min_unique": MIN_UNIQUE,
        "suggestions": suggestions,
    }
