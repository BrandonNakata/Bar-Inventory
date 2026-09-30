"""Tests for recipe matching."""

import sqlite3
import sys

from app.db import SCHEMA
from app.recipe_data import RECIPES, seed_recipes
from app.recipes import load_recipes, random_makeable, shopping_list
from app.taxonomy import TAXONOMY, seed

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


def status_of(conn, recipe_id):
    for recipe in load_recipes(conn):
        if recipe["id"] == recipe_id:
            return recipe["status"]
    return "MISSING FROM DB"


def recipe_named(conn, recipe_id):
    return next(r for r in load_recipes(conn) if r["id"] == recipe_id)


print("\nrecipe data integrity")
known_ids = {ingredient_id for ingredient_id, _, _ in TAXONOMY}

unknown = sorted({
    ingredient_id
    for recipe in RECIPES
    for ingredient_id, _, _ in recipe["ingredients"]
    if ingredient_id not in known_ids
})
check("every recipe ingredient exists in the taxonomy", unknown, [])

slugs = [r["id"] for r in RECIPES]
check("no duplicate recipe ids", len(slugs), len(set(slugs)))
check("thirty curated recipes", len(RECIPES), 30)

empty = [r["id"] for r in RECIPES if not r["ingredients"]]
check("no recipe has zero ingredients", empty, [])

all_optional = [
    r["id"] for r in RECIPES
    if r["ingredients"] and all(opt for _, _, opt in r["ingredients"])
]
check("no recipe is entirely optional", all_optional, [])

db = fresh_db()
check("all thirty load into the database", len(load_recipes(db)), 30)


print("\nan empty shelf")
db = fresh_db()
check("nothing is makeable", [r for r in load_recipes(db) if r["status"] == "makeable"], [])
check("a Negroni is not tonight", status_of(db, "negroni"), "not_tonight")
check("'pick one for me' returns nothing", random_makeable(db), None)


print("\nthe Negroni, built up one bottle at a time")
db = fresh_db("gin")
check("gin alone: not tonight", status_of(db, "negroni"), "not_tonight")

db = fresh_db("gin", "campari")
check("gin + campari: one short", status_of(db, "negroni"), "one_short")
check("...and it names what's missing",
      [line["ingredient_name"] for line in recipe_named(db, "negroni")["missing"]],
      ["Sweet Vermouth"])

db = fresh_db("gin", "campari", "sweet-vermouth")
check("all three: makeable", status_of(db, "negroni"), "makeable")
check("...with nothing missing", recipe_named(db, "negroni")["missing"], [])


print("\nthe tree doing its job")
db = fresh_db("london-dry-gin", "campari", "sweet-vermouth")
check("a London Dry satisfies a recipe asking for 'gin'",
      status_of(db, "negroni"), "makeable")

db = fresh_db("gin", "campari", "dry-vermouth")
check("a DRY vermouth does not satisfy 'sweet vermouth'",
      status_of(db, "negroni"), "one_short")

db = fresh_db("blanco-tequila", "triple-sec")
check("a Margarita is one short without lime", status_of(db, "margarita"), "one_short")
db = fresh_db("blanco-tequila", "triple-sec", "lime-juice")
check("...and makeable with it", status_of(db, "margarita"), "makeable")

db = fresh_db("reposado-tequila", "triple-sec", "lime-juice")
check("a reposado does NOT satisfy a recipe asking for blanco",
      status_of(db, "margarita"), "one_short")


print("\noptional lines and garnishes never block a drink")
db = fresh_db("bourbon", "lemon-juice", "simple-syrup")
check("a Whiskey Sour is makeable without the optional egg white",
      status_of(db, "whiskey-sour"), "makeable")
sour = recipe_named(db, "whiskey-sour")
check("...and the egg white is still listed, marked missing",
      [(l["ingredient_name"], l["have"], l["optional"]) for l in sour["ingredients"]
       if l["ingredient_id"] == "egg-white"],
      [("Egg White", False, True)])

db = fresh_db("rye-whiskey", "peychauds-bitters")
check("a Sazerac without syrup is one short -- and absinthe isn't the reason",
      status_of(db, "sazerac"), "one_short")
check("...the missing line is the syrup, not the optional absinthe",
      [l["ingredient_name"] for l in recipe_named(db, "sazerac")["missing"]],
      ["Rich / Demerara Syrup"])

db = fresh_db("rye-whiskey", "peychauds-bitters", "rich-syrup")
check("add the syrup and it is makeable, absinthe still absent",
      status_of(db, "sazerac"), "makeable")

db = fresh_db("gin", "campari", "sweet-vermouth")
check("a garnish is never an ingredient line",
      [l for l in recipe_named(db, "negroni")["ingredients"]
       if "peel" in (l["ingredient_name"] or "").lower()],
      [])
check("...it's just text on the recipe",
      recipe_named(db, "negroni")["garnish"], "orange peel")


print("\nstaples are assumed")
db = fresh_db("cachaca", "lime-juice")
check("a Caipirinha needs sugar, which is a staple -> makeable",
      status_of(db, "caipirinha"), "makeable")


print("\nsorting")
db = fresh_db("gin", "campari", "sweet-vermouth", "tonic-water")
statuses = [r["status"] for r in load_recipes(db)]
order = {"makeable": 0, "one_short": 1, "not_tonight": 2}
check("makeable first, then one-short, then the rest",
      statuses == sorted(statuses, key=lambda s: order[s]), True)


print("\n'pick one for me'")
db = fresh_db("gin", "campari", "sweet-vermouth", "tonic-water")
picks = {random_makeable(db)["id"] for _ in range(40)}
makeable = {r["id"] for r in load_recipes(db) if r["status"] == "makeable"}
check("only ever returns something makeable", picks <= makeable, True)
check("and can return more than one thing", len(picks) > 1, True)


print("\nshopping list")
db = fresh_db("gin", "campari", "dry-vermouth", "tonic-water")
suggestions = shopping_list(db)
check("top suggestion is the sweet vermouth that unlocks the Negroni",
      suggestions[0]["ingredient_id"], "sweet-vermouth")
check("...and it says which drink",
      suggestions[0]["recipes"], ["Negroni"])
check("...and counts it once", suggestions[0]["unlocks"], 1)

# Ties sort alphabetically so the order is stable.
db = fresh_db("gin", "campari")
first = [s["ingredient_id"] for s in shopping_list(db)]
second = [s["ingredient_id"] for s in shopping_list(db)]
check("a three-way tie is ordered alphabetically", first[:3],
      ["dry-vermouth", "sweet-vermouth", "tonic-water"])
check("...and identically every time", first, second)

db = fresh_db("gin", "campari", "sweet-vermouth")
check("nothing to suggest for a recipe you can already make",
      [s for s in shopping_list(db) if "Negroni" in s["recipes"]], [])

# Two recipes one short at different levels of one branch: one specific bottle fixes both.
db = fresh_db("campari", "sweet-vermouth", "green-chartreuse", "maraschino", "lime-juice")
suggestions = shopping_list(db)
top = suggestions[0]
check("one gin purchase is credited with unlocking both the Negroni and the Last Word",
      (top["ingredient_id"], sorted(top["recipes"])),
      ("gin", ["Last Word", "Negroni"]))

db = fresh_db()
check("an empty shelf suggests nothing (no recipe is one-short)",
      shopping_list(db), [])

print()
if failures:
    print(f"{len(failures)} failed: {', '.join(failures)}")
    sys.exit(1)
print("all good")
