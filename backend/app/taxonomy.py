"""The ingredient tree, and the queries that walk it."""

import re
import sqlite3
import unicodedata

# Seed taxonomy: (id, display name, parent id or None).
# Asking for a node accepts anything at or below it. Parents must come before children.

TAXONOMY = [
    # --- spirits ------------------------------------------------------------
    ("spirit",              "Spirit",                 None),
    ("gin",                 "Gin",                    "spirit"),
    ("london-dry-gin",      "London Dry Gin",         "gin"),
    ("old-tom-gin",         "Old Tom Gin",            "gin"),
    ("genever",             "Genever",                "gin"),
    ("rum",                 "Rum",                    "spirit"),
    ("white-rum",           "White Rum",              "rum"),
    ("aged-rum",            "Aged Rum",               "rum"),
    ("dark-rum",            "Dark Rum",               "rum"),
    # Spiced rum sits under rum; fruit-flavored rums don't (see flavored-spirit).
    ("spiced-rum",          "Spiced Rum",             "rum"),
    ("overproof-rum",       "Overproof Rum (151)",    "rum"),
    ("rhum-agricole",       "Rhum Agricole",          "rum"),
    ("cachaca",             "Cachaça",                "spirit"),
    ("whiskey",             "Whiskey",                "spirit"),
    ("bourbon",             "Bourbon",                "whiskey"),
    ("rye-whiskey",         "Rye Whiskey",            "whiskey"),
    ("tennessee-whiskey",   "Tennessee Whiskey",      "whiskey"),
    ("canadian-whisky",     "Canadian Whisky",        "whiskey"),
    ("scotch",              "Scotch",                 "whiskey"),
    ("islay-scotch",        "Islay Scotch",           "scotch"),
    ("irish-whiskey",       "Irish Whiskey",          "whiskey"),
    ("japanese-whisky",     "Japanese Whisky",        "whiskey"),
    ("tequila",             "Tequila",                "spirit"),
    ("blanco-tequila",      "Blanco Tequila",         "tequila"),
    ("reposado-tequila",    "Reposado Tequila",       "tequila"),
    ("anejo-tequila",       "Añejo Tequila",          "tequila"),
    ("mezcal",              "Mezcal",                 "spirit"),
    ("vodka",               "Vodka",                  "spirit"),
    ("brandy",              "Brandy",                 "spirit"),
    ("cognac",              "Cognac",                 "brandy"),
    ("applejack",           "Applejack / Calvados",   "brandy"),
    ("kirsch",              "Kirsch",                 "brandy"),
    ("pisco",               "Pisco",                  "spirit"),
    ("absinthe",            "Absinthe / Pastis",      "spirit"),
    ("aquavit",             "Aquavit",                "spirit"),
    ("soju",                "Soju",                   "spirit"),
    ("grain-alcohol",       "Grain Alcohol (Everclear)", "spirit"),

    # Flavored spirits get their own branch, so banana rum never counts as rum in a Mojito.
    ("flavored-spirit",     "Flavored Spirit",        "spirit"),
    ("flavored-rum",        "Flavored Rum",           "flavored-spirit"),
    ("coconut-rum",         "Coconut Rum (Malibu)",   "flavored-rum"),
    ("banana-rum",          "Banana Rum",             "flavored-rum"),
    ("citrus-rum",          "Citrus Rum (Bacardi Limón)", "flavored-rum"),
    ("flavored-vodka",      "Flavored Vodka",         "flavored-spirit"),
    ("citrus-vodka",        "Citrus Vodka (Citron)",  "flavored-vodka"),
    ("orange-vodka",        "Orange Vodka",           "flavored-vodka"),
    ("vanilla-vodka",       "Vanilla Vodka",          "flavored-vodka"),
    ("raspberry-vodka",     "Raspberry Vodka",        "flavored-vodka"),
    ("peach-vodka",         "Peach Vodka",            "flavored-vodka"),
    ("cherry-vodka",        "Cherry Vodka",           "flavored-vodka"),
    ("flavored-whiskey",    "Flavored Whiskey",       "flavored-spirit"),
    ("cinnamon-whiskey",    "Cinnamon Whisky (Fireball)", "flavored-whiskey"),
    ("honey-whiskey",       "Honey Whiskey",          "flavored-whiskey"),
    ("apple-whiskey",       "Apple Whisky (Crown Apple)", "flavored-whiskey"),

    # --- wine ---------------------------------------------------------------
    ("wine",                "Wine",                   None),
    ("sparkling-wine",      "Sparkling Wine",         "wine"),
    ("champagne",           "Champagne",              "sparkling-wine"),
    ("prosecco",            "Prosecco",               "sparkling-wine"),
    ("red-wine",            "Red Wine",               "wine"),
    ("white-wine",          "White Wine",             "wine"),
    # Sake only needs a home no recipe line wanders into.
    ("sake",                "Sake",                   "wine"),

    # --- fortified wine -----------------------------------------------------
    ("fortified-wine",      "Fortified Wine",         None),
    ("vermouth",            "Vermouth",               "fortified-wine"),
    ("sweet-vermouth",      "Sweet Vermouth",         "vermouth"),
    ("dry-vermouth",        "Dry Vermouth",           "vermouth"),
    ("blanc-vermouth",      "Blanc Vermouth",         "vermouth"),
    ("sherry",              "Sherry",                 "fortified-wine"),
    ("fino-sherry",         "Fino Sherry",            "sherry"),
    ("cream-sherry",        "Cream Sherry",           "sherry"),
    ("port",                "Port",                   "fortified-wine"),
    ("aperitif-wine",       "Aperitif Wine",          "fortified-wine"),
    ("lillet-blanc",        "Lillet Blanc",           "aperitif-wine"),
    ("dubonnet",            "Dubonnet Rouge",         "aperitif-wine"),

    # --- beer & cider -------------------------------------------------------
    ("beer",                "Beer & Cider",           None),
    ("lager",               "Lager",                  "beer"),
    ("stout",               "Stout (Guinness)",       "beer"),
    ("cider",               "Hard Cider",             "beer"),

    # --- liqueurs -----------------------------------------------------------
    ("liqueur",             "Liqueur",                None),
    ("orange-liqueur",      "Orange Liqueur",         "liqueur"),
    ("triple-sec",          "Triple Sec / Cointreau", "orange-liqueur"),
    ("curacao",             "Curaçao",                "orange-liqueur"),
    ("blue-curacao",        "Blue Curaçao",           "curacao"),
    ("grand-marnier",       "Grand Marnier",          "orange-liqueur"),
    ("amaro",               "Amaro",                  "liqueur"),
    ("campari",             "Campari",                "amaro"),
    ("aperol",              "Aperol",                 "amaro"),
    ("fernet",              "Fernet",                 "amaro"),
    ("amaro-nonino",        "Amaro Nonino",           "amaro"),
    ("cynar",               "Cynar",                  "amaro"),
    ("maraschino",          "Maraschino Liqueur",     "liqueur"),
    ("chartreuse",          "Chartreuse",             "liqueur"),
    ("green-chartreuse",    "Green Chartreuse",       "chartreuse"),
    ("yellow-chartreuse",   "Yellow Chartreuse",      "chartreuse"),
    ("benedictine",         "Bénédictine",            "liqueur"),
    ("coffee-liqueur",      "Coffee Liqueur",         "liqueur"),
    ("elderflower-liqueur", "Elderflower Liqueur",    "liqueur"),
    ("amaretto",            "Amaretto",               "liqueur"),
    ("irish-cream",         "Irish Cream",            "liqueur"),
    ("rumchata",            "RumChata",               "liqueur"),
    ("creme-de-cassis",     "Crème de Cassis",        "liqueur"),
    ("creme-de-menthe",     "Crème de Menthe",        "liqueur"),
    ("green-creme-de-menthe", "Green Crème de Menthe", "creme-de-menthe"),
    ("white-creme-de-menthe", "White Crème de Menthe", "creme-de-menthe"),
    ("creme-de-violette",   "Crème de Violette",      "liqueur"),
    ("creme-de-cacao",      "Crème de Cacao",         "liqueur"),
    ("white-creme-de-cacao", "White Crème de Cacao",  "creme-de-cacao"),
    ("dark-creme-de-cacao", "Dark Crème de Cacao",    "creme-de-cacao"),
    ("schnapps",            "Schnapps",               "liqueur"),
    ("peach-schnapps",      "Peach Schnapps",         "schnapps"),
    ("butterscotch-schnapps", "Butterscotch Schnapps", "schnapps"),
    ("peppermint-schnapps", "Peppermint Schnapps",    "schnapps"),
    ("cinnamon-schnapps",   "Cinnamon Schnapps (Goldschläger)", "schnapps"),
    ("sour-apple-schnapps", "Sour Apple Schnapps",    "schnapps"),
    ("fruit-liqueur",       "Fruit Liqueur",          "liqueur"),
    ("cherry-liqueur",      "Cherry Liqueur (Heering)", "fruit-liqueur"),
    ("apricot-liqueur",     "Apricot Liqueur",        "fruit-liqueur"),
    ("banana-liqueur",      "Banana Liqueur",         "fruit-liqueur"),
    ("melon-liqueur",       "Melon Liqueur (Midori)", "fruit-liqueur"),
    ("raspberry-liqueur",   "Raspberry Liqueur (Chambord)", "fruit-liqueur"),
    ("blackberry-liqueur",  "Blackberry Liqueur",     "fruit-liqueur"),
    ("strawberry-liqueur",  "Strawberry Liqueur",     "fruit-liqueur"),
    ("limoncello",          "Limoncello",             "fruit-liqueur"),
    ("hazelnut-liqueur",    "Hazelnut Liqueur (Frangelico)", "liqueur"),
    ("anise-liqueur",       "Anise Liqueur (Anisette, Ouzo)", "liqueur"),
    ("sambuca",             "Sambuca",                "anise-liqueur"),
    ("galliano",            "Galliano",               "liqueur"),
    ("drambuie",            "Drambuie",               "liqueur"),
    ("southern-comfort",    "Southern Comfort",       "liqueur"),
    ("jagermeister",        "Jägermeister",           "liqueur"),
    ("sloe-gin",            "Sloe Gin",               "liqueur"),
    ("vanilla-liqueur",     "Vanilla Liqueur (Licor 43)", "liqueur"),
    ("pimms",               "Pimm's No. 1",           "liqueur"),

    # --- bitters ------------------------------------------------------------
    ("bitters",             "Bitters",                None),
    ("aromatic-bitters",    "Aromatic Bitters",       "bitters"),
    ("orange-bitters",      "Orange Bitters",         "bitters"),
    ("peychauds-bitters",   "Peychaud's Bitters",     "bitters"),

    # --- mixers -------------------------------------------------------------
    ("mixer",               "Mixer",                  None),
    ("syrup",               "Syrup",                  "mixer"),
    ("simple-syrup",        "Simple Syrup",           "syrup"),
    ("rich-syrup",          "Rich / Demerara Syrup",  "syrup"),
    ("honey-syrup",         "Honey Syrup",            "syrup"),
    ("agave-syrup",         "Agave Syrup",            "syrup"),
    ("ginger-syrup",        "Ginger Syrup",           "syrup"),
    ("grenadine",           "Grenadine",              "syrup"),
    ("orgeat",              "Orgeat",                 "syrup"),
    ("raspberry-syrup",     "Raspberry Syrup",        "syrup"),
    ("passion-fruit-syrup", "Passion Fruit Syrup",    "syrup"),
    ("maple-syrup",         "Maple Syrup",            "syrup"),
    ("lime-cordial",        "Lime Cordial (Rose's)",  "syrup"),
    ("juice",               "Juice",                  "mixer"),
    ("lime-juice",          "Lime Juice",             "juice"),
    ("lemon-juice",         "Lemon Juice",            "juice"),
    ("orange-juice",        "Orange Juice",           "juice"),
    ("grapefruit-juice",    "Grapefruit Juice",       "juice"),
    ("pineapple-juice",     "Pineapple Juice",        "juice"),
    ("cranberry-juice",     "Cranberry Juice",        "juice"),
    ("apple-juice",         "Apple Juice",            "juice"),
    ("tomato-juice",        "Tomato Juice",           "juice"),
    ("peach-puree",         "Peach Purée / Nectar",   "juice"),
    ("sour-mix",            "Sour Mix",               "mixer"),
    ("lemonade",            "Lemonade",               "mixer"),
    ("carbonated",          "Carbonated",             "mixer"),
    ("soda-water",          "Soda Water",             "carbonated"),
    ("tonic-water",         "Tonic Water",            "carbonated"),
    ("ginger-beer",         "Ginger Beer",            "carbonated"),
    ("ginger-ale",          "Ginger Ale",             "carbonated"),
    ("cola",                "Cola",                   "carbonated"),
    ("lemon-lime-soda",     "Lemon-Lime Soda (Sprite)", "carbonated"),
    ("grapefruit-soda",     "Grapefruit Soda",        "carbonated"),
    ("energy-drink",        "Energy Drink (Red Bull)", "carbonated"),
    ("dairy",               "Dairy",                  "mixer"),
    ("heavy-cream",         "Cream",                  "dairy"),
    ("milk",                "Milk",                   "dairy"),
    ("coconut-cream",       "Coconut Cream",          "mixer"),
    ("coffee",              "Coffee / Espresso",      "mixer"),
    ("tea",                 "Tea",                    "mixer"),

    # --- fresh --------------------------------------------------------------
    ("fresh",               "Fresh",                  None),
    ("mint",                "Mint",                   "fresh"),
    ("basil",               "Basil",                  "fresh"),
    ("cucumber",            "Cucumber",               "fresh"),
    ("egg-white",           "Egg White",              "fresh"),
    # Whole egg sits under egg white: having eggs means having egg whites.
    ("whole-egg",           "Whole Egg",              "egg-white"),
    ("strawberry",          "Strawberries",           "fresh"),
    ("banana",              "Banana",                 "fresh"),

    # --- pantry -------------------------------------------------------------
    ("pantry",              "Pantry",                 None),
    ("ice",                 "Ice",                    "pantry"),
    ("water",               "Water",                  "pantry"),
    ("sugar",               "Sugar",                  "pantry"),
    ("salt",                "Salt",                   "pantry"),
    ("black-pepper",        "Black Pepper",           "pantry"),
    ("hot-sauce",           "Hot Sauce",              "pantry"),
    ("worcestershire-sauce", "Worcestershire Sauce",  "pantry"),
    ("celery-salt",         "Celery Salt",            "pantry"),
    ("olive-brine",         "Olive Brine",            "pantry"),
    ("pickle-brine",        "Pickle Brine",           "pantry"),
]

# Always treated as on hand, so "no ice" never blocks a drink.
ASSUMED_ON_HAND = {"ice", "water", "sugar", "salt", "black-pepper"}


# Aliases: product-name fragments mapped to categories.
# Only ever a suggestion; the user confirms the category.

ALIASES = {
    # vermouth & aperitif wine
    "carpano":          "sweet-vermouth",
    "antica":           "sweet-vermouth",
    "punt e mes":       "sweet-vermouth",
    "rosso":            "sweet-vermouth",
    "sweet vermouth":   "sweet-vermouth",
    "red vermouth":     "sweet-vermouth",
    "italian vermouth": "sweet-vermouth",
    "dolin dry":        "dry-vermouth",
    "dry vermouth":     "dry-vermouth",
    "french vermouth":  "dry-vermouth",
    "noilly":           "dry-vermouth",
    "dolin blanc":      "blanc-vermouth",
    "bianco":           "blanc-vermouth",
    "blanc vermouth":   "blanc-vermouth",
    "vermouth":         "vermouth",
    "lillet":           "lillet-blanc",
    "kina lillet":      "lillet-blanc",
    "dubonnet":         "dubonnet",
    "sherry":           "sherry",
    "amontillado":      "sherry",
    "oloroso":          "sherry",
    "fino":             "fino-sherry",
    "manzanilla":       "fino-sherry",
    "tio pepe":         "fino-sherry",
    "cream sherry":     "cream-sherry",
    "bristol cream":    "cream-sherry",
    "port wine":        "port",
    "tawny port":       "port",
    "ruby port":        "port",
    "porto":            "port",
    "graham's":         "port",
    "sandeman":         "port",
    # gin
    "gin":              "gin",
    "tanqueray":        "london-dry-gin",
    "beefeater":        "london-dry-gin",
    "bombay":           "london-dry-gin",
    "gordon's":         "london-dry-gin",
    "sipsmith":         "london-dry-gin",
    "london dry":       "london-dry-gin",
    "hendrick":         "gin",
    "hendrick's gin":   "gin",
    "aviation gin":     "gin",
    "the botanist":     "gin",
    "plymouth":         "gin",
    "old tom":          "old-tom-gin",
    "genever":          "genever",
    # rum & cane
    "rum":              "rum",
    "bacardi":          "white-rum",
    "white rum":        "white-rum",
    "light rum":        "white-rum",
    "silver rum":       "white-rum",
    "plantation":       "aged-rum",
    "gold rum":         "aged-rum",
    "aged rum":         "aged-rum",
    "anejo rum":        "aged-rum",
    "appleton":         "aged-rum",
    "mount gay":        "aged-rum",
    "diplomatico":      "aged-rum",
    "el dorado":        "aged-rum",
    "zacapa":           "aged-rum",
    "gosling":          "dark-rum",
    "black rum":        "dark-rum",
    "dark rum":         "dark-rum",
    "myers":            "dark-rum",
    "blackstrap":       "dark-rum",
    "spiced rum":       "spiced-rum",
    "bacardi spiced":   "spiced-rum",
    "captain morgan":   "spiced-rum",
    "kraken":           "spiced-rum",
    "sailor jerry":     "spiced-rum",
    "overproof":        "overproof-rum",
    "151":              "overproof-rum",
    "wray & nephew":    "overproof-rum",
    "wray and nephew":  "overproof-rum",
    "agricole":         "rhum-agricole",
    "cachaca":          "cachaca",
    "cachaça":          "cachaca",
    # flavoured spirits
    "malibu":           "coconut-rum",
    "parrot bay":       "coconut-rum",
    "coconut rum":      "coconut-rum",
    "banana rum":       "banana-rum",
    "cruzan banana":    "banana-rum",
    "bacardi limon":    "citrus-rum",
    "citrus rum":       "citrus-rum",
    "flavored rum":     "flavored-rum",
    "citron":           "citrus-vodka",
    "citroen":          "citrus-vodka",
    "absolut citron":   "citrus-vodka",
    "absolut mandrin":  "orange-vodka",
    "absolut vanilia":  "vanilla-vodka",
    "absolut raspberri": "raspberry-vodka",
    "citrus vodka":     "citrus-vodka",
    "lemon vodka":      "citrus-vodka",
    "mandrin":          "orange-vodka",
    "orange vodka":     "orange-vodka",
    "vanilla vodka":    "vanilla-vodka",
    "vanilia":          "vanilla-vodka",
    "raspberri":        "raspberry-vodka",
    "raspberry vodka":  "raspberry-vodka",
    "peach vodka":      "peach-vodka",
    "cherry vodka":     "cherry-vodka",
    "whipped":          "flavored-vodka",
    "flavored vodka":   "flavored-vodka",
    "fireball":         "cinnamon-whiskey",
    "cinnamon whisk":   "cinnamon-whiskey",
    "tennessee honey":  "honey-whiskey",
    "american honey":   "honey-whiskey",
    "honey whisk":      "honey-whiskey",
    "crown apple":      "apple-whiskey",
    "regal apple":      "apple-whiskey",
    "tennessee apple":  "apple-whiskey",
    "apple whisk":      "apple-whiskey",
    # whiskey
    "whiskey":          "whiskey",
    "whisky":           "whiskey",
    "blended whiskey":  "whiskey",
    "seagram's 7":      "whiskey",
    "seagrams 7":       "whiskey",
    "bulleit rye":      "rye-whiskey",
    "rittenhouse":      "rye-whiskey",
    "rye whiskey":      "rye-whiskey",
    "rye whisky":       "rye-whiskey",
    "buffalo trace":    "bourbon",
    "makers mark":      "bourbon",
    "maker's mark":     "bourbon",
    "woodford":         "bourbon",
    "bourbon":          "bourbon",
    "bulleit":          "bourbon",
    "jim beam":         "bourbon",
    "wild turkey":      "bourbon",
    "evan williams":    "bourbon",
    "four roses":       "bourbon",
    "knob creek":       "bourbon",
    "elijah craig":     "bourbon",
    "old forester":     "bourbon",
    "jack daniel":      "tennessee-whiskey",
    "tennessee whiskey": "tennessee-whiskey",
    "george dickel":    "tennessee-whiskey",
    "crown royal":      "canadian-whisky",
    "canadian club":    "canadian-whisky",
    "black velvet":     "canadian-whisky",
    "canadian whisky":  "canadian-whisky",
    "laphroaig":        "islay-scotch",
    "ardbeg":           "islay-scotch",
    "lagavulin":        "islay-scotch",
    "bowmore":          "islay-scotch",
    "islay":            "islay-scotch",
    "scotch":           "scotch",
    "blended scotch":   "scotch",
    "johnnie walker":   "scotch",
    "dewar":            "scotch",
    "chivas":           "scotch",
    "famous grouse":    "scotch",
    "monkey shoulder":  "scotch",
    "glenfiddich":      "scotch",
    "glenlivet":        "scotch",
    "macallan":         "scotch",
    "single malt":      "scotch",
    "jameson":          "irish-whiskey",
    "irish whiskey":    "irish-whiskey",
    "tullamore":        "irish-whiskey",
    "bushmills":        "irish-whiskey",
    "redbreast":        "irish-whiskey",
    "suntory":          "japanese-whisky",
    "hibiki":           "japanese-whisky",
    "nikka":            "japanese-whisky",
    "yamazaki":         "japanese-whisky",
    "japanese whisky":  "japanese-whisky",
    # agave
    "tequila":          "tequila",
    "jose cuervo":      "tequila",
    "don julio":        "tequila",
    "casamigos":        "tequila",
    "sauza":            "tequila",
    "hornitos":         "tequila",
    "el jimador":       "tequila",
    "olmeca":           "tequila",
    "espolon":          "blanco-tequila",
    "patron silver":    "blanco-tequila",
    "silver tequila":   "blanco-tequila",
    "blanco":           "blanco-tequila",
    "plata":            "blanco-tequila",
    "reposado":         "reposado-tequila",
    "anejo":            "anejo-tequila",
    "mezcal":           "mezcal",
    "del maguey":       "mezcal",
    # other spirits
    "vodka":            "vodka",
    "titos":            "vodka",
    "tito's":           "vodka",
    "ketel one":        "vodka",
    "smirnoff":         "vodka",
    "absolut":          "vodka",
    "grey goose":       "vodka",
    "svedka":           "vodka",
    "stoli":            "vodka",
    "belvedere":        "vodka",
    "ciroc":            "vodka",
    "skyy":             "vodka",
    "deep eddy":        "vodka",
    "brandy":           "brandy",
    "hennessy":         "cognac",
    "remy martin":      "cognac",
    "courvoisier":      "cognac",
    "martell":          "cognac",
    "cognac":           "cognac",
    "calvados":         "applejack",
    "laird":            "applejack",
    "applejack":        "applejack",
    "kirsch":           "kirsch",
    "pisco":            "pisco",
    "absinthe":         "absinthe",
    "herbsaint":        "absinthe",
    "pastis":           "absinthe",
    "pernod":           "absinthe",
    "ricard":           "absinthe",
    "aquavit":          "aquavit",
    "akvavit":          "aquavit",
    "soju":             "soju",
    "jinro":            "soju",
    "chum churum":      "soju",
    "chamisul":         "soju",
    "everclear":        "grain-alcohol",
    "grain alcohol":    "grain-alcohol",
    # wine & beer
    "prosecco":         "prosecco",
    "cava":             "sparkling-wine",
    "champagne":        "champagne",
    "sparkling wine":   "sparkling-wine",
    "red wine":         "red-wine",
    "cabernet":         "red-wine",
    "merlot":           "red-wine",
    "pinot noir":       "red-wine",
    "malbec":           "red-wine",
    "zinfandel":        "red-wine",
    "white wine":       "white-wine",
    "chardonnay":       "white-wine",
    "sauvignon blanc":  "white-wine",
    "pinot grigio":     "white-wine",
    "riesling":         "white-wine",
    "sake":             "sake",
    "junmai":           "sake",
    "gekkeikan":        "sake",
    "lager":            "lager",
    "pilsner":          "lager",
    "corona":           "lager",
    "modelo":           "lager",
    "budweiser":        "lager",
    "bud light":        "lager",
    "coors":            "lager",
    "miller":           "lager",
    "heineken":         "lager",
    "stella artois":    "lager",
    "sapporo":          "lager",
    "asahi":            "lager",
    "hite":             "lager",
    "cass":             "lager",
    "stout":            "stout",
    "guinness":         "stout",
    "cider":            "cider",
    "angry orchard":    "cider",
    "strongbow":        "cider",
    # liqueurs
    "cointreau":        "triple-sec",
    "triple sec":       "triple-sec",
    "combier":          "triple-sec",
    "curacao":          "curacao",
    "curaçao":          "curacao",
    "blue curacao":     "blue-curacao",
    "grand marnier":    "grand-marnier",
    "orange liqueur":   "orange-liqueur",
    "campari":          "campari",
    "aperol":           "aperol",
    "fernet":           "fernet",
    "nonino":           "amaro-nonino",
    "cynar":            "cynar",
    "amaro":            "amaro",
    "averna":           "amaro",
    "montenegro":       "amaro",
    "ramazzotti":       "amaro",
    "luxardo":          "maraschino",
    "maraschino":       "maraschino",
    "green chartreuse": "green-chartreuse",
    "yellow chartreuse": "yellow-chartreuse",
    "chartreuse":       "chartreuse",
    "benedictine":      "benedictine",
    "bénédictine":      "benedictine",
    "kahlua":           "coffee-liqueur",
    "kahlúa":           "coffee-liqueur",
    "tia maria":        "coffee-liqueur",
    "mr black":         "coffee-liqueur",
    "coffee liqueur":   "coffee-liqueur",
    "st germain":       "elderflower-liqueur",
    "st-germain":       "elderflower-liqueur",
    "elderflower":      "elderflower-liqueur",
    "amaretto":         "amaretto",
    "disaronno":        "amaretto",
    "baileys":          "irish-cream",
    "bailey's":         "irish-cream",
    "irish cream":      "irish-cream",
    "carolans":         "irish-cream",
    "rumchata":         "rumchata",
    "horchata":         "rumchata",
    "cassis":           "creme-de-cassis",
    "creme de menthe":  "creme-de-menthe",
    "green creme de menthe": "green-creme-de-menthe",
    "white creme de menthe": "white-creme-de-menthe",
    "violette":         "creme-de-violette",
    "creme de cacao":   "creme-de-cacao",
    "white creme de cacao": "white-creme-de-cacao",
    "dark creme de cacao": "dark-creme-de-cacao",
    "brown creme de cacao": "dark-creme-de-cacao",
    "schnapps":         "schnapps",
    "peach schnapps":   "peach-schnapps",
    "peachtree":        "peach-schnapps",
    "peach liqueur":    "peach-schnapps",
    "butterscotch":     "butterscotch-schnapps",
    "buttershots":      "butterscotch-schnapps",
    "peppermint":       "peppermint-schnapps",
    "rumple minze":     "peppermint-schnapps",
    "goldschlager":     "cinnamon-schnapps",
    "hot damn":         "cinnamon-schnapps",
    "cinnamon schnapps": "cinnamon-schnapps",
    "sour apple":       "sour-apple-schnapps",
    "apple pucker":     "sour-apple-schnapps",
    "apple schnapps":   "sour-apple-schnapps",
    "heering":          "cherry-liqueur",
    "cherry liqueur":   "cherry-liqueur",
    "cherry brandy":    "cherry-liqueur",
    "apricot brandy":   "apricot-liqueur",
    "apricot liqueur":  "apricot-liqueur",
    "banana liqueur":   "banana-liqueur",
    "creme de banane":  "banana-liqueur",
    "99 bananas":       "banana-liqueur",
    "midori":           "melon-liqueur",
    "melon liqueur":    "melon-liqueur",
    "chambord":         "raspberry-liqueur",
    "raspberry liqueur": "raspberry-liqueur",
    "creme de mure":    "blackberry-liqueur",
    "blackberry liqueur": "blackberry-liqueur",
    "blackberry brandy": "blackberry-liqueur",
    "strawberry liqueur": "strawberry-liqueur",
    "limoncello":       "limoncello",
    "frangelico":       "hazelnut-liqueur",
    "hazelnut liqueur": "hazelnut-liqueur",
    "anisette":         "anise-liqueur",
    "ouzo":             "anise-liqueur",
    "sambuca":          "sambuca",
    "galliano":         "galliano",
    "drambuie":         "drambuie",
    "southern comfort": "southern-comfort",
    "jagermeister":     "jagermeister",
    "jager":            "jagermeister",
    "sloe gin":         "sloe-gin",
    "licor 43":         "vanilla-liqueur",
    "cuarenta y tres":  "vanilla-liqueur",
    "pimm":             "pimms",
    # bitters
    "angostura":        "aromatic-bitters",
    "aromatic bitters": "aromatic-bitters",
    "regans":           "orange-bitters",
    "orange bitters":   "orange-bitters",
    "peychaud":         "peychauds-bitters",
    # syrups & juices
    "simple syrup":     "simple-syrup",
    "sugar syrup":      "simple-syrup",
    "gomme":            "simple-syrup",
    "demerara syrup":   "rich-syrup",
    "rich syrup":       "rich-syrup",
    "honey syrup":      "honey-syrup",
    "honey":            "honey-syrup",
    # Not plain "agave": that's printed on every 100%-agave tequila label.
    "agave syrup":      "agave-syrup",
    "agave nectar":     "agave-syrup",
    "ginger syrup":     "ginger-syrup",
    "grenadine":        "grenadine",
    "orgeat":           "orgeat",
    "raspberry syrup":  "raspberry-syrup",
    "passion fruit":    "passion-fruit-syrup",
    "passionfruit":     "passion-fruit-syrup",
    "maple syrup":      "maple-syrup",
    "rose's lime":      "lime-cordial",
    "roses lime":       "lime-cordial",
    "lime cordial":     "lime-cordial",
    "lime juice":       "lime-juice",
    "fresh lime":       "lime-juice",
    "lemon juice":      "lemon-juice",
    "fresh lemon":      "lemon-juice",
    "orange juice":     "orange-juice",
    "grapefruit juice": "grapefruit-juice",
    "pineapple juice":  "pineapple-juice",
    "cranberry juice":  "cranberry-juice",
    "apple juice":      "apple-juice",
    "tomato juice":     "tomato-juice",
    "peach nectar":     "peach-puree",
    "peach puree":      "peach-puree",
    "sour mix":         "sour-mix",
    "sweet and sour":   "sour-mix",
    "sweet & sour":     "sour-mix",
    "lemonade":         "lemonade",
    # carbonated & dairy
    "soda water":       "soda-water",
    "club soda":        "soda-water",
    "sparkling water":  "soda-water",
    "tonic":            "tonic-water",
    "ginger beer":      "ginger-beer",
    "ginger ale":       "ginger-ale",
    "coca cola":        "cola",
    "coke":             "cola",
    "pepsi":            "cola",
    "cola":             "cola",
    "sprite":           "lemon-lime-soda",
    "7up":              "lemon-lime-soda",
    "7-up":             "lemon-lime-soda",
    "lemon-lime":       "lemon-lime-soda",
    "lemon lime":       "lemon-lime-soda",
    "grapefruit soda":  "grapefruit-soda",
    "squirt":           "grapefruit-soda",
    "fresca":           "grapefruit-soda",
    "red bull":         "energy-drink",
    "monster energy":   "energy-drink",
    "energy drink":     "energy-drink",
    "heavy cream":      "heavy-cream",
    "double cream":     "heavy-cream",
    "whipping cream":   "heavy-cream",
    "half and half":    "heavy-cream",
    "half & half":      "heavy-cream",
    "light cream":      "heavy-cream",
    "milk":             "milk",
    "coconut cream":    "coconut-cream",
    "cream of coconut": "coconut-cream",
    "coconut milk":     "coconut-cream",
    "espresso":         "coffee",
    "coffee":           "coffee",
    "iced tea":         "tea",
    "black tea":        "tea",
    "green tea":        "tea",
    # fresh & pantry
    "mint":             "mint",
    "egg white":        "egg-white",
    "eggs":             "whole-egg",
    "cucumber":         "cucumber",
    "basil":            "basil",
    "strawberr":        "strawberry",
    "banana":           "banana",
    "tabasco":          "hot-sauce",
    "hot sauce":        "hot-sauce",
    "cholula":          "hot-sauce",
    "worcestershire":   "worcestershire-sauce",
    "lea & perrins":    "worcestershire-sauce",
    "celery salt":      "celery-salt",
    "olive brine":      "olive-brine",
    "olive juice":      "olive-brine",
    "pickle brine":     "pickle-brine",
    "pickle juice":     "pickle-brine",
}


def seed(conn: sqlite3.Connection) -> None:
    """Load the taxonomy and aliases."""
    rows = [
        (ingredient_id, name, parent, 1 if ingredient_id in ASSUMED_ON_HAND else 0)
        for ingredient_id, name, parent in TAXONOMY
    ]
    with conn:
        conn.executemany(
            """
            INSERT INTO ingredient (id, name, parent_id, assumed_on_hand)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name            = excluded.name,
                parent_id       = excluded.parent_id,
                assumed_on_hand = excluded.assumed_on_hand
            """,
            rows,
        )
        conn.executemany(
            """
            INSERT INTO ingredient_alias (alias, ingredient_id)
            VALUES (?, ?)
            ON CONFLICT(alias) DO UPDATE SET ingredient_id = excluded.ingredient_id
            """,
            ALIASES.items(),
        )


# Walking the tree

def descendant_ids(conn: sqlite3.Connection, ingredient_id: str) -> list[str]:
    """Every node at or below `ingredient_id`, including itself."""
    rows = conn.execute(
        """
        WITH RECURSIVE subtree(id) AS (
            SELECT id FROM ingredient WHERE id = ?
            UNION ALL
            SELECT child.id
              FROM ingredient child
              JOIN subtree ON child.parent_id = subtree.id
        )
        SELECT id FROM subtree
        """,
        (ingredient_id,),
    ).fetchall()
    return [row["id"] for row in rows]


def ancestor_ids(conn: sqlite3.Connection, ingredient_id: str) -> list[str]:
    """Every node at or above `ingredient_id`, nearest first."""
    rows = conn.execute(
        """
        WITH RECURSIVE chain(id, parent_id) AS (
            SELECT id, parent_id FROM ingredient WHERE id = ?
            UNION ALL
            SELECT parent.id, parent.parent_id
              FROM ingredient parent
              JOIN chain ON chain.parent_id = parent.id
        )
        SELECT id FROM chain
        """,
        (ingredient_id,),
    ).fetchall()
    return [row["id"] for row in rows]


def bottles_satisfying(conn: sqlite3.Connection, ingredient_id: str) -> list[sqlite3.Row]:
    """Which bottles you own would satisfy a recipe asking for `ingredient_id`?"""
    ids = descendant_ids(conn, ingredient_id)
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    return conn.execute(
        f"""
        SELECT b.*, i.name AS ingredient_name
          FROM bottle b
          JOIN ingredient i ON i.id = b.ingredient_id
         WHERE b.ingredient_id IN ({placeholders})
         ORDER BY b.product_name
        """,
        ids,
    ).fetchall()


def satisfiable_ids(conn: sqlite3.Connection) -> set[str]:
    """Every requirement your shelf can currently meet -- as one set."""
    rows = conn.execute(
        """
        WITH RECURSIVE
        owned(id) AS (
            SELECT DISTINCT ingredient_id FROM bottle
            UNION
            SELECT id FROM ingredient WHERE assumed_on_hand = 1
        ),
        closure(id, parent_id) AS (
            SELECT i.id, i.parent_id
              FROM ingredient i
              JOIN owned o ON o.id = i.id
            UNION
            SELECT parent.id, parent.parent_id
              FROM ingredient parent
              JOIN closure ON closure.parent_id = parent.id
        )
        SELECT id FROM closure
        """
    ).fetchall()
    return {row["id"] for row in rows}


# Guessing a category from text

def _fold(text: str) -> str:
    """Lowercase and strip accents, so "Espolòn" matches the alias "espolon" and "Kahlúa" matches "kahlua"."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def suggest_ingredient(conn: sqlite3.Connection, product_name: str) -> str | None:
    """Best guess at a category for a product name, from the alias table."""
    haystack = _fold(product_name)
    matches: dict[str, int] = {}   # ingredient_id -> longest alias that hit it
    for row in conn.execute("SELECT alias, ingredient_id FROM ingredient_alias"):
        alias = _fold(row["alias"])
        if re.search(r"(?<![a-z0-9])" + re.escape(alias), haystack):
            node = row["ingredient_id"]
            matches[node] = max(matches.get(node, 0), len(alias))
    if not matches:
        return None

    chains = {node: ancestor_ids(conn, node) for node in matches}
    # A node is redundant if it's an ancestor of some OTHER matched node.
    redundant = {
        ancestor
        for node, chain in chains.items()
        for ancestor in chain[1:]
        if ancestor in matches
    }
    candidates = [node for node in matches if node not in redundant] or list(matches)
    return max(candidates, key=lambda node: (matches[node], len(chains[node]), node))


def resolve_ingredient(conn: sqlite3.Connection, text: str) -> str | None:
    """Map an imported recipe's ingredient text onto a category id."""
    probe = text.strip().lower()
    if not probe:
        return None

    if conn.execute("SELECT 1 FROM ingredient WHERE id = ?", (probe,)).fetchone():
        return probe

    row = conn.execute(
        "SELECT id FROM ingredient WHERE lower(name) = ?", (probe,)
    ).fetchone()
    if row:
        return row["id"]

    slug = re.sub(r"[^a-z0-9]+", "-", probe).strip("-")
    if conn.execute("SELECT 1 FROM ingredient WHERE id = ?", (slug,)).fetchone():
        return slug

    return suggest_ingredient(conn, probe)


# Families: the iPad's spirit chips. Flavored branches fold back into their base spirit here.

FAMILIES = [
    ("gin",     ("gin",)),
    ("rum",     ("rum", "flavored-rum", "cachaca")),
    ("tequila", ("tequila", "mezcal")),
    ("vodka",   ("vodka", "flavored-vodka", "grain-alcohol")),
    ("whiskey", ("whiskey", "flavored-whiskey")),
]

PARENT = {row[0]: row[2] for row in TAXONOMY}


def chain(ingredient_id: str) -> list[str]:
    """The node and its ancestors, nearest first -- from code, not the DB."""
    out = []
    node = ingredient_id
    while node and node not in out:
        out.append(node)
        node = PARENT.get(node)
    return out


def family_of(ingredient_id: str | None) -> str:
    """'blanco-tequila' -> 'tequila'."""
    if not ingredient_id:
        return "other"
    ancestors = set(chain(ingredient_id))
    for family, roots in FAMILIES:
        if ancestors & set(roots):
            return family
    return "other"


def is_spirit(ingredient_id: str) -> bool:
    return "spirit" in chain(ingredient_id)
