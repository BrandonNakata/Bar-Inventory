"""Turn three public cocktail datasets into recipes this app can use."""

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

from app.ranking import rank_for, name_key
from app.recipe_data import RECIPES as CURATED
from app.shot_data import SHOTS as CURATED_SHOTS
from app.taxonomy import TAXONOMY
from library.extras import EXTRAS
from library.ingredient_map import RULES
from library.overrides import DROP, OVERRIDES

HERE = Path(__file__).resolve().parent
DATA = HERE.parent.parent / "Data"
OUT = HERE.parent / "app" / "recipe_library.json"

NODE = {row[0]: row for row in TAXONOMY}
PARENT = {row[0]: row[2] for row in TAXONOMY}
COMPILED = [(re.compile(pattern), action) for pattern, action in RULES]

# Where each source ranks when two of them have the same drink.
SOURCE_PRIORITY = {"iba": 0, "extra": 0, "cocktaildb": 1, "boston": 2}


# Text helpers

def fold(text: str) -> str:
    """Lowercase, strip accents, squash whitespace."""
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", plain).strip()


BRAND_PREFIX = re.compile(
    r"^(old mr\.? boston|mr\.? boston|old thompson|desmond & duff|old kentucky tavern)\s+"
)


def clean(text: str) -> str:
    """Ingredient text as RULES sees it."""
    return BRAND_PREFIX.sub("", fold(text)).strip(" .")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", fold(text)).strip("-")


def is_under(node: str, ancestor: str) -> bool:
    """True if `node` sits at or below `ancestor` in the taxonomy."""
    while node:
        if node == ancestor:
            return True
        node = PARENT.get(node)
    return False


# Loading: each loader yields the same record shape.

def read_csv(name: str) -> list[dict]:
    with open(DATA / name, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_iba() -> list[dict]:
    cocktails = read_csv("iba-cocktails-web.csv")
    by_name = defaultdict(list)
    for row in read_csv("iba-cocktails-ingredients-web.csv"):
        by_name[row["name"]].append(row)
    out = []
    for c in cocktails:
        lines = []
        for row in by_name[c["name"]]:
            qty, unit = row["quantity"], row["unit"]
            measure = " ".join(x for x in (qty, unit) if x and x != "NA")
            lines.append((row["ingredient"], measure))
        out.append({
            "name": c["name"],
            "source": "iba",
            "ref": c["category"],
            "category": c["category"],
            "glass": None,
            "method_text": c["method"],
            "garnish_text": None if c["garnish"] == "NA" else c["garnish"],
            "lines": lines,
        })
    return out


# TheCocktailDB categories that aren't what this app is for.
TT_SKIP = {
    "Punch / Party Drink", "Beer", "Homemade Liqueur", "Soft Drink / Soda",
    "Milk / Float / Shake", "Cocoa", "Other/Unknown",
}


def load_cocktaildb() -> list[dict]:
    by_id = defaultdict(list)
    for row in read_csv("cocktails.csv"):
        by_id[row["id_drink"]].append(row)
    out = []
    for rows in by_id.values():
        first = rows[0]
        if first["alcoholic"] != "Alcoholic" or first["category"] in TT_SKIP:
            continue
        rows.sort(key=lambda r: int(r["ingredient_number"]))
        out.append({
            "name": first["drink"],
            "source": "cocktaildb",
            "ref": first["id_drink"],
            "category": first["category"],
            "glass": first["glass"],
            "method_text": None,
            "garnish_text": None,
            "lines": [(r["ingredient"], r["measure"]) for r in rows],
        })
    return out


BOSTON_SPIRIT = {
    "Vodka": "vodka", "Tequila": "tequila", "Gin": "gin", "Brandy": "brandy",
    "Whiskies": "whiskey", "Rum - Daiquiris": "rum", "Rum": "rum",
}


def load_boston() -> list[dict]:
    by_row = defaultdict(list)
    for row in read_csv("boston_cocktails.csv"):
        by_row[row["row_id"]].append(row)
    out = []
    for rows in by_row.values():
        first = rows[0]
        if first["category"] == "Non-alcoholic Drinks":
            continue
        rows.sort(key=lambda r: int(r["ingredient_number"]))
        numbers = [int(r["ingredient_number"]) for r in rows]
        out.append({
            "name": first["name"],
            "source": "boston",
            "ref": first["row_id"],
            "category": first["category"],
            "glass": None,
            "method_text": None,
            "garnish_text": None,
            "lines": [(r["ingredient"], r["measure"]) for r in rows],
            # A numbering gap means rows bled between recipes.
            "suspect": numbers != list(range(1, len(numbers) + 1)),
        })
    return out


# Amounts

UNICODE_FRACTIONS = {"½": " 1/2", "¼": " 1/4", "¾": " 3/4", "⅓": " 1/3", "⅔": " 2/3"}
NUM = r"(\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)"


def to_number(text: str) -> Fraction:
    """'1 1/2' -> 3/2, '0.75' -> 3/4, '1/3' -> 1/3."""
    total = Fraction(0)
    for part in text.split():
        total += Fraction(part)
    return total


def fmt_oz(value: Fraction) -> str:
    """3/2 -> '1 1/2 oz'."""
    quarters = max(1, round(value * 4))
    whole, rest = divmod(quarters, 4)
    frac = {0: "", 1: "1/4", 2: "1/2", 3: "3/4"}[rest]
    text = " ".join(x for x in (str(whole) if whole else "", frac) if x)
    return f"{text} oz"


def fmt_count(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    whole, rest = divmod(value.numerator, value.denominator)
    frac = f"{rest}/{value.denominator}"
    return f"{whole} {frac}" if whole else frac


def plural(n: Fraction, word: str) -> str:
    return f"{fmt_count(n)} {word}{'' if n <= 1 else ('es' if word.endswith('sh') else 's')}"


JUICE_PER_FRUIT = {"lemon-juice": Fraction(3, 2), "lime-juice": Fraction(1),
                   "orange-juice": Fraction(3), "grapefruit-juice": Fraction(4)}

# Mr. Boston flattened every unit to oz; these were really dashes or teaspoons.
BOSTON_DASH = ("bitters", "hot-sauce", "worcestershire-sauce")
BOSTON_TSP = ("sugar", "grenadine")
BOSTON_COUNT = ("whole-egg",)


class Batch(Exception):
    """A punch-bowl quantity."""


def parse_amount(measure: str, ingredient_id: str, source: str, is_shot: bool):
    """A dataset measure -> (amount string or None, oz value or None)."""
    raw = measure or ""
    for glyph, rep in UNICODE_FRACTIONS.items():
        raw = raw.replace(glyph, rep)
    m = fold(raw)
    if not m or m in ("na",):
        return None, None

    if source == "boston":
        oz = re.fullmatch(NUM + r"\s*oz", m)
        if oz:
            n = to_number(oz.group(1))
            if any(is_under(ingredient_id, b) for b in BOSTON_DASH):
                return plural(n, "dash"), None
            if ingredient_id == "sugar":
                return f"{fmt_count(n)} tsp", None
            if ingredient_id in BOSTON_TSP and n >= 1:
                return f"{fmt_count(n)} tsp", n / 6
            if ingredient_id in BOSTON_COUNT:
                return "1", None
            if ingredient_id == "egg-white":
                return ("1" if n >= 1 else fmt_oz(n)), None

    # Ranges: "2-3 oz" -> the first number.
    m = re.sub(r"(\d)\s*-\s*\d+(?:/\d+)?", r"\1", m)

    if re.search(r"\b(cups?|pints?|qt|quarts?|gal|gallons?|bottles?|fifth|liters?|l|lb|cans?)\b", m):
        match = re.match(NUM, m)
        n = to_number(match.group(1)) if match else Fraction(1)
        unit_oz = 8 if "cup" in m else 16
        if n * unit_oz > 8:
            raise Batch(measure)
        return fmt_oz(n * unit_oz), n * unit_oz

    if m.startswith("juice of"):
        match = re.search(NUM, m)
        n = to_number(match.group(1)) if match else Fraction(1)
        if "wedge" in m:
            return "1/4 oz", Fraction(1, 4)
        per = JUICE_PER_FRUIT.get(ingredient_id, Fraction(1))
        value = n * per
        return fmt_oz(value), value

    if m in ("for glass",):
        return None, None
    if re.search(r"\b(top|fill|full glass|add)\b", m) and not re.search(r"\d", m):
        return "top", None
    if re.fullmatch(r"(a )?splash|dash|add splash|\d+ splash(es)?", m):
        return "splash", Fraction(1, 4)
    if re.fullmatch(r"(to taste|pinch|\d+ pinch(es)?)", m):
        return "pinch", None

    match = re.match(NUM + r"\s*(.*)$", m)
    if not match:
        return None, None
    n = to_number(match.group(1))
    unit = match.group(2).strip()

    if re.match(r"(oz|ounces?)\b", unit):
        return fmt_oz(n), n
    if re.match(r"cl\b", unit):
        return fmt_oz(n * Fraction(338, 1000)), n * Fraction(338, 1000)
    if re.match(r"ml\b", unit):
        oz = n / Fraction(2957, 100)
        if oz < Fraction(1, 4) and ingredient_id not in ("water",):
            tsp = max(1, round(n / 5))
            return f"{tsp} tsp", oz
        return fmt_oz(oz), oz
    if re.match(r"(shots?|jiggers?)\b", unit):
        return fmt_oz(n * Fraction(3, 2)), n * Fraction(3, 2)
    if re.match(r"(tblsp|tbsp|tablespoons?)\b", unit):
        if ingredient_id == "sugar":
            return f"{fmt_count(n)} tbsp", None
        return fmt_oz(n / 2), n / 2
    if re.match(r"(tsp|teaspoons?)\b", unit):
        return f"{fmt_count(n)} tsp", n / 6
    if re.match(r"(bar ?spoons?)\b", unit):
        return f"{fmt_count(n)} barspoon", n / 8
    if re.match(r"dash(es)?\b", unit):
        return plural(n, "dash"), None
    if re.match(r"drops?\b", unit):
        return plural(n, "drop"), None
    if re.match(r"(top up|fill up)\b", unit):
        return "top", None
    if re.match(r"(splash(es)?)\b", unit):
        return "splash", Fraction(1, 4)
    if re.match(r"(parts?)\b", unit):
        return ("PARTS", n), None
    if re.match(r"(cubes?|lumps?)\b", unit):
        return f"{fmt_count(n)} cube", None
    if re.match(r"(leaves|leaf|sprigs?)\b", unit) or ingredient_id == "mint":
        if ingredient_id != "mint":
            return fmt_count(n), None
        if "sprig" in unit or n < 3:
            return plural(n, "sprig"), None
        return f"{fmt_count(n)} leaves", None
    if re.match(r"(pieces?|whole|large|medium)?$", unit):
        # A bare number: a count for fruit and eggs, a share of the glass for shots.
        if ingredient_id == "sugar":
            return f"{fmt_count(n)} cube", None
        if ingredient_id in ("whole-egg", "egg-white", "strawberry", "banana"):
            return fmt_count(n), None
        if ingredient_id in JUICE_PER_FRUIT:
            value = n * JUICE_PER_FRUIT[ingredient_id]
            return fmt_oz(value), value
        return ("PARTS", n), None
    return fmt_oz(n) if unit.startswith("oz") else fmt_count(n), None


def resolve_parts(lines: list[dict], is_shot: bool) -> None:
    """"2 parts vodka, 1 part triple sec" -> real ounces, in place."""
    boozy = [ln for ln in lines if has([ln], "spirit", "liqueur", "fortified-wine")]
    if boozy and all(ln["amount"] is None for ln in boozy) and (
        is_shot or all(ln["amount"] is None for ln in lines)
    ):
        # No measures: pour equal parts.
        for ln in boozy:
            ln["amount"] = ("PARTS", Fraction(1))
    parts = [ln for ln in lines if isinstance(ln["amount"], tuple)]
    if not parts:
        return
    shares = [ln["amount"][1] for ln in parts]
    if is_shot:
        scale = Fraction(3, 2) / (sum(shares) or 1)
    else:
        scale = min(Fraction(1), Fraction(2) / (max(shares) or 1))
    for ln in parts:
        value = ln["amount"][1] * scale
        ln["amount"], ln["oz"] = fmt_oz(value), value


# Mapping lines

GARNISH_WORDS = re.compile(
    r"wedge|wheel|twist|peel|zest|spiral|slice|cherry|cherries|olive|sprig|leaf|"
    r"salt|sugar|nutmeg|strawberr|raspberr|cucumber|mint|basil|pineapple"
)


def classify(text: str) -> str | None:
    """RULES lookup."""
    for pattern, action in COMPILED:
        if pattern.search(text):
            return action
    return None


def split_composite(text: str, measure: str) -> list[tuple[str, str, bool]]:
    """Split Mr. Boston lines that pack several items into one."""
    t = clean(text)
    t = t.replace("pineapple juie", "pineapple juice")
    if fold(measure) == "for glass":
        return [(t, "", True)]
    if t.startswith("each "):
        items = re.split(r",\s*(?:and\s+)?|\s+and\s+", t[5:])
        return [(item.strip(), measure, False) for item in items if item.strip()]
    if "," not in t:
        return [(t, measure, False)]
    head, *rest = [p.strip() for p in t.split(",")]
    out = [(head, measure, False)]
    for part in rest:
        if re.fullmatch(NUM + r"\s*oz", part):
            out[0] = (head, part, False)       # "simple syrup, 3/4 oz"
        elif GARNISH_WORDS.search(part):
            out.append((part, "", True))
        else:
            out.append((part, measure, False))
    return out


def map_lines(record: dict):
    """Every raw line -> ingredient lines + garnish words, or a reason to drop."""
    lines, garnishes = [], []
    for text, measure in record["lines"]:
        # "Lime" + "Juice of 1" is lime juice; "Lime" + "1 wedge" is a garnish.
        base = clean(text)
        mfold = fold(measure)
        if base in ("lemon", "lime", "orange", "grapefruit"):
            if "juice" in mfold or re.fullmatch(NUM, mfold or "x"):
                text = f"{base} juice"
                if re.fullmatch(NUM, mfold or "x"):
                    measure = f"juice of {mfold}"
            elif record["source"] == "boston" and re.fullmatch(NUM + r"\s*oz", mfold):
                text = f"{base} juice"
        for part, part_measure, garnish_hint in split_composite(text, measure):
            action = classify(part)
            if garnish_hint and action not in ("G",) and not (action or "").startswith("="):
                action = "G"
            if garnish_hint and part in ("coarse salt", "salt", "superfine sugar", "sugar"):
                action = "G"
            if action is None:
                return [], [], f"unmapped: {part}"
            if action == "X":
                return [], [], f"rare: {part}"
            if action == "S":
                continue
            if action == "G":
                garnishes.append(part)
                continue
            optional = action.startswith("?") or "optional" in part or "if desired" in part
            ingredient_id = action[1:]
            try:
                amount, oz = parse_amount(part_measure, ingredient_id, record["source"],
                                          record.get("is_shot", False))
            except Batch:
                return [], [], "batch quantity"
            if ingredient_id == "salt" and amount != "pinch":
                # A line of salt in a Salty Dog or a Margarita is the rim.
                garnishes.append("salt")
                continue
            lines.append({"id": ingredient_id, "amount": amount, "oz": oz,
                          "optional": optional, "text": part})
    return lines, garnishes, None


def tidy_lines(lines: list[dict]) -> list[dict]:
    """Merge duplicate ids (a recipe listing sugar twice) and drop ice."""
    seen, out = {}, []
    for ln in lines:
        if ln["id"] in ("ice",):
            continue
        if ln["id"] in seen:
            continue
        seen[ln["id"]] = ln
        out.append(ln)
    return out


# Garnish text

def garnish_text(words: list[str], iba_text: str | None) -> str | None:
    """Garnish words -> one readable phrase: "lime wheel, salt rim"."""
    phrases = []
    for w in words:
        w = w.replace("(optional)", "").strip()
        if w in ("coarse salt", "salt", "kosher salt") or "coarse salt" in w:
            phrases.append("salt rim")
        elif "sugar" in w:
            phrases.append("sugar rim")
        elif w in ("lemon", "lime", "orange"):
            phrases.append(f"{w} wedge")
        elif w in ("cherry", "maraschino cherry", "cherries"):
            phrases.append("cherry")
        elif w in ("olive", "green olive", "olives"):
            phrases.append("olive")
        elif w in ("nutmeg",):
            phrases.append("grated nutmeg")
        else:
            phrases.append(w)
    if iba_text:
        t = fold(iba_text).split(". ")[0].rstrip(".")
        t = re.sub(r"^(garnish(ed)?( optionally)? with|optionally garnish with|optional)\s+", "", t)
        t = re.sub(r"\((optional)?\)|\boptional(ly)?\b|^n/a,?", "", t).strip(" ,")
        if t and len(t) <= 60:
            phrases.insert(0, t)
    unique = []
    for p in phrases:
        p = re.sub(r"\s+", " ", p).strip(" .,")
        p = p.replace("mint springs", "mint sprigs").replace("mint leave", "mint leaf").replace("leaff", "leaf")
        if p and p not in unique:
            unique.append(p)
    return ", ".join(unique) or None


# Method, glass, kind

CARBONATED_TOPPERS = ("carbonated", "sparkling-wine", "beer")
SHAKE_SIGNALS = ("juice", "dairy", "egg-white", "sour-mix", "coconut-cream",
                 "syrup", "lemonade", "strawberry", "banana", "peach-puree")
LONG_JUICES = ("orange-juice", "cranberry-juice", "pineapple-juice",
               "grapefruit-juice", "tomato-juice", "apple-juice", "lemonade")

GLASS_MAP = [
    (r"shot|pousse|cordial", "shot"),
    (r"old.fashioned|whiskey sour|rocks", "rocks"),
    (r"highball", "highball"),
    (r"collins|mason|jar|parfait", "collins"),
    (r"flute|champagne", "flute"),
    (r"hurricane", "hurricane"),
    (r"copper", "copper mug"),
    (r"mug|irish coffee|coffee", "mug"),
    (r"pint|beer|pilsner", "pint"),
    (r"wine", "wine glass"),
    (r"snifter", "snifter"),
    (r"julep", "julep cup"),
    (r"tiki", "tiki mug"),
    (r"cocktail|martini|margarita|coupe", "coupe"),
]


def norm_glass(text: str | None) -> str | None:
    if not text:
        return None
    t = fold(text)
    for pattern, glass in GLASS_MAP:
        if re.search(pattern, t):
            return glass
    return None


def iba_glass(method_text: str) -> str | None:
    """IBA names the glass inside its method prose."""
    t = fold(method_text)
    for pattern, glass in [
        (r"copper mug", "copper mug"), (r"julep", "julep cup"),
        (r"highball", "highball"), (r"collins|tall glass", "collins"),
        (r"old.fashioned|rocks", "rocks"), (r"flute", "flute"),
        (r"wine glass|balloon", "wine glass"), (r"hurricane", "hurricane"),
        (r"tiki", "tiki mug"), (r"mug|irish coffee glass|coffee glass", "mug"),
        (r"cocktail glass|coupe|martini|margarita", "coupe"),
        (r"shot glass", "shot"),
    ]:
        if re.search(pattern, t):
            return glass
    return None


def has(lines, *ancestors):
    return any(is_under(ln["id"], a) for ln in lines for a in ancestors)


def infer_method(record: dict, lines: list[dict]) -> str:
    if re.search(r"old.fashioned", fold(record["name"])) and not has(lines, "juice"):
        return "stirred"
    text = fold(record.get("method_text") or "")
    if text:
        if "blend" in text:
            return "blended"
        if "layer" in text or ("float" in text and record.get("is_shot")):
            return "layered"
        if "shake" in text or "shaker" in text:
            return "shaken"
        if "stir" in text and ("mixing glass" in text or "strain" in text):
            return "stirred"
        return "built"

    if has(lines, "strawberry", "banana") and not has(lines, "carbonated"):
        return "blended"
    long_juice = any(ln["id"] in LONG_JUICES and (ln["oz"] or 0) >= 3 for ln in lines)
    hot = record.get("category") == "Coffee / Tea" or has(lines, "coffee", "tea")
    if hot and not has(lines, "juice", "egg-white"):
        return "built"
    if record.get("is_shot"):
        if has(lines, *SHAKE_SIGNALS):
            return "shaken"
        # Layering needs liqueurs of different weights.
        return "layered" if has(lines, "liqueur") and len(lines) >= 2 else "built"
    if long_juice and not has(lines, "egg-white", "dairy"):
        return "built"
    if has(lines, *SHAKE_SIGNALS):
        return "shaken"
    if has(lines, *CARBONATED_TOPPERS):
        return "built"
    return "stirred"


def infer_glass(record: dict, lines: list[dict], method: str) -> str:
    glass = iba_glass(record["method_text"]) if record.get("method_text") else None
    glass = glass or norm_glass(record.get("glass"))
    if record.get("is_shot"):
        return "shot"
    if re.search(r"old.fashioned", fold(record["name"])):
        return "rocks"
    if glass:
        return glass
    hot = has(lines, "coffee", "tea")
    if hot:
        return "mug"
    if method == "built":
        if has(lines, "sparkling-wine") and not has(lines, "juice", "carbonated"):
            return "flute"
        return "highball"
    if method == "blended":
        return "hurricane"
    if method == "stirred":
        return "coupe"
    # shaken
    long = has(lines, "carbonated") or any((ln["oz"] or 0) >= 3 for ln in lines)
    return "highball" if long else "coupe"


# Steps
# {id} renders "1 1/2 oz White Rum"; {id:name} renders "White Rum".

GLASS_PHRASE = {
    "coupe": "coupe", "rocks": "rocks glass", "highball": "highball glass",
    "collins": "collins glass", "flute": "champagne flute",
    "wine glass": "wine glass", "copper mug": "copper mug", "mug": "mug",
    "hurricane": "hurricane glass", "julep cup": "julep cup",
    "shot": "shot glass", "pint": "pint glass", "snifter": "snifter",
    "tiki mug": "tiki mug",
}
SERVED_UP = {"coupe", "flute", "shot", "snifter"}


def build_steps(recipe: dict) -> list[str]:
    method, glass = recipe["method"], recipe["glass"]
    g = GLASS_PHRASE.get(glass, glass)
    lines = [ln for ln in recipe["lines"] if ln["id"] not in ("ice",)]
    toppers = [ln for ln in lines
               if (has([ln], *CARBONATED_TOPPERS) or ln["amount"] == "top")
               and method in ("built", "shaken", "stirred", "layered")
               and not (method == "built" and len(lines) == 1)]
    body = [ln for ln in lines if ln not in toppers]
    muddle = [ln for ln in body if ln["id"] in ("mint", "basil", "cucumber", "strawberry")]
    if method == "blended":
        muddle = []
    body = muddle + [ln for ln in body if ln not in muddle]
    garnish = recipe.get("garnish") or ""
    steps: list[str] = []

    def add_each(first_where: str | None):
        for i, ln in enumerate(body):
            token = "{" + ln["id"] + "}"
            if i == 0 and first_where:
                steps.append(f"Add {token} to {first_where}.")
            else:
                steps.append(f"Add {token}.")

    if "salt rim" in garnish or "sugar rim" in garnish:
        what = "salt" if "salt rim" in garnish else "sugar"
        wedge = "lemon" if has(lines, "lemon-juice") and not has(lines, "lime-juice") else "lime"
        steps.append(f"Run a {wedge} wedge around the rim of a {g} and dip it in {what}.")
    elif glass in ("coupe", "flute") and method in ("shaken", "stirred"):
        steps.append(f"Chill a {g} (fill it with ice water while you mix).")

    if method == "shaken":
        if muddle:
            sweet = [ln for ln in body if ln not in muddle and has([ln], "syrup", "sugar")]
            rest = [ln for ln in body if ln not in muddle and ln not in sweet]
            for i, ln in enumerate(muddle + sweet):
                steps.append("Add {" + ln["id"] + "}" + (" to a shaker." if i == 0 else "."))
            steps.append("Press the {" + muddle[0]["id"] + ":name} gently with a muddler.")
            for ln in rest:
                steps.append("Add {" + ln["id"] + "}.")
        else:
            add_each("a shaker")
        if has(body, "egg-white"):
            steps.append("Shake without ice for 10 seconds to foam the egg.")
        steps.append("Fill the shaker with ice.")
        steps.append("Shake hard for 10 to 12 seconds.")
        if glass in SERVED_UP:
            if glass in ("coupe", "flute"):
                steps.append("Dump the ice water from the glass.")
            steps.append(f"Strain into the {'chilled ' if glass in ('coupe', 'flute') else ''}{g}.")
        else:
            steps.append(f"Fill a {g} with fresh ice.")
            steps.append("Strain the drink into the glass.")
        for t in toppers:
            steps.append("Top with {" + t["id"] + "}.")
        if toppers and glass not in SERVED_UP:
            steps.append("Stir gently once to mix.")

    elif method == "stirred":
        add_each("a mixing glass")
        steps.append("Fill the mixing glass with ice.")
        steps.append("Stir for about 30 seconds, until very cold.")
        if glass == "rocks":
            steps.append("Strain into a rocks glass over one large ice cube.")
        elif glass in ("coupe", "flute"):
            steps.append("Dump the ice water from the glass.")
            steps.append(f"Strain into the chilled {g}.")
        else:
            steps.append(f"Strain into a {g}.")
        for t in toppers:
            steps.append("Top with {" + t["id"] + "}.")

    elif method == "blended":
        add_each("a blender")
        steps.append("Add about 1 cup of ice.")
        steps.append("Blend until smooth.")
        steps.append(f"Pour into a {g}.")

    elif method == "layered":
        for i, ln in enumerate(body):
            token = "{" + ln["id"] + "}"
            if i == 0:
                steps.append(f"Pour {token} into a {g}.")
            else:
                steps.append(
                    f"Slowly pour {token} over the back of a bar spoon so it floats on top."
                )
        for t in toppers:
            steps.append("Top with {" + t["id"] + "}.")

    else:  # built
        hot = has(lines, "coffee", "tea") and glass == "mug"
        if hot:
            steps.append(f"Warm a {g} with hot water, then empty it.")
            add_each(f"the {g}")
            steps.append("Stir until any sugar dissolves.")
        elif glass == "shot":
            add_each("a shot glass")
        elif glass in ("flute",):
            add_each(f"a {g}")
            for t in toppers:
                steps.append("Top with {" + t["id"] + "}.")
        else:
            if muddle:
                token = "{" + muddle[0]["id"] + "}"
                steps.append(f"Add {token} to a {g}.")
                rest = body[1:]
                syrup = [ln for ln in rest if has([ln], "syrup", "sugar")]
                for ln in syrup:
                    steps.append("Add {" + ln["id"] + "}.")
                steps.append(f"Press the {{{muddle[0]['id']}:name}} gently with a muddler.")
                steps.append("Fill the glass with crushed ice.")
                for ln in rest:
                    if ln not in syrup:
                        steps.append("Add {" + ln["id"] + "}.")
            else:
                steps.append(f"Fill a {g} with ice.")
                for ln in body:
                    steps.append("Add {" + ln["id"] + "}.")
            for t in toppers:
                steps.append("Top with {" + t["id"] + "}.")
            steps.append("Stir gently to mix.")

    if garnish:
        shown = ", ".join(
            p for p in garnish.split(", ") if p not in ("salt rim", "sugar rim")
        )
        if re.match(r"(sprinkle|squeeze|express|rub|spray|float|dust)\b", shown):
            steps.append(shown[0].upper() + shown[1:] + ".")
        elif shown:
            steps.append(f"Garnish with {article(shown)}.")
    return steps


def article(phrase: str) -> str:
    """'lime wheel, cherry' -> 'a lime wheel and a cherry'."""
    parts = [p.strip() for p in re.split(r",\s*|\s+and\s+", phrase) if p.strip()]

    def one(p: str) -> str:
        p = {"pineapple": "pineapple wedge", "lime": "lime wedge", "lemon": "lemon wedge",
             "orange": "orange slice"}.get(p, p)
        if re.match(r"(a|an|the|grated|fresh|few|some|half|\d)\b", p) or p.endswith("s") \
                or p in ("mint", "nutmeg", "cinnamon", "lemon zest", "orange zest", "lime zest"):
            return p
        return ("an " if p[0] in "aeiou" else "a ") + p

    parts = [one(p) for p in parts]
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


SUMMARY = {
    ("shaken", True): "Shake with ice and strain into a chilled {g}.",
    ("shaken", False): "Shake with ice and strain into a {g} over fresh ice.",
    ("stirred", True): "Stir with ice and strain into a chilled {g}.",
    ("stirred", False): "Stir with ice and strain over a large cube.",
    ("built", False): "Build over ice in a {g} and stir gently.",
    ("built", True): "Build in a {g}.",
    ("blended", False): "Blend with ice until smooth.",
    ("blended", True): "Blend with ice until smooth.",
    ("layered", True): "Layer carefully in a {g}, heaviest first.",
    ("layered", False): "Layer carefully in a {g}, heaviest first.",
}


def summary(recipe: dict) -> str:
    glass = recipe["glass"]
    up = glass in SERVED_UP or glass == "mug"
    text = SUMMARY[(recipe["method"], up)].format(g=GLASS_PHRASE.get(glass, glass))
    if recipe["method"] == "shaken" and recipe["glass"] == "shot":
        text = "Shake with ice and strain into a shot glass."
    if recipe["method"] == "built" and recipe["glass"] == "mug":
        text = "Build in a warmed mug and stir."
    return text


# The pipeline

def base_family(lines: list[dict]) -> str:
    """The panel's spirit chip: Gin, Rum, Tequila, Vodka, Whiskey or Other."""
    best, best_oz = None, Fraction(-1)
    for ln in lines:
        oz = ln.get("oz") or Fraction(0)
        if is_under(ln["id"], "spirit") and oz > best_oz:
            best, best_oz = ln["id"], oz
    return family_of(best)


def family_of(ingredient_id: str | None) -> str:
    if not ingredient_id:
        return "other"
    for fam, roots in (("gin", ("gin",)), ("rum", ("rum", "flavored-rum", "cachaca")),
                       ("tequila", ("tequila", "mezcal")),
                       ("vodka", ("vodka", "flavored-vodka", "grain-alcohol")),
                       ("whiskey", ("whiskey", "flavored-whiskey"))):
        if any(is_under(ingredient_id, r) for r in roots):
            return fam
    return "other"


def shrink_shot(lines: list[dict]) -> None:
    """TheCocktailDB files some 5 oz drinks under "Shot"."""
    measured = [ln for ln in lines if ln.get("oz")]
    total = sum(ln["oz"] for ln in measured)
    if total <= Fraction(5, 2):
        return
    scale = Fraction(3, 2) / total
    for ln in measured:
        value = ln["oz"] * scale
        ln["amount"], ln["oz"] = fmt_oz(value), value


# Rough specific gravity, heaviest first; layered pours are re-sorted by it.
DENSITY = [
    (("grenadine", "syrup"), 1.25),
    (("creme-de-cassis",), 1.18),
    (("coffee-liqueur", "creme-de-cacao", "creme-de-menthe", "banana-liqueur"), 1.14),
    (("raspberry-liqueur", "blackberry-liqueur", "cherry-liqueur", "blue-curacao",
      "melon-liqueur", "galliano", "anise-liqueur", "amaretto"), 1.10),
    (("butterscotch-schnapps", "peach-schnapps", "sour-apple-schnapps",
      "peppermint-schnapps", "irish-cream", "rumchata"), 1.06),
    (("jagermeister", "hazelnut-liqueur", "southern-comfort", "drambuie"), 1.05),
    (("orange-liqueur", "cinnamon-schnapps", "chartreuse", "benedictine", "liqueur"), 1.03),
    (("dairy",), 1.01),
    (("overproof-rum",), 0.88),
    (("spirit",), 0.94),
]


def density(line: dict) -> float:
    for roots, value in DENSITY:
        if any(is_under(line["id"], r) for r in roots):
            return value
    return 1.0


def order_by_density(lines: list[dict]) -> None:
    """Sort a layered shot's pours heaviest first, in place (stable)."""
    lines.sort(key=lambda ln: -density(ln))


NAME_PROMISES = [
    (r"\bmilk\b|\bnog\b|eggnog|\bflip\b|alexander|\bcream\b", ("dairy", "whole-egg", "irish-cream", "coconut-cream")),
    (r"highball|cooler|rickey|collins|\bfizz\b|\bbuck\b|\bmule\b|spritzer|\bsoda\b|\bsplash\b", ("carbonated", "sparkling-wine")),
    (r"\bcola\b|\bcoke\b|libre", ("cola",)),
    (r"\bginger\b", ("ginger-ale", "ginger-beer", "ginger-syrup")),
    (r"\btonic\b", ("tonic-water",)),
    (r"coffee|espresso", ("coffee", "coffee-liqueur")),
    (r"\btoddy\b|\btea\b", ("water", "tea")),
    (r"lemonade", ("lemonade", "lemon-juice")),
    (r"champagne|royale?\b|\b75\b|sparkl", ("sparkling-wine",)),
    (r"\bpunch\b", ("juice", "sour-mix", "carbonated", "dairy")),
]


def sane_boston(record: dict, lines: list[dict]) -> str | None:
    """Reasons to distrust a Mr. Boston row; None means it looks fine."""
    if record.get("suspect"):
        return "row bled from a neighbour"
    wanted = BOSTON_SPIRIT.get(record["category"])
    if wanted and not has(lines, wanted):
        return f"filed under {record['category']} but has no {wanted}"
    # Mr. Boston dropped unmeasured lines, so a name promising a missing mixer is suspect.
    name = fold(record["name"])
    for words, needs in NAME_PROMISES:
        if re.search(words, name) and not has(lines, *needs):
            return f"name promises {needs[0]} but the line is missing"
    families = {family_of(ln["id"]) for ln in lines if is_under(ln["id"], "spirit")}
    spirits = [ln for ln in lines if is_under(ln["id"], "spirit")]
    if len(spirits) >= 3 and len(families) >= 3 and "tea" not in fold(record["name"]):
        return "three unrelated spirits"
    return None


def convert(record: dict, report: Counter):
    record["is_shot"] = (record["category"] in ("Shot", "Shooters")
                         or norm_glass(record.get("glass")) == "shot")
    lines, garnishes, reason = map_lines(record)
    if reason:
        report[reason.split(":")[0]] += 1
        return None, reason
    resolve_parts(lines, record["is_shot"])
    lines = tidy_lines(lines)
    real = [ln for ln in lines if not ln["optional"]]
    if len(real) < 2:
        return None, "fewer than two ingredients"
    if not has(lines, "spirit", "liqueur", "wine", "fortified-wine", "beer", "bitters"):
        return None, "no alcohol"
    if record["source"] == "boston":
        why = sane_boston(record, lines)
        if why:
            return None, why

    if record["is_shot"]:
        shrink_shot(lines)
    method = infer_method(record, lines)
    glass = infer_glass(record, lines, method)
    if method == "layered":
        order_by_density(lines)
    for ln in lines:
        if ln["amount"] is None and has([ln], *CARBONATED_TOPPERS, "juice", "lemonade"):
            ln["amount"] = "top"
        elif ln["amount"] is None and ln["id"] in ("egg-white", "whole-egg"):
            ln["amount"] = "1"
    return {
        "name": re.sub(r"\s+", " ", record["name"]).strip(),
        "kind": "shot" if record["is_shot"] else "cocktail",
        "source": record["source"],
        "ref": record["ref"],
        "category": record["category"],
        "method": method,
        "glass": glass,
        "garnish": garnish_text(garnishes, record.get("garnish_text")),
        "lines": lines,
    }, None


_INGREDIENT_WORDS = {fold(row[1]) for row in TAXONOMY} | {
    "champagne", "dubonnet", "bacardi", "brandy", "cognac", "sherry", "port",
    "vermouth", "scotch", "whiskey", "gin", "rum", "tequila", "vodka",
}
_SMALL_WORDS = {"on", "the", "of", "and", "a", "an", "in", "with", "de", "la", "au", "or"}


def display_name(name: str) -> str:
    """Tidy a dataset's drink name for display."""
    name = re.sub(r"\s+", " ", name).strip()
    stripped = re.sub(r"\s+Cocktail(?=(\s+No\.\s*\d+)?$)", "", name, flags=re.I).strip()
    if fold(stripped) not in _INGREDIENT_WORDS:
        name = stripped
    words = []
    for i, w in enumerate(name.split()):
        if w.isupper() and (len(w) > 3 or w == "KIR") and w not in ("VSOP",) and "." not in w:
            w = w.capitalize()
        elif "'" not in w and "-" not in w:
            w = w[:1].upper() + w[1:]
        if i and w.lower() in _SMALL_WORDS:
            w = w.lower()
        words.append(w)
    return " ".join(words)


def oz_of(amount: str | None) -> Fraction | None:
    """'1 1/2 oz' -> 3/2."""
    match = re.fullmatch(NUM + r"\s*oz", (amount or "").strip())
    return to_number(match.group(1)) if match else None


def from_hand(entry: dict, source: str, partial: bool = False) -> dict:
    """A hand-written recipe (extras.py, overrides.py) -> the pipeline's shape."""
    out = {k: v for k, v in entry.items() if k != "ingredients"}
    if "ingredients" in entry:
        for ingredient_id, _, _ in entry["ingredients"]:
            if ingredient_id not in NODE:
                raise SystemExit(f"{entry.get('name')}: unknown ingredient '{ingredient_id}'")
        out["lines"] = [
            {"id": i, "amount": a, "oz": oz_of(a), "optional": o, "text": i}
            for i, a, o in entry["ingredients"]
        ]
    if not partial:
        out.setdefault("kind", "cocktail")
        out.update(source=source, ref=f"{source}s.py" if source == "extra" else source)
        out["category"] = None
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    records = load_iba() + load_cocktaildb() + load_boston()
    report: Counter = Counter()
    unmapped: Counter = Counter()
    kept_by_key: dict[str, list[dict]] = defaultdict(list)
    seen_names: dict[str, set] = defaultdict(set)

    for record in records:
        key = name_key(display_name(record["name"]))
        seen_names[key].add(record["source"])
        if key in DROP:
            report["dropped by hand"] += 1
            continue
        recipe, reason = convert(record, report)
        if recipe is None:
            if reason and reason.startswith(("unmapped", "rare")):
                unmapped[reason] += 1
            else:
                report[reason] += 1
            continue
        kept_by_key[key].append(recipe)

    curated_keys = {name_key(r["name"]) for r in CURATED} | {name_key(s["name"]) for s in CURATED_SHOTS}
    curated_ids = {r["id"] for r in CURATED} | {s["id"] for s in CURATED_SHOTS}

    out, used_ids = [], set(curated_ids)
    for extra in EXTRAS:
        key = name_key(extra["name"])
        seen_names[key].add("extra")
        kept_by_key[key] = [from_hand(extra, "extra")] + kept_by_key.get(key, [])

    for key, versions in kept_by_key.items():
        if key in curated_keys:
            continue
        versions.sort(key=lambda r: SOURCE_PRIORITY[r["source"]])
        best = versions[0]
        name = display_name(best["name"])
        if key in OVERRIDES:
            best = {**best, **from_hand(OVERRIDES[key], best["source"], partial=True)}
            name = OVERRIDES[key].get("name", name)
        if "steps" not in best:
            best["steps"] = build_steps(best)
        rid = slugify(name)
        n = 2
        while rid in used_ids:
            rid, n = f"{slugify(name)}-{n}", n + 1
        used_ids.add(rid)
        sources = sorted(seen_names[key])
        lines = best["lines"]
        out.append({
            "id": rid,
            "name": name,
            "kind": best["kind"],
            "glass": best["glass"],
            "method": best["method"],
            "garnish": best.get("garnish"),
            "instructions": best.get("instructions") or summary(best),
            "steps": best["steps"],
            "ingredients": [
                [ln["id"], ln["amount"], bool(ln["optional"])]
                for ln in lines
            ],
            "base": best.get("base") or base_family(lines),
            "rank": rank_for(name, len(sources)),
            "sources": sources,
            "source_ref": f"{best['source']}:{best['ref']}",
        })

    out.sort(key=lambda r: (r["rank"], r["name"]))
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    kinds = Counter(r["kind"] for r in out)
    print(f"{len(records)} dataset records -> {len(out)} recipes "
          f"({kinds['cocktail']} cocktails, {kinds['shot']} shots) + "
          f"{len(CURATED)} curated cocktails + {len(CURATED_SHOTS)} curated shots")
    print(f"written to {OUT.relative_to(HERE.parent)}")
    if args.report:
        print("\nDropped:")
        for reason, count in report.most_common():
            print(f"  {count:4d}  {reason}")
        print("\nRare or unmapped ingredients that dropped a recipe (top 60):")
        for reason, count in unmapped.most_common(60):
            print(f"  {count:4d}  {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
