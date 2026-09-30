"""Generate the frontend's demo fixtures from the real taxonomy and recipes."""

import json
import sqlite3
from pathlib import Path

from app.barcode import InvalidBarcode, normalize_barcode
from app.db import SCHEMA, migrate
from app.ranking import rank_for
from app.recipe_data import RECIPES, seed_recipes
from app.recipe_store import LIBRARY_PATH, seed_library
from app.recipes import load_recipes, shopping_list
from app.shot_data import SHOTS
from app.taxonomy import ALIASES, ASSUMED_ON_HAND, TAXONOMY, seed

OUT_PATH = Path(__file__).resolve().parent.parent / "frontend" / "src" / "api" / "demoData.js"

# Starter shelf chosen so all three buckets have drinks on first load.
DEMO_BOTTLES = [
    (1,  "Carpano Antica Formula",      "sweet-vermouth"),
    (2,  "Dolin Dry Vermouth",          "dry-vermouth"),
    (3,  "Tanqueray London Dry Gin",    "london-dry-gin"),
    (4,  "Campari",                     "campari"),
    (5,  "Bulleit Rye",                 "rye-whiskey"),
    (6,  "Buffalo Trace Bourbon",       "bourbon"),
    (7,  "Bacardí Superior",            "white-rum"),
    (8,  "Espolòn Blanco",              "blanco-tequila"),
    (9,  "Cointreau",                   "triple-sec"),
    (10, "Angostura Aromatic Bitters",  "aromatic-bitters"),
    (11, "Luxardo Maraschino",          "maraschino"),
    (12, "Simple Syrup (house)",        "simple-syrup"),
    (13, "Fresh Lime Juice",            "lime-juice"),
    # Extra bottles so the Unique shots reel has enough to spin.
    (14, "Tito's Handmade Vodka",       "vodka"),
    (15, "Jameson Irish Whiskey",       "irish-whiskey"),
    (16, "Baileys Original Irish Cream", "irish-cream"),
    (17, "Kahlúa",                      "coffee-liqueur"),
    (18, "DeKuyper Peachtree",          "peach-schnapps"),
    (19, "Cranberry Juice",             "cranberry-juice"),
    (20, "Fresh Lemon Juice",           "lemon-juice"),
]

# Shelves the JS vs Python parity check runs.
PARITY_SHELVES = {
    "demo": [ingredient_id for _, _, ingredient_id in DEMO_BOTTLES],
    "empty": [],
    "tie": ["gin", "campari"],
    "reach": ["campari", "sweet-vermouth", "green-chartreuse", "maraschino", "lime-juice"],
    "staples": ["cachaca", "lime-juice"],
}

# Barcode cases the parity check runs through both implementations.
BARCODE_CASES = [
    "036000291452", "0036000291452", " 0 36000 29145 2 ", "4-006381-333931",
    "00036000291452", "96385074", "4006381333931",
    "036000291453", "03600029145X", "12345", "", "   ",
]

NAMES = {ingredient_id: name for ingredient_id, name, _ in TAXONOMY}


def js_array(rows: list[dict]) -> str:
    """Pretty-print one object per line -- diffs stay readable in git."""
    return "[\n" + "".join(
        f"  {json.dumps(row, ensure_ascii=False)},\n" for row in rows
    ) + "]"


def python_verdicts(shelf: list[str], detail: bool = False) -> dict:
    """Ask the real backend code what it thinks of this shelf."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    migrate(conn)
    seed(conn)
    seed_recipes(conn)
    seed_library(conn)
    with conn:
        conn.executemany(
            "INSERT INTO bottle (product_name, ingredient_id) VALUES (?, ?)",
            [(ingredient_id, ingredient_id) for ingredient_id in shelf],
        )
    recipes = load_recipes(conn)
    verdict = {
        "shelf": shelf,
        "order": [r["id"] for r in recipes],
        "status": {r["id"]: r["status"] for r in recipes},
        "missing": {r["id"]: [line["ingredient_id"] for line in r["missing"]] for r in recipes},
        "shopping": shopping_list(conn, limit=5),
    }
    if detail:
        # Steps and spirit chips, for the JS vs Python parity check.
        verdict["steps"] = {r["id"]: r["steps"] for r in recipes}
        verdict["base"] = {r["id"]: r["base"] for r in recipes}
    conn.close()
    return verdict


def main() -> None:
    ingredients = [
        {
            "id": ingredient_id,
            "name": name,
            "parent_id": parent,
            "assumed_on_hand": ingredient_id in ASSUMED_ON_HAND,
        }
        for ingredient_id, name, parent in TAXONOMY
    ]

    bottles = [
        {
            "id": bottle_id,
            "product_name": product_name,
            "ingredient_id": ingredient_id,
            "ingredient_name": NAMES[ingredient_id],
            "barcode": None,
            "added_at": "2026-09-19 18:00:00",
        }
        for bottle_id, product_name, ingredient_id in DEMO_BOTTLES
    ]

    unknown = [b["ingredient_id"] for b in bottles if b["ingredient_id"] not in NAMES]
    if unknown:
        raise SystemExit(f"Demo bottles reference unknown categories: {unknown}")

    def demo_recipe(recipe, source, kind, rank):
        return {
            "id": recipe["id"],
            "name": recipe["name"],
            "kind": kind,
            "rank": rank,
            "glass": recipe.get("glass"),
            "method": recipe.get("method"),
            "garnish": recipe.get("garnish"),
            "instructions": recipe.get("instructions"),
            "source": source,
            "steps": recipe.get("steps", []),
            "hidden": False,
            "edited": False,
            "ingredients": [
                {"ingredient_id": ingredient_id, "amount": amount, "optional": optional}
                for ingredient_id, amount, optional in recipe["ingredients"]
            ],
        }

    library = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    recipes = (
        [demo_recipe(r, "curated", "cocktail", rank_for(r["name"])) for r in RECIPES]
        + [demo_recipe(r, "curated", "shot", rank_for(r["name"])) for r in SHOTS]
        + [demo_recipe(r, "library", r["kind"], r["rank"]) for r in library]
    )

    expected = {
        name: python_verdicts(shelf, detail=(name == "demo"))
        for name, shelf in PARITY_SHELVES.items()
    }

    barcode_expected = []
    for raw in BARCODE_CASES:
        try:
            barcode_expected.append({"input": raw, "ok": normalize_barcode(raw)})
        except InvalidBarcode as err:
            barcode_expected.append({"input": raw, "error": str(err)})

    aliases = dict(ALIASES)

    contents = f"""/**
 * GENERATED FILE -- do not edit. Regenerate with: cd backend && python export_demo_data.py
 * DEMO_EXPECTED holds the Python verdicts that `npm run check:demo` compares against.
 */

export const DEMO_INGREDIENTS = {js_array(ingredients)}

export const DEMO_ALIASES = {json.dumps(aliases, indent=2, ensure_ascii=False)}

export const DEMO_BOTTLES = {js_array(bottles)}

export const DEMO_RECIPES = {js_array(recipes)}

export const DEMO_EXPECTED = {json.dumps(expected, indent=2, ensure_ascii=False)}

export const DEMO_EXPECTED_BARCODES = {js_array(barcode_expected)}
"""

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(contents, encoding="utf-8")

    demo = expected["demo"]["status"]
    print(
        f"wrote {OUT_PATH}\n"
        f"  {len(ingredients)} categories, {len(aliases)} aliases, "
        f"{len(bottles)} bottles, {len(recipes)} recipes\n"
        f"  demo shelf: {sum(1 for s in demo.values() if s == 'makeable')} makeable, "
        f"{sum(1 for s in demo.values() if s == 'one_short')} one short, "
        f"{sum(1 for s in demo.values() if s == 'not_tonight')} not tonight"
    )


if __name__ == "__main__":
    main()
