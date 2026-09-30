"""Tests for the iPad panel's endpoint shape."""

import sqlite3
import sys

from app.db import SCHEMA
from app.panel import panel_recipes
from app.recipe_data import seed_recipes
from app.recipes import load_recipes
from app.taxonomy import seed

failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok    {label}")
    else:
        print(f"  FAIL  {label}\n          got:  {got}\n          want: {want}")
        failures.append(label)


def fresh_db(*bottles):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    seed(conn)
    seed_recipes(conn)
    with conn:
        for ingredient_id in bottles:
            conn.execute(
                "INSERT INTO bottle (product_name, ingredient_id) VALUES (?, ?)",
                (f"A bottle of {ingredient_id}", ingredient_id),
            )
    return conn


def by_id(payload, recipe_id):
    return next(r for r in payload["recipes"] if r["id"] == recipe_id)


print("\nthe shape the panel reads")

conn = fresh_db("london-dry-gin", "campari", "sweet-vermouth", "bourbon", "rich-syrup")
payload = panel_recipes(conn)

check("top-level keys", sorted(payload), ["inventory_count", "ready_count", "recipes"])
check("inventory_count counts bottles", payload["inventory_count"], 5)

negroni = by_id(payload, "negroni")
check(
    "recipe keys are exactly what renderRecipe() uses",
    sorted(negroni),
    ["base", "glass", "id", "ingredients", "instructions", "method", "missing", "name", "steps"],
)
check(
    "each ingredient is {name, amount, have}",
    negroni["ingredients"][0],
    {"name": "Gin", "amount": "1 oz", "have": True},
)
check("have is a real boolean (the panel tests === false)",
      all(type(i["have"]) is bool for r in payload["recipes"] for i in r["ingredients"]),
      True)
check("missing is a list of names", negroni["missing"], [])

check("steps is a list of strings",
      all(type(r["steps"]) is list and all(type(x) is str for x in r["steps"])
          for r in payload["recipes"]),
      True)
check("every curated recipe has at least three steps",
      [r["id"] for r in payload["recipes"] if len(r["steps"]) < 3], [])
check("the Negroni's steps start with what goes in the glass, amount included",
      negroni["steps"][0], "Add 1 oz Gin to a mixing glass.")
check("steps arrive rendered: no placeholder ever reaches the panel",
      [s for r in payload["recipes"] for s in r["steps"] if "{" in s], [])
check("base is the chip the drink sits under", (negroni["base"], by_id(payload, "margarita")["base"]),
      ("gin", "tequila"))
check("shots are not in the cocktail list",
      [r["id"] for r in payload["recipes"] if r["id"] in ("b-52", "green-tea-shot")], [])

boulevardier = by_id(payload, "boulevardier")
check("a makeable drink has nothing missing", boulevardier["missing"], [])

old_fashioned = by_id(payload, "old-fashioned")
check("a drink missing one thing names it", old_fashioned["missing"], ["Aromatic Bitters"])


print("\nthe panel and the React app agree")

# The panel's READY and 1 SHORT must match the status recipes.py computes.
for shelf in [(), ("bourbon",), ("london-dry-gin", "campari", "sweet-vermouth"),
              ("white-rum", "lime-juice", "simple-syrup", "mint", "soda-water")]:
    conn = fresh_db(*shelf)
    status = {r["id"]: r["status"] for r in load_recipes(conn)}
    payload = panel_recipes(conn)
    bucket = {0: "makeable", 1: "one_short"}
    agree = all(
        bucket.get(len(r["missing"]), "not_tonight") == status[r["id"]]
        for r in payload["recipes"]
    )
    check(f"shelf {shelf or '(empty)'}: same verdict for every recipe", agree, True)
    check(
        "   ...and ready_count matches",
        payload["ready_count"],
        sum(1 for s in status.values() if s == "makeable"),
    )


print("\nthings the panel can't do for itself")

conn = fresh_db("bourbon", "lemon-juice", "simple-syrup")
sour = by_id(panel_recipes(conn), "whiskey-sour")
egg = next(i for i in sour["ingredients"] if i["name"].startswith("Egg White"))
check("an optional line says so in its name", egg["name"], "Egg White (optional)")
check("...is not counted as missing", sour["missing"], [])

manhattan = by_id(panel_recipes(conn), "manhattan")
check(
    "the garnish is folded into the instructions",
    manhattan["instructions"].endswith("Garnish: brandied cherry."),
    True,
)
negroni = by_id(panel_recipes(conn), "negroni")
check(
    "...but not when the method already mentions it",
    negroni["instructions"].count("orange peel"),
    1,
)
paper_plane = by_id(panel_recipes(conn), "paper-plane")
check(
    "a recipe with no garnish keeps its instructions untouched",
    "Garnish" in paper_plane["instructions"],
    False,
)

print()
if failures:
    print(f"{len(failures)} check(s) failed")
    sys.exit(1)
print("all good")
