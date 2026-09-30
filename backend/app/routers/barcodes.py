"""Route for barcode lookup."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..barcode import InvalidBarcode, barcode_report, normalize_barcode
from ..db import get_db
from ..models import BarcodeLookup

router = APIRouter(prefix="/api/barcodes", tags=["barcodes"])


@router.get("/{code}", response_model=BarcodeLookup)
def lookup(code: str, db: sqlite3.Connection = Depends(get_db)):
    """What is this barcode, and do I already own it?"""
    try:
        barcode = normalize_barcode(code)
    except InvalidBarcode as err:
        raise HTTPException(status_code=400, detail=str(err))
    return barcode_report(db, barcode)
