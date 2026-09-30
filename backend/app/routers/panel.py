"""The iPad wall panel's endpoint."""

import sqlite3

from fastapi import APIRouter, Depends

from ..db import get_db
from ..panel import panel_recipes
from ..shots import panel_shots

router = APIRouter(prefix="/panel", tags=["panel"])


@router.get("/recipes")
def recipes_for_panel(db: sqlite3.Connection = Depends(get_db)):
    """Every recipe, pre-shaped for the iPad's ES5 renderer."""
    return panel_recipes(db)


@router.get("/shots")
def shots_for_panel(db: sqlite3.Connection = Depends(get_db)):
    """What the Shots reel can land on, in Basic and Unique mode."""
    return panel_shots(db)
