"""Hand fixes to specific converted recipes, keyed by ranking.name_key()."""

DROP = {
    "amaretto tea",        # 6 oz of hot tea filed as a shot
    "lemon shot",          # a lick-the-sugar ritual the steps can't express
    "quick f k",           # crude names on a guest-facing wall panel
    "royal bitch",
}

OVERRIDES = {
    "kir": {"glass": "wine glass"},
    "banana daiquiri": {"glass": "hurricane"},
    "amaretto sour": {"glass": "rocks"},
    "bellini": {
        "method": "built",
        "steps": [
            "Chill a champagne flute.",
            "Add {peach-puree} to the flute.",
            "Slowly top with {prosecco}, tilting the glass so it doesn't foam over.",
            "Stir gently once.",
        ],
    },
    "french martini": {"garnish": "lemon peel, expressed over the top"},
    "horse s neck": {"garnish": "long lemon peel spiral"},
    "pisco sour": {"garnish": "a few drops of aromatic bitters on the foam"},
}
