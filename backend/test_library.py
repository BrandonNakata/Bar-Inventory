"""Tests for the recipe library, the step templates, phone edits and the shot reel."""

import json
import sqlite3
import sys

from app.db import SCHEMA, migrate
from app.ranking import name_key, rank_for
from app.recipe_data import RECIPES, seed_recipes
from app.recipe_store import (
    LIBRARY_PATH, RecipeError, create_recipe, seed_library, set_hidden, update_recipe,
)
from app.recipes import get_recipe, load_recipes
from app.shot_data import SHOTS
from app.shots import panel_shots
from app.steps import TOKEN, phrase, referenced_ids, render
from app.taxonomy import TAXONOMY, satisfiable_ids, seed, suggest_ingredient

failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok    {label}")
    else:
        print(f"  FAIL  {label}\n          got:  {got}\n          want: {want}")
        failures.append(label)


def fresh_db(*bottles, library=False):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    migrate(conn)
    seed(conn)
    seed_recipes(conn)
    if library:
        seed_library(conn)
    with conn:
        for ingredient_id in bottles:
            conn.execute(
                "INSERT INTO bottle (product_name, ingredient_id) VALUES (?, ?)",
                (f"A bottle of {ingredient_id}", ingredient_id),
            )
    return conn


LIBRARY = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
KNOWN = {row[0] for row in TAXONOMY}


print("\nstep placeholders render into plain English")

check("amount + name", phrase("Gin", "2 oz"), "2 oz Gin")
check("dashes take 'of'", phrase("Aromatic Bitters", "2 dashes"), "2 dashes of Aromatic Bitters")
check("counts put the unit after the name", phrase("Mint", "8 leaves"), "8 mint leaves")
check("'top' is just the name", phrase("Soda Water", "top"), "Soda Water")
check("a splash", phrase("Soda Water", "splash"), "a splash of Soda Water")
check("a float drops the word 'float'", phrase("Islay Scotch", "1/4 oz float"), "1/4 oz Islay Scotch")
check("no amount is just the name", phrase("Grand Marnier", None), "Grand Marnier")

lines = [{"ingredient_id": "gin", "ingredient_name": "Gin", "amount": "2 oz"},
         {"ingredient_id": "soda-water", "ingredient_name": "Soda Water", "amount": "top"}]
check("{id} and {id:name} both fill in",
      render(["Add {gin} to a shaker.", "Top with {soda-water:name}."], lines),
      ["Add 2 oz Gin to a shaker.", "Top with Soda Water."])
lines[0]["amount"] = "1 1/2 oz"
check("change the amount once, the step follows",
      render(["Add {gin} to a shaker."], lines), ["Add 1 1/2 oz Gin to a shaker."])
check("a dangling placeholder falls back to the plain name, never braces",
      render(["Add {campari}."], lines, {"campari": "Campari"}), ["Add Campari."])


print("\nevery recipe's steps and ingredients line up")


def audit(recipes, label):
    unknown, dangling, unused = [], [], []
    for r in recipes:
        ids = [line[0] for line in r["ingredients"]]
        unknown += [f"{r['id']}:{i}" for i in ids if i not in KNOWN]
        dangling += [f"{r['id']}:{i}" for i in referenced_ids(r["steps"]) - set(ids)]
        unused += [f"{r['id']}:{i}" for i in set(ids) - referenced_ids(r["steps"])]
    check(f"{label}: every ingredient exists in the taxonomy", unknown, [])
    check(f"{label}: every placeholder is one of the recipe's own lines", dangling, [])
    check(f"{label}: every ingredient line is used by some step", unused, [])


audit(RECIPES, "curated cocktails")
audit(SHOTS, "curated shots")
audit(LIBRARY, "library")

check("no step in the library is written in plain text with an amount baked in",
      [s for r in LIBRARY for s in r["steps"] if " oz " in TOKEN.sub("", s)][:3], [])


print("\nthe library as a whole")

ids = [r["id"] for r in LIBRARY]
check("no duplicate ids", len(ids), len(set(ids)))
curated_ids = {r["id"] for r in RECIPES} | {s["id"] for s in SHOTS}
check("no library id collides with a curated one", sorted(set(ids) & curated_ids), [])
curated_keys = {name_key(r["name"]) for r in RECIPES} | {name_key(s["name"]) for s in SHOTS}
check("no library drink duplicates a curated one by name",
      sorted({r["name"] for r in LIBRARY if name_key(r["name"]) in curated_keys}), [])
check("kinds are only cocktail or shot", {r["kind"] for r in LIBRARY}, {"cocktail", "shot"})
check("methods come from a small vocabulary",
      {r["method"] for r in LIBRARY} <= {"shaken", "stirred", "built", "blended", "layered", "bomb"},
      True)
check("every recipe has at least two steps", [r["id"] for r in LIBRARY if len(r["steps"]) < 2], [])
check("at least 800 cocktails made it through", sum(r["kind"] == "cocktail" for r in LIBRARY) >= 800, True)
check("the list is sorted most-common first", ids[:3] != sorted(ids)[:3], True)
check("a Margarita outranks a Last Word", rank_for("Margarita") < rank_for("Last Word"), True)
check("an unranked drink in three datasets beats one in a single dataset",
      rank_for("Nobody Knows This", 3) < rank_for("Nobody Knows This", 1), True)


print("\nthe ingredients you couldn't add before")

db = fresh_db()
for label, want in [
    ("Captain Morgan Original Spiced Rum", "spiced-rum"),
    ("Cruzan Banana Flavored Rum", "banana-rum"),
    ("DeKuyper Peachtree Schnapps", "peach-schnapps"),
    ("Jinro Chamisul Fresh Soju", "soju"),
    ("Fireball Cinnamon Whisky", "cinnamon-whiskey"),
    ("Espolòn Tequila Blanco", "blanco-tequila"),
]:
    check(f"'{label}' is guessed as {want}", suggest_ingredient(db, label), want)

db = fresh_db("spiced-rum")
check("spiced rum counts as rum", "rum" in satisfiable_ids(db), True)
db = fresh_db("banana-rum")
check("banana rum does not", "rum" in satisfiable_ids(db), False)
db = fresh_db("banana-rum", "white-rum", "lime-juice", "simple-syrup")
check("a banana rum does NOT count as the rum in a Daiquiri... white rum does",
      next(r for r in load_recipes(db) if r["id"] == "daiquiri")["status"], "makeable")
db = fresh_db("banana-rum", "lime-juice", "simple-syrup")
check("...and with only banana rum, the Daiquiri is one short",
      next(r for r in load_recipes(db) if r["id"] == "daiquiri")["status"], "one_short")


print("\nseeding the library")

db = fresh_db(library=True)
total = db.execute("SELECT COUNT(*) c FROM recipe WHERE source = 'library'").fetchone()["c"]
check("every library recipe lands in the database", total, len(LIBRARY))
check("a second seed with an unchanged file writes nothing", seed_library(db), 0)

target = LIBRARY[0]["id"]
update_recipe(db, target, {
    "name": "My Better Version", "kind": "cocktail",
    "ingredients": [{"ingredient_id": "gin", "amount": "2 oz"}],
    "steps": ["Add {gin} to a glass."],
})
set_hidden(db, LIBRARY[1]["id"], True)
with db:
    db.execute("DELETE FROM meta")          # pretend the library file changed
seed_library(db)
check("a recipe you edited survives a re-seed",
      get_recipe(db, target)["name"], "My Better Version")
check("...and is marked as edited", get_recipe(db, target)["edited"], True)
check("a recipe you hid stays hidden through a re-seed",
      get_recipe(db, LIBRARY[1]["id"])["hidden"], True)
check("hidden recipes are left out of the normal list",
      LIBRARY[1]["id"] in {r["id"] for r in load_recipes(db, kind=None)}, False)
check("...and are the whole of the Hidden list",
      [r["id"] for r in load_recipes(db, kind=None, hidden="only")], [LIBRARY[1]["id"]])


print("\nediting from the phone")

db = fresh_db("gin", "lime-juice", "simple-syrup")
new_id = create_recipe(db, {
    "name": "House Gimlet", "kind": "cocktail", "glass": "coupe", "method": "shaken",
    "ingredients": [
        {"ingredient_id": "gin", "amount": "2 oz"},
        {"ingredient_id": "lime-juice", "amount": "3/4 oz"},
        {"ingredient_id": "simple-syrup", "amount": "1/2 oz"},
    ],
    "steps": ["Add {gin} to a shaker.", "Add {lime-juice}.", "Add {simple-syrup}.",
              "Shake with ice and strain."],
})
made = get_recipe(db, new_id)
check("a new recipe gets a slug id", new_id, "house-gimlet")
check("...is marked as yours", made["source"], "user")
check("...renders its steps", made["steps"][0], "Add 2 oz Gin to a shaker.")
check("...keeps its template for the editor", made["steps_template"][0], "Add {gin} to a shaker.")
check("...and is makeable from the shelf", made["status"], "makeable")
check("a second one with the same name gets its own id",
      create_recipe(db, {"name": "House Gimlet",
                         "ingredients": [{"ingredient_id": "gin", "amount": "2 oz"}]}),
      "house-gimlet-2")

update_recipe(db, "negroni", {
    "name": "Negroni", "kind": "cocktail", "glass": "rocks", "method": "stirred",
    "ingredients": [
        {"ingredient_id": "gin", "amount": "1 1/2 oz"},
        {"ingredient_id": "campari", "amount": "1 oz"},
        {"ingredient_id": "sweet-vermouth", "amount": "1 oz"},
    ],
    "steps": ["Add {gin} to a mixing glass.", "Add {campari}.", "Add {sweet-vermouth}."],
})
check("editing an amount changes the step that mentions it",
      get_recipe(db, "negroni")["steps"][0], "Add 1 1/2 oz Gin to a mixing glass.")
seed_recipes(db)
check("...and a restart doesn't put the old amount back",
      get_recipe(db, "negroni")["steps"][0], "Add 1 1/2 oz Gin to a mixing glass.")


def refused(data):
    try:
        create_recipe(db, data)
    except RecipeError as err:
        return str(err)
    return None


check("a recipe needs a name", refused({"name": " ", "ingredients": [
    {"ingredient_id": "gin"}]}) is not None, True)
check("a recipe needs an ingredient", refused({"name": "Air", "ingredients": []}) is not None, True)
check("an unknown ingredient is refused",
      "unicorn" in (refused({"name": "X", "ingredients": [{"ingredient_id": "unicorn"}]}) or ""), True)
check("a step naming an ingredient the recipe lacks is refused",
      "campari" in (refused({"name": "X", "ingredients": [{"ingredient_id": "gin"}],
                              "steps": ["Add {campari}."]}) or ""), True)
check("hiding something that doesn't exist says so", set_hidden(db, "nope", True), False)


print("\nthe shots reel")

db = fresh_db()
shots = panel_shots(db)
check("an empty shelf has nothing to roll", (shots["basic"], shots["unique"]), ([], []))
check("...and suggests what to buy instead", len(shots["suggestions"]) > 0, True)

db = fresh_db("blanco-tequila", "reposado-tequila", "soju", "irish-cream",
              "coffee-liqueur", "grand-marnier", "lime-juice")
shots = panel_shots(db)
names = [b["name"] for b in shots["basic"]]
check("two tequilas are ONE Tequila entry", names.count("Tequila"), 1)
check("...listing both bottles",
      next(b for b in shots["basic"] if b["name"] == "Tequila")["bottles"],
      ["A bottle of blanco-tequila", "A bottle of reposado-tequila"])
check("soju and shootable liqueurs are on the Basic reel",
      {"Soju", "Irish Cream", "Coffee Liqueur"} <= set(names), True)
check("lime juice is not something you shoot", "Lime Juice" in names, False)
check("Grand Marnier isn't a Basic entry", "Grand Marnier" in names, False)
check("the B-52 is on the Unique reel",
      "b-52" in [s["id"] for s in shots["unique"]], True)
check("unique shots come pre-rendered for the panel",
      [s for u in shots["unique"] for s in u["steps"] if "{" in s], [])

print()
if failures:
    print(f"{len(failures)} check(s) failed")
    sys.exit(1)
print("all good")
