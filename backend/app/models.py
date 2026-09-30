"""Pydantic models -- the shape of what goes in and out over HTTP."""

from typing import Literal

from pydantic import BaseModel, Field


# Ingredients & bottles

class Ingredient(BaseModel):
    """One node in the taxonomy tree."""
    id: str
    name: str
    parent_id: str | None = None
    assumed_on_hand: bool = False


class BottleCreate(BaseModel):
    """What the client sends to add a bottle."""
    product_name: str = Field(min_length=1, max_length=200)
    ingredient_id: str
    barcode: str | None = None


class Bottle(BaseModel):
    """What the server sends back for a bottle."""
    id: int
    product_name: str
    ingredient_id: str
    ingredient_name: str      # joined in, so the UI doesn't have to look it up
    barcode: str | None = None
    added_at: str


class Suggestion(BaseModel):
    """The alias map's guess at a category for a product name."""
    product_name: str
    ingredient_id: str | None
    ingredient_name: str | None


class BarcodeLookup(BaseModel):
    """Everything the UI needs after a scan."""
    barcode: str                              # normalised form
    found: bool                               # do we know a product name?
    product_name: str | None = None
    brand: str | None = None
    source: str                               # openfoodfacts | upcitemdb | manual | none
    ingredient_id: str | None = None  # category confirmed before
    ingredient_name: str | None = None
    suggested_ingredient_id: str | None = None   # the alias map's guess
    suggested_ingredient_name: str | None = None
    on_shelf: list[Bottle] = []               # bottles already carrying it
    cached: bool                              # answered without the network?
    lookup_error: str | None = None           # sources that couldn't be reached


# Recipes

class RecipeLine(BaseModel):
    """One ingredient line of a recipe, marked against your shelf."""
    ingredient_id: str
    ingredient_name: str
    amount: str | None = None
    optional: bool = False
    note: str | None = None
    have: bool


class Recipe(BaseModel):
    """A recipe, already judged against what you own."""
    id: str
    name: str
    kind: Literal["cocktail", "shot"] = "cocktail"
    glass: str | None = None
    method: str | None = None
    garnish: str | None = None      # decoration, never a requirement
    instructions: str | None = None
    steps: list[str] = []           # rendered: "Add 2 oz Gin to a shaker."
    steps_template: list[str] = []  # stored:   "Add {gin} to a shaker."
    source: str
    rank: int = 3000                # lower = more commonly ordered
    base: str = "other"             # gin | rum | tequila | vodka | whiskey | other
    hidden: bool = False
    edited: bool = False  # a seeded recipe that was edited
    ingredients: list[RecipeLine]
    missing: list[RecipeLine]  # required lines not on the shelf
    # Literal so the docs list the three values and typos fail loudly.
    status: Literal["makeable", "one_short", "not_tonight"]


class RecipeLineIn(BaseModel):
    """One ingredient line, as the phone's editor sends it."""
    ingredient_id: str
    amount: str | None = Field(default=None, max_length=40)
    optional: bool = False


class RecipeIn(BaseModel):
    """A whole recipe from the phone's editor -- for creating one, or for replacing one you've edited."""
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["cocktail", "shot"] = "cocktail"
    glass: str | None = Field(default=None, max_length=40)
    method: str | None = Field(default=None, max_length=40)
    garnish: str | None = Field(default=None, max_length=200)
    instructions: str | None = Field(default=None, max_length=300)
    steps: list[str] = Field(default=[], max_length=40)
    ingredients: list[RecipeLineIn] = Field(min_length=1, max_length=20)


class RecipeHidden(BaseModel):
    """PATCH body: take a recipe off the lists, or put it back."""
    hidden: bool


class RecipeList(BaseModel):
    """The whole list plus the counts a UI wants in its header."""
    inventory_count: int
    makeable_count: int
    one_short_count: int
    recipes: list[Recipe]


class ShoppingSuggestion(BaseModel):
    """One bottle worth buying, and what it would unlock."""
    ingredient_id: str
    ingredient_name: str
    unlocks: int
    recipes: list[str]
