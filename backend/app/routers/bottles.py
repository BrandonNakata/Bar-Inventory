"""Routes for the bottles you own -- your inventory."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status

from ..barcode import InvalidBarcode, normalize_barcode, remember_barcode
from ..db import get_db
from ..models import Bottle, BottleCreate
from ..taxonomy import bottles_satisfying

router = APIRouter(prefix="/api/bottles", tags=["bottles"])


def _fetch_bottle(db: sqlite3.Connection, bottle_id: int) -> sqlite3.Row | None:
    return db.execute(
        """
        SELECT b.id, b.product_name, b.ingredient_id, b.barcode, b.added_at,
               i.name AS ingredient_name
          FROM bottle b
          JOIN ingredient i ON i.id = b.ingredient_id
         WHERE b.id = ?
        """,
        (bottle_id,),
    ).fetchone()


@router.get("", response_model=list[Bottle])
def list_bottles(db: sqlite3.Connection = Depends(get_db)):
    """Everything on the shelf, newest first."""
    rows = db.execute(
        """
        SELECT b.id, b.product_name, b.ingredient_id, b.barcode, b.added_at,
               i.name AS ingredient_name
          FROM bottle b
          JOIN ingredient i ON i.id = b.ingredient_id
         ORDER BY b.id DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


@router.post("", response_model=Bottle, status_code=status.HTTP_201_CREATED)
def add_bottle(payload: BottleCreate, db: sqlite3.Connection = Depends(get_db)):
    """Add a bottle."""
    exists = db.execute(
        "SELECT 1 FROM ingredient WHERE id = ?", (payload.ingredient_id,)
    ).fetchone()
    if not exists:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown ingredient '{payload.ingredient_id}'",
        )

    # Store one canonical form so UPC-A and EAN-13 scans match.
    barcode = None
    if payload.barcode:
        try:
            barcode = normalize_barcode(payload.barcode)
        except InvalidBarcode as err:
            raise HTTPException(status_code=400, detail=str(err))

    with db:
        cursor = db.execute(
            """
            INSERT INTO bottle (product_name, ingredient_id, barcode)
            VALUES (?, ?, ?)
            """,
            (payload.product_name, payload.ingredient_id, barcode),
        )
        # Save the bottle and barcode memory in one transaction.
        if barcode:
            remember_barcode(db, barcode, payload.product_name, payload.ingredient_id)
    return dict(_fetch_bottle(db, cursor.lastrowid))


@router.delete("/{bottle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bottle(bottle_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Bottle's empty."""
    with db:
        cursor = db.execute("DELETE FROM bottle WHERE id = ?", (bottle_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"No bottle {bottle_id}")


@router.get("/satisfying/{ingredient_id}", response_model=list[Bottle])
def satisfying(ingredient_id: str, db: sqlite3.Connection = Depends(get_db)):
    """Which of your bottles would satisfy a recipe asking for this ingredient?"""
    return [dict(row) for row in bottles_satisfying(db, ingredient_id)]
