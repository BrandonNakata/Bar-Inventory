""""Most common drinks first" -- how the recipe list is ordered."""

import re
import unicodedata

# Names that are the same drink. Keys are already name_key()'d.
SAME_DRINK = {
    "dry martini": "martini",
    "gin tonic": "gin and tonic",
    "dark n stormy": "dark and stormy",
    "old fashioned cocktail": "old fashioned",
    "whisky sour": "whiskey sour",
    "corpse reviver 2": "corpse reviver no 2",
    "corpse reviver number 2": "corpse reviver no 2",
    "lemon drop martini": "lemon drop",
    "long island tea": "long island iced tea",
    "pornstar martini": "porn star martini",
    "kir royal": "kir royale",
    "ramos fizz": "ramos gin fizz",
    "hemingway special": "hemingway daiquiri",
    "apple martini": "appletini",
    "b52": "b 52",
    "jagerbomb": "jager bomb",
    "jaeger bomb": "jager bomb",
    "spritz veneziano": "aperol spritz",
    "spritz": "aperol spritz",
    "sbagliato": "negroni sbagliato",
    "cosmo": "cosmopolitan",
    "rum and coke": "cuba libre",
    "rum and coca cola": "cuba libre",
    "vodka cranberry": "cape codder",
    "cape cod": "cape codder",
    "seven and seven": "7 and 7",
    "7 and 7 highball": "7 and 7",
    "the last word": "last word",
    "french seventy five": "french 75",
    "3 wise men": "three wise men",
}


def name_key(name: str) -> str:
    """A drink's name, reduced to what matters for "is this the same drink?"."""
    t = unicodedata.normalize("NFKD", name.lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.replace("&", " and ").replace("'n'", " and ").replace("#", " no ")
    t = re.sub(r"\bno\.\s*", "no ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"\b(the|cocktail)\b", " ", t)
    t = re.sub(r"\bn\b", "and", t)
    t = re.sub(r"\s+", " ", t).strip()
    return SAME_DRINK.get(t, t)


RANKED = [
    # the drinks everyone knows
    "Margarita", "Old Fashioned", "Mojito", "Martini", "Moscow Mule",
    "Espresso Martini", "Negroni", "Manhattan", "Whiskey Sour", "Cosmopolitan",
    "Daiquiri", "Piña Colada", "Long Island Iced Tea", "Aperol Spritz",
    "Mimosa", "Bloody Mary", "Paloma", "Gin & Tonic", "Tom Collins", "Mai Tai",
    "White Russian", "Tequila Sunrise", "Screwdriver", "Cuba Libre",
    "Dark 'n' Stormy", "French 75", "Mint Julep", "Sidecar", "Gimlet",
    "Lemon Drop", "Sex on the Beach", "Black Russian", "Caipirinha",
    "Irish Coffee", "Vodka Tonic", "Vodka Soda", "Whiskey Ginger",
    "Jack and Coke", "Ranch Water", "Cape Codder", "Sazerac", "Bellini",
    "Hurricane", "Amaretto Sour", "Pisco Sour", "Dirty Martini", "Paper Plane",
    "Penicillin", "Boulevardier", "Americano", "Last Word", "Sea Breeze",
    "Greyhound", "Salty Dog", "Madras", "Bay Breeze", "Harvey Wallbanger",
    "Singapore Sling", "Zombie", "Painkiller", "Mudslide", "Blue Hawaiian",
    "Bahama Mama", "Rum Runner", "Kamikaze", "Appletini", "Midori Sour",
    "Blue Lagoon", "Electric Lemonade", "Fuzzy Navel", "Woo Woo",
    "Alabama Slammer", "Lynchburg Lemonade", "Hot Toddy", "7 and 7",
    "Tequila Soda", "Gin Rickey", "Bramble", "Bee's Knees",
    "Clover Club", "Aviation", "Corpse Reviver No. 2", "Vieux Carré", "Rob Roy",
    "Rusty Nail", "Godfather", "Stinger", "Grasshopper", "Brandy Alexander",
    "Kir Royale", "Kir", "Negroni Sbagliato", "Hugo Spritz", "Tommy's Margarita",
    "Naked and Famous", "Jungle Bird", "Southside", "Ramos Gin Fizz", "Gin Fizz",
    "Sloe Gin Fizz", "John Collins", "Vesper", "Porn Star Martini",
    "French Martini", "French Connection", "Gibson", "Vodka Gimlet",
    "Hanky Panky", "Bronx", "Between the Sheets", "Jack Rose", "Ward Eight",
    "Pink Lady", "Hemingway Daiquiri", "El Diablo", "Champagne Cocktail",
    "Brandy Crusta", "Bijou", "Martinez", "Tuxedo", "Mary Pickford",
    "Monkey Gland", "Garibaldi", "Illegal", "Trinidad Sour", "Suffering Bastard",
    "Yellow Bird", "Planter's Punch", "Scorpion", "Blood and Sand", "Toronto",
    "Horse's Neck", "Pimm's Cup", "Pink Squirrel", "Golden Cadillac",
    "Brandy Sour", "Whiskey Smash", "Oaxaca Old Fashioned", "Caipiroska",
    "Vodka Sour", "Perfect Manhattan", "Tequila Old Fashioned", "Mezcal Negroni",
    "Banana Daiquiri", "Strawberry Daiquiri", "Frozen Margarita",
    "Spiced Rum and Coke", "Malibu Bay Breeze", "Banana Colada",
    "Black Velvet", "Pisco Punch", "Hairy Navel", "Spiced Rum Mule", "Bushwacker",

    # shots, most-ordered first (they only ever sort among themselves)
    "Green Tea Shot", "Lemon Drop Shot", "B-52", "Kamikaze Shot", "Baby Guinness",
    "Jäger Bomb", "Washington Apple Shot", "Pickleback",
    "Buttery Nipple", "Slippery Nipple", "Irish Slammer", "Sake Bomb",
    "Somaek", "Tequila Slammer", "Mind Eraser", "Alabama Slammer Shot",
    "Scooby Snack", "Surfer on Acid", "Oatmeal Cookie", "Cinnamon Toast Crunch",
    "Vegas Bomb", "Boilermaker", "Tequila, Salt & Lime",
]

_POSITION: dict[str, int] = {}
for _i, _name in enumerate(RANKED, start=1):
    _POSITION.setdefault(name_key(_name), _i)


def rank_for(name: str, source_count: int = 1) -> int:
    """Lower is more common."""
    position = _POSITION.get(name_key(name))
    if position is not None:
        return position
    return 1000 * (4 - max(1, min(source_count, 3)))
