"""Import recipes from an external dataset."""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from app.db import connect, init_db
from app.taxonomy import resolve_ingredient, seed

# Map the field names datasets use onto ours.
FIELD_ALIASES = {
    "name":         ("name", "title", "strDrink", "drink"),
    "glass":        ("glass", "glassware", "strGlass"),
    "method":       ("method", "preparation", "technique"),
    "garnish":      ("garnish", "strGarnish"),
    "instructions": ("instructions", "directions", "strInstructions", "steps"),
    "ingredients":  ("ingredients", "recipeIngredient", "ingredient_list"),
}


def field(record: dict, key: str):
    """Pull a field by whichever name this dataset happens to use."""
    for candidate in FIELD_ALIASES[key]:
        if record.get(candidate):
            return record[candidate]
    return None


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")


def parse_ingredient(raw) -> tuple[str, str | None]:
    """Normalise one ingredient line to (text, amount)."""
    if isinstance(raw, dict):
        name = raw.get("name") or raw.get("ingredient") or raw.get("strIngredient")
        amount = raw.get("amount") or raw.get("measure") or raw.get("strMeasure")
        return (str(name or "").strip(), str(amount).strip() if amount else None)

    text = str(raw).strip()
    # Split a leading quantity off the line; if unsure, keep the whole string.
    match = re.match(
        r"^([\d/\.\s¼½¾⅓⅔]+(?:oz|ml|cl|dash(?:es)?|tsp|tbsp|barspoon|part[s]?|drop[s]?)?)\s+(.*)$",
        text,
        re.IGNORECASE,
    )
    if match:
        return (match.group(2).strip(), match.group(1).strip())
    return (text, None)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("---")[0])
    parser.add_argument("dataset", type=Path, help="JSON file to import")
    parser.add_argument(
        "--commit", action="store_true",
        help="actually write to the database (default is a dry run)",
    )
    parser.add_argument(
        "--source", default=None,
        help="value for recipe.source (default: import:<filename>)",
    )
    parser.add_argument(
        "--unmapped", type=Path, default=None,
        help="write the unresolved ingredient names to this JSON file",
    )
    args = parser.parse_args()

    if not args.dataset.exists():
        print(f"No such file: {args.dataset}")
        return 1

    source = args.source or f"import:{args.dataset.stem}"
    records = json.loads(args.dataset.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        print("Expected the file to contain a JSON array of recipes.")
        return 1

    init_db()
    conn = connect()
    seed(conn)

    ready, skipped = [], []
    unmapped_counter: Counter[str] = Counter()

    for record in records:
        name = field(record, "name")
        raw_ingredients = field(record, "ingredients") or []
        if not name or not raw_ingredients:
            skipped.append({"name": name or "(unnamed)", "why": "no name or no ingredients"})
            continue

        lines, unresolved = [], []
        for raw in raw_ingredients:
            text, amount = parse_ingredient(raw)
            if not text:
                continue
            ingredient_id = resolve_ingredient(conn, text)
            if ingredient_id is None:
                unresolved.append(text)
                unmapped_counter[text.lower()] += 1
            else:
                # Keep the source wording to debug mappings later.
                lines.append((ingredient_id, amount, 0, text))

        if unresolved:
            # All-or-nothing: a partial recipe would falsely show as makeable.
            skipped.append({"name": name, "why": f"unmapped: {', '.join(unresolved)}"})
            continue

        ready.append({
            "id": slugify(name),
            "name": name,
            "glass": field(record, "glass"),
            "method": field(record, "method"),
            "garnish": field(record, "garnish"),
            "instructions": field(record, "instructions"),
            "source_ref": str(record.get("id") or record.get("idDrink") or ""),
            "lines": lines,
        })

    # ---- report -----------------------------------------------------------
    print(f"\n{args.dataset.name}: {len(records)} records")
    print(f"  resolved cleanly : {len(ready)}")
    print(f"  skipped          : {len(skipped)}")

    if unmapped_counter:
        print(f"\nTop unmapped ingredient names ({len(unmapped_counter)} distinct):")
        for text, count in unmapped_counter.most_common(25):
            print(f"  {count:4d}  {text}")
        print(
            "\nAdd the ones worth having to ALIASES in app/taxonomy.py "
            "(or add new categories to TAXONOMY), then run this again."
        )

    if args.unmapped:
        args.unmapped.write_text(
            json.dumps(unmapped_counter.most_common(), indent=2), encoding="utf-8"
        )
        print(f"\nFull unmapped list written to {args.unmapped}")

    if not args.commit:
        print("\nDry run -- nothing written. Re-run with --commit to import.")
        conn.close()
        return 0

    # ---- write ------------------------------------------------------------
    with conn:
        for recipe in ready:
            conn.execute(
                """
                INSERT INTO recipe (id, name, glass, method, garnish,
                                    instructions, source, source_ref)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name         = excluded.name,
                    glass        = excluded.glass,
                    method       = excluded.method,
                    garnish      = excluded.garnish,
                    instructions = excluded.instructions,
                    source       = excluded.source,
                    source_ref   = excluded.source_ref
                WHERE recipe.source != 'curated'
                """,
                (
                    recipe["id"], recipe["name"], recipe["glass"], recipe["method"],
                    recipe["garnish"], recipe["instructions"], source,
                    recipe["source_ref"] or None,
                ),
            )
            # Never overwrite a curated recipe.
            still_curated = conn.execute(
                "SELECT 1 FROM recipe WHERE id = ? AND source = 'curated'",
                (recipe["id"],),
            ).fetchone()
            if still_curated:
                continue

            conn.execute(
                "DELETE FROM recipe_ingredient WHERE recipe_id = ?", (recipe["id"],)
            )
            conn.executemany(
                """
                INSERT INTO recipe_ingredient
                       (recipe_id, position, ingredient_id, amount, optional, note)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (recipe["id"], position, ingredient_id, amount, optional, note)
                    for position, (ingredient_id, amount, optional, note)
                    in enumerate(recipe["lines"])
                ],
            )

    total = conn.execute("SELECT COUNT(*) c FROM recipe").fetchone()["c"]
    conn.close()
    print(f"\nImported. {total} recipes in the database.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
