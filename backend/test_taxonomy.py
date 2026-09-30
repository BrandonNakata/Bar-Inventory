"""Tests for the ingredient tree."""

import sqlite3
import sys

from app.db import SCHEMA
from app.taxonomy import (
    ancestor_ids,
    bottles_satisfying,
    descendant_ids,
    resolve_ingredient,
    satisfiable_ids,
    seed,
    suggest_ingredient,
)

failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok    {label}")
    else:
        print(f"  FAIL  {label}\n          got:  {got}\n          want: {want}")
        failures.append(label)


def fresh_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    seed(conn)
    return conn


def add(conn, name, ingredient_id):
    with conn:
        conn.execute(
            "INSERT INTO bottle (product_name, ingredient_id) VALUES (?, ?)",
            (name, ingredient_id),
        )


print("\ndescendant_ids -- a requirement is satisfied by anything below it")
db = fresh_db()
check("vermouth covers all three styles",
      sorted(descendant_ids(db, "vermouth")),
      ["blanc-vermouth", "dry-vermouth", "sweet-vermouth", "vermouth"])
check("a leaf covers only itself",
      descendant_ids(db, "sweet-vermouth"), ["sweet-vermouth"])
check("gin reaches its whole subtree",
      sorted(descendant_ids(db, "gin")),
      ["genever", "gin", "london-dry-gin", "old-tom-gin"])
check("unknown id is empty, not an error",
      descendant_ids(db, "unobtainium"), [])

print("\nancestor_ids -- the chain upward, nearest first")
check("sweet vermouth's lineage",
      ancestor_ids(db, "sweet-vermouth"),
      ["sweet-vermouth", "vermouth", "fortified-wine"])
check("islay scotch is three deep",
      ancestor_ids(db, "islay-scotch"),
      ["islay-scotch", "scotch", "whiskey", "spirit"])
check("a root has only itself", ancestor_ids(db, "spirit"), ["spirit"])

print("\nbottles_satisfying -- the asymmetry that makes this worth doing")
db = fresh_db()
add(db, "Carpano Antica Formula", "sweet-vermouth")
add(db, "Dolin Dry", "dry-vermouth")
add(db, "Tanqueray", "london-dry-gin")

check("a recipe asking for 'vermouth' gets both bottles",
      sorted(b["product_name"] for b in bottles_satisfying(db, "vermouth")),
      ["Carpano Antica Formula", "Dolin Dry"])
check("asking for 'sweet vermouth' excludes the dry one",
      [b["product_name"] for b in bottles_satisfying(db, "sweet-vermouth")],
      ["Carpano Antica Formula"])
check("asking for 'gin' finds the London dry",
      [b["product_name"] for b in bottles_satisfying(db, "gin")],
      ["Tanqueray"])
check("asking for 'old tom gin' does NOT accept a London dry",
      bottles_satisfying(db, "old-tom-gin"), [])
check("nothing on the shelf satisfies rum",
      bottles_satisfying(db, "rum"), [])
check("the join brings the category name along",
      [b["ingredient_name"] for b in bottles_satisfying(db, "sweet-vermouth")],
      ["Sweet Vermouth"])

print("\nsatisfiable_ids -- the same tree, walked upward")
db = fresh_db()
add(db, "Tanqueray", "london-dry-gin")
ids = satisfiable_ids(db)
check("one bottle satisfies its own category", "london-dry-gin" in ids, True)
check("...and its parent", "gin" in ids, True)
check("...and its grandparent", "spirit" in ids, True)
check("but not a sibling", "old-tom-gin" in ids, False)
check("and not an unrelated branch", "rum" in ids, False)
check("staples are always satisfiable", {"ice", "sugar"} <= ids, True)
check("a non-staple you don't own is not", "mint" in ids, False)

print("\nsuggest_ingredient -- the guess the human confirms")
db = fresh_db()
check("brand name in the middle of a long label",
      suggest_ingredient(db, "Carpano Antica Formula Vermouth di Torino"),
      "sweet-vermouth")
check("case doesn't matter", suggest_ingredient(db, "TANQUERAY LONDON DRY"),
      "london-dry-gin")
check("longest alias wins over a shorter overlap",
      suggest_ingredient(db, "Bulleit Rye Whiskey"), "rye-whiskey")
check("green chartreuse beats plain chartreuse",
      suggest_ingredient(db, "Green Chartreuse 750ml"), "green-chartreuse")
check("a miss returns None rather than guessing",
      suggest_ingredient(db, "Ancho Reyes Verde"), None)

print("\nresolve_ingredient -- for importing recipes")
check("an id passes straight through",
      resolve_ingredient(db, "sweet-vermouth"), "sweet-vermouth")
check("a display name matches", resolve_ingredient(db, "Sweet Vermouth"),
      "sweet-vermouth")
check("a spaced name slugifies", resolve_ingredient(db, "lime juice"),
      "lime-juice")
check("otherwise it falls back to aliases",
      resolve_ingredient(db, "rosso"), "sweet-vermouth")
check("and gives up honestly", resolve_ingredient(db, "unicorn tears"), None)
check("empty input is None", resolve_ingredient(db, "   "), None)

print("\nseeding is idempotent, and repairs drift")
db = fresh_db()
before = db.execute("SELECT COUNT(*) c FROM ingredient").fetchone()["c"]
seed(db)
seed(db)
after = db.execute("SELECT COUNT(*) c FROM ingredient").fetchone()["c"]
check("re-seeding doesn't duplicate rows", after, before)

with db:
    db.execute("UPDATE ingredient SET name = 'WRONG' WHERE id = 'gin'")
seed(db)
check("re-seeding repairs an edited row",
      db.execute("SELECT name FROM ingredient WHERE id='gin'").fetchone()["name"],
      "Gin")

print("\ntaxonomy integrity")
db = fresh_db()
orphans = db.execute(
    """SELECT i.id FROM ingredient i
       WHERE i.parent_id IS NOT NULL
         AND NOT EXISTS (SELECT 1 FROM ingredient p WHERE p.id = i.parent_id)"""
).fetchall()
check("every parent_id points at a real node", [r["id"] for r in orphans], [])

bad_alias = db.execute(
    """SELECT a.alias FROM ingredient_alias a
       WHERE NOT EXISTS (SELECT 1 FROM ingredient i WHERE i.id = a.ingredient_id)"""
).fetchall()
check("every alias points at a real node", [r["alias"] for r in bad_alias], [])

cycles = []
for row in db.execute("SELECT id FROM ingredient"):
    chain = ancestor_ids(db, row["id"])
    if len(chain) != len(set(chain)):
        cycles.append(row["id"])
check("no cycles -- the recursive query would never terminate", cycles, [])

print()
if failures:
    print(f"{len(failures)} failed: {', '.join(failures)}")
    sys.exit(1)
print("all good")
