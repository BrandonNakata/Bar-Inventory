"""The iPad wall panel's view of the recipes."""

import sqlite3

from .recipes import MAKEABLE, load_recipes


def _line(line: dict) -> dict:
    """One ingredient line, in the three fields the panel draws."""
    name = line["ingredient_name"]
    if line["optional"]:
        # Label optional lines so they don't read as the blocker.
        name += " (optional)"
    return {"name": name, "amount": line["amount"], "have": line["have"]}


def _instructions(recipe: dict) -> str | None:
    """The method, with the garnish folded in."""
    text, garnish = recipe["instructions"], recipe["garnish"]
    # Skip the garnish if the method already mentions it.
    if not garnish or (text and garnish.lower() in text.lower()):
        return text
    if not text:
        return f"Garnish: {garnish}."
    return f"{text.rstrip('.')}. Garnish: {garnish}."


def panel_card(r: dict) -> dict:
    """One recipe in the panel's shape."""
    return {
        "id": r["id"],
        "name": r["name"],
        "glass": r["glass"],
        "method": r["method"],
        "ingredients": [_line(line) for line in r["ingredients"]],
        "missing": [line["ingredient_name"] for line in r["missing"]],
        "instructions": _instructions(r),
        # Pre-rendered steps; the panel never sees placeholders.
        "steps": r["steps"],
        # Old panels ignore keys they don't read.
        "base": r["base"],
    }


def panel_recipes(conn: sqlite3.Connection) -> dict:
    """Everything the panel's Bar tab needs, in one response."""
    recipes = load_recipes(conn, kind="cocktail")
    inventory = conn.execute("SELECT COUNT(*) AS c FROM bottle").fetchone()["c"]

    return {
        "inventory_count": inventory,
        "ready_count": sum(1 for r in recipes if r["status"] == MAKEABLE),
        "recipes": [panel_card(r) for r in recipes],
    }
