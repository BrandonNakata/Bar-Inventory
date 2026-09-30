"""Generate the Bar-tab fixture for the portfolio's iPad panel demo."""

import json
import sqlite3
import sys
from pathlib import Path

from app.db import SCHEMA, migrate
from app.panel import panel_recipes
from app.recipe_data import seed_recipes
from app.recipe_store import seed_library
from app.shots import panel_shots
from app.taxonomy import seed
from export_demo_data import DEMO_BOTTLES


def build() -> dict:
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
            [(name, ingredient_id) for _, name, ingredient_id in DEMO_BOTTLES],
        )
    fixture = {"recipes": panel_recipes(conn), "shots": panel_shots(conn)}
    conn.close()
    return fixture


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python export_panel_fixture.py OUT.json")
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    fixture = build()
    # Compact JSON: it ships inside a web page.
    out.write_text(
        json.dumps(fixture, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    recipes, shots = fixture["recipes"], fixture["shots"]
    print(f"wrote {out}")
    print(f"  {len(recipes['recipes'])} cocktails, {recipes['ready_count']} makeable")
    print(f"  {len(shots['basic'])} basic types, {len(shots['unique'])} makeable shots")


if __name__ == "__main__":
    main()
