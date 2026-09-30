"""Recipe matching: what can you actually make right now?"""

import random
import re
import sqlite3

from .steps import render
from .taxonomy import ancestor_ids, family_of, is_spirit, satisfiable_ids

# The number of missing required ingredients decides the bucket.
MAKEABLE = "makeable"
ONE_SHORT = "one_short"
NOT_TONIGHT = "not_tonight"

_BUCKET_ORDER = {MAKEABLE: 0, ONE_SHORT: 1, NOT_TONIGHT: 2}


def load_recipes(
    conn: sqlite3.Connection,
    available: set[str] | None = None,
    kind: str | None = "cocktail",
    hidden: str = "exclude",
) -> list[dict]:
    """Every recipe, with each ingredient marked have/missing and a status."""
    if available is None:
        available = satisfiable_ids(conn)

    where, params = [], []
    if kind:
        where.append("kind = ?")
        params.append(kind)
    if hidden == "exclude":
        where.append("hidden = 0")
    elif hidden == "only":
        where.append("hidden = 1")
    clause = f"WHERE {' AND '.join(where)}" if where else ""

    recipe_rows = conn.execute(
        f"""
        SELECT id, name, glass, method, garnish, instructions, steps, source,
               kind, rank, hidden, edited
          FROM recipe
          {clause}
        """,
        params,
    ).fetchall()

    line_rows = conn.execute(
        """
        SELECT ri.recipe_id, ri.position, ri.ingredient_id, ri.amount,
               ri.optional, ri.note, i.name AS ingredient_name
          FROM recipe_ingredient ri
          JOIN ingredient i ON i.id = ri.ingredient_id
         ORDER BY ri.recipe_id, ri.position
        """
    ).fetchall()

    # For a step that names an ingredient the recipe no longer has.
    names = {row["id"]: row["name"] for row in conn.execute("SELECT id, name FROM ingredient")}

    # Group the lines by recipe in one pass.
    lines_by_recipe: dict[str, list[dict]] = {}
    for row in line_rows:
        lines_by_recipe.setdefault(row["recipe_id"], []).append(
            {
                "ingredient_id": row["ingredient_id"],
                "ingredient_name": row["ingredient_name"],
                "amount": row["amount"],
                "optional": bool(row["optional"]),
                "note": row["note"],
                # The actual check.
                "have": row["ingredient_id"] in available,
            }
        )

    recipes = []
    for row in recipe_rows:
        lines = lines_by_recipe.get(row["id"], [])

        # Optional lines never block a drink.
        missing = [
            line for line in lines if not line["have"] and not line["optional"]
        ]

        if not missing:
            status = MAKEABLE
        elif len(missing) == 1:
            status = ONE_SHORT
        else:
            status = NOT_TONIGHT

        template = _steps(row["steps"])
        recipes.append(
            {
                "id": row["id"],
                "name": row["name"],
                "kind": row["kind"],
                "glass": row["glass"],
                "method": row["method"],
                "garnish": row["garnish"],
                "instructions": row["instructions"],
                # Rendered for reading; the template for the phone's editor.
                "steps": render(template, lines, names),
                "steps_template": template,
                "source": row["source"],
                "rank": row["rank"],
                "base": base_family(lines),
                "hidden": bool(row["hidden"]),
                "edited": bool(row["edited"]),
                "ingredients": lines,
                "missing": missing,
                "status": status,
            }
        )

    # Makeable first, then most commonly ordered, then A to Z.
    recipes.sort(key=lambda r: (_BUCKET_ORDER[r["status"]], r["rank"], r["name"].lower()))
    return recipes


def _steps(text: str | None) -> list[str]:
    """The stored one-step-per-line text back into a list."""
    if not text:
        return []
    return [step.strip() for step in text.split("\n") if step.strip()]


def _oz(amount: str | None) -> float:
    """'1 1/2 oz' -> 1.5."""
    match = re.fullmatch(r"(\d+)?\s*(?:(\d+)/(\d+))?\s*oz(?: float)?", (amount or "").strip())
    if not match or not (match.group(1) or match.group(2)):
        return 0.0
    whole = int(match.group(1) or 0)
    frac = int(match.group(2)) / int(match.group(3)) if match.group(2) else 0.0
    return whole + frac


def base_family(lines: list[dict]) -> str:
    """The spirit a drink is built on, for the iPad's chips: the spirit line with the biggest pour."""
    best, best_oz = None, -1.0
    for line in lines:
        if not is_spirit(line["ingredient_id"]):
            continue
        oz = _oz(line["amount"])
        if oz > best_oz:
            best, best_oz = line["ingredient_id"], oz
    return family_of(best)


def get_recipe(conn: sqlite3.Connection, recipe_id: str) -> dict | None:
    """One recipe by id -- any kind, hidden or not -- with the same markings."""
    for recipe in load_recipes(conn, kind=None, hidden="include"):
        if recipe["id"] == recipe_id:
            return recipe
    return None


def random_makeable(conn: sqlite3.Connection) -> dict | None:
    """Pick something you can make right now, at random."""
    options = [r for r in load_recipes(conn) if r["status"] == MAKEABLE]
    return random.choice(options) if options else None


def shopping_list(conn: sqlite3.Connection, limit: int = 5, kind: str = "cocktail") -> list[dict]:
    """Which single bottle would unlock the most drinks?"""
    available = satisfiable_ids(conn)
    recipes = load_recipes(conn, available, kind=kind)
    one_short = [r for r in recipes if r["status"] == ONE_SHORT]

    # Only ingredients a one-short recipe is missing can unlock anything.
    candidates = {r["missing"][0]["ingredient_id"] for r in one_short}

    suggestions = []
    for candidate in candidates:
        covers = set(ancestor_ids(conn, candidate))
        unlocked = [
            r for r in one_short if r["missing"][0]["ingredient_id"] in covers
        ]
        name_row = conn.execute(
            "SELECT name FROM ingredient WHERE id = ?", (candidate,)
        ).fetchone()
        suggestions.append(
            {
                "ingredient_id": candidate,
                "ingredient_name": name_row["name"] if name_row else candidate,
                "unlocks": len(unlocked),
                "recipes": [r["name"] for r in unlocked],
            }
        )

    # Ties break alphabetically so the order is stable.
    suggestions.sort(key=lambda s: (-s["unlocks"], s["ingredient_name"]))
    return suggestions[:limit]
