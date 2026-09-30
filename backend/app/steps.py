"""Recipe steps with placeholders, and the one function that fills them in."""

import re

TOKEN = re.compile(r"\{([a-z0-9-]+)(?::(name))?\}")

# Count units read better after the name: "8 mint leaves".
_COUNT_UNIT = re.compile(r"^([\d /]+)\s+(leaves|leaf|sprigs?|slices?|wedges?|cubes?)$")
# Amounts that want "of": "2 dashes of bitters", "1 tsp of sugar".
_OF_UNIT = re.compile(r"^[\d /]+\s+(dash|dashes|drop|drops|barspoons?|tsp|tbsp|pinch(es)?)$")


def phrase(name: str, amount: str | None) -> str:
    """One ingredient line as a phrase for the middle of a sentence."""
    amount = (amount or "").strip()
    if not amount or amount in ("top", "top up", "fill", "rinse"):
        return name
    if amount == "splash":
        return f"a splash of {name}"
    if amount == "pinch":
        return f"a pinch of {name}"
    if amount.endswith(" float"):
        amount = amount[: -len(" float")]
    count = _COUNT_UNIT.match(amount)
    if count:
        return f"{count.group(1)} {name.lower()} {count.group(2)}"
    if _OF_UNIT.match(amount):
        return f"{amount} of {name}"
    return f"{amount} {name}"


def render(templates: list[str], lines: list[dict], names: dict[str, str] | None = None) -> list[str]:
    """Fill every placeholder in `templates` from the recipe's `lines`."""
    by_id = {line["ingredient_id"]: line for line in lines}
    names = names or {}

    def fill(match: re.Match) -> str:
        ingredient_id, name_only = match.group(1), match.group(2)
        line = by_id.get(ingredient_id)
        if line is None:
            return names.get(ingredient_id) or ingredient_id.replace("-", " ")
        if name_only:
            return line["ingredient_name"]
        return phrase(line["ingredient_name"], line["amount"])

    return [TOKEN.sub(fill, step) for step in templates]


def referenced_ids(templates: list[str]) -> set[str]:
    """Every ingredient id a set of steps mentions."""
    return {m.group(1) for step in templates for m in TOKEN.finditer(step)}
