"""Writing recipes: startup seeding, and the edits you make from your phone."""

import hashlib
import json
import re
import sqlite3
from pathlib import Path

from .ranking import rank_for
from .steps import referenced_ids

LIBRARY_PATH = Path(__file__).resolve().parent / "recipe_library.json"

SEEDED_SOURCES = ("curated", "library")

# User recipes sort after the famous drinks, ahead of the long tail.
USER_RANK = 500

KINDS = ("cocktail", "shot")

# Ids that collide with existing routes.
RESERVED_IDS = {"new", "hidden", "random", "shopping-list", "edit"}


# The one upsert everything shares

def _write(conn: sqlite3.Connection, recipe: dict, source: str, rank: int) -> bool:
    """Insert or refresh one seeded recipe."""
    cursor = conn.execute(
        """
        INSERT INTO recipe (id, name, glass, method, garnish, instructions, steps,
                            source, source_ref, kind, rank)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name         = excluded.name,
            glass        = excluded.glass,
            method       = excluded.method,
            garnish      = excluded.garnish,
            instructions = excluded.instructions,
            steps        = excluded.steps,
            source       = excluded.source,
            source_ref   = excluded.source_ref,
            kind         = excluded.kind,
            rank         = excluded.rank
        WHERE recipe.edited = 0 AND recipe.source IN ('curated', 'library')
        """,
        (
            recipe["id"], recipe["name"], recipe.get("glass"), recipe.get("method"),
            recipe.get("garnish"), recipe.get("instructions"),
            # One step per line; steps never contain newlines.
            "\n".join(recipe.get("steps", [])) or None,
            source, recipe.get("source_ref"), recipe.get("kind", "cocktail"), rank,
        ),
    )
    if cursor.rowcount == 0:
        return False
    _replace_lines(conn, recipe["id"], recipe["ingredients"])
    return True


def _replace_lines(conn: sqlite3.Connection, recipe_id: str, ingredients) -> None:
    """Ingredient lines are replaced wholesale rather than merged."""
    conn.execute("DELETE FROM recipe_ingredient WHERE recipe_id = ?", (recipe_id,))
    conn.executemany(
        """
        INSERT INTO recipe_ingredient (recipe_id, position, ingredient_id, amount, optional)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (recipe_id, position, ingredient_id, amount, 1 if optional else 0)
            for position, (ingredient_id, amount, optional) in enumerate(ingredients)
        ],
    )


# Seeding

def seed_curated(conn: sqlite3.Connection) -> None:
    """The hand-written cocktails and shots."""
    from .recipe_data import RECIPES
    from .shot_data import SHOTS

    with conn:
        for recipe in RECIPES:
            _write(conn, recipe, "curated", rank_for(recipe["name"]))
        for shot in SHOTS:
            _write(conn, {**shot, "kind": "shot"}, "curated", rank_for(shot["name"]))


def seed_library(conn: sqlite3.Connection, path: Path = LIBRARY_PATH) -> int:
    """The ~1,000 converted dataset recipes."""
    if not path.exists():
        return 0
    raw = path.read_bytes()
    fingerprint = hashlib.sha256(raw).hexdigest()
    row = conn.execute("SELECT value FROM meta WHERE key = 'library_hash'").fetchone()
    if row and row["value"] == fingerprint:
        return 0

    library = json.loads(raw.decode("utf-8"))
    written = 0
    with conn:
        for recipe in library:
            if _write(conn, recipe, "library", recipe.get("rank", 3000)):
                written += 1
        # Drop recipes that left the library, unless edited.
        keep = {r["id"] for r in library}
        stale = [
            row["id"]
            for row in conn.execute(
                "SELECT id FROM recipe WHERE source = 'library' AND edited = 0"
            )
            if row["id"] not in keep
        ]
        conn.executemany("DELETE FROM recipe WHERE id = ?", [(i,) for i in stale])
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('library_hash', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (fingerprint,),
        )
    return written


# Editing from the phone

class RecipeError(ValueError):
    """Something about a submitted recipe that a person needs to fix."""


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "recipe"


def _clean(data: dict, conn: sqlite3.Connection) -> dict:
    """Validate and tidy a submitted recipe."""
    name = (data.get("name") or "").strip()
    if not name:
        raise RecipeError("Give the drink a name.")
    kind = data.get("kind") or "cocktail"
    if kind not in KINDS:
        raise RecipeError(f"Kind must be one of {', '.join(KINDS)}.")

    lines = []
    for line in data.get("ingredients") or []:
        ingredient_id = line["ingredient_id"]
        if not conn.execute("SELECT 1 FROM ingredient WHERE id = ?", (ingredient_id,)).fetchone():
            raise RecipeError(f"Unknown ingredient '{ingredient_id}'.")
        amount = (line.get("amount") or "").strip() or None
        lines.append((ingredient_id, amount, bool(line.get("optional"))))
    if not lines:
        raise RecipeError("Add at least one ingredient.")
    if len({i for i, _, _ in lines}) != len(lines):
        raise RecipeError("Each ingredient can only appear once.")

    steps = [s.strip() for s in data.get("steps") or [] if s and s.strip()]
    if any("\n" in s for s in steps):
        # Split embedded newlines, since steps are stored one per line.
        steps = [part.strip() for s in steps for part in s.split("\n") if part.strip()]
    dangling = referenced_ids(steps) - {i for i, _, _ in lines}
    if dangling:
        raise RecipeError(
            "A step mentions an ingredient that isn't in the recipe: "
            + ", ".join(sorted(dangling))
            + ". Add it to the ingredients or take it out of the step."
        )

    def text(key):
        value = (data.get(key) or "").strip()
        return value or None

    return {
        "name": name, "kind": kind, "glass": text("glass"), "method": text("method"),
        "garnish": text("garnish"), "instructions": text("instructions"),
        "steps": steps, "ingredients": lines,
    }


def create_recipe(conn: sqlite3.Connection, data: dict) -> str:
    """A brand-new drink from your phone."""
    recipe = _clean(data, conn)
    base = _slugify(recipe["name"])
    recipe_id, n = (base, 2) if base not in RESERVED_IDS else (f"{base}-2", 3)
    while conn.execute("SELECT 1 FROM recipe WHERE id = ?", (recipe_id,)).fetchone():
        recipe_id, n = f"{base}-{n}", n + 1
    with conn:
        conn.execute(
            """
            INSERT INTO recipe (id, name, glass, method, garnish, instructions, steps,
                                source, kind, rank)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'user', ?, ?)
            """,
            (recipe_id, recipe["name"], recipe["glass"], recipe["method"],
             recipe["garnish"], recipe["instructions"],
             "\n".join(recipe["steps"]) or None, recipe["kind"], USER_RANK),
        )
        _replace_lines(conn, recipe_id, recipe["ingredients"])
    return recipe_id


def update_recipe(conn: sqlite3.Connection, recipe_id: str, data: dict) -> bool:
    """Replace a recipe with your edited version."""
    recipe = _clean(data, conn)
    with conn:
        cursor = conn.execute(
            """
            UPDATE recipe
               SET name = ?, glass = ?, method = ?, garnish = ?, instructions = ?,
                   steps = ?, kind = ?, edited = 1
             WHERE id = ?
            """,
            (recipe["name"], recipe["glass"], recipe["method"], recipe["garnish"],
             recipe["instructions"], "\n".join(recipe["steps"]) or None,
             recipe["kind"], recipe_id),
        )
        if cursor.rowcount == 0:
            return False
        _replace_lines(conn, recipe_id, recipe["ingredients"])
    return True


def set_hidden(conn: sqlite3.Connection, recipe_id: str, hidden: bool) -> bool:
    """Take a drink off every list, or put it back."""
    with conn:
        cursor = conn.execute(
            "UPDATE recipe SET hidden = ? WHERE id = ?", (1 if hidden else 0, recipe_id)
        )
    return cursor.rowcount > 0
