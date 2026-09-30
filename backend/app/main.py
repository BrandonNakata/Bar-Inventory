"""The FastAPI application itself."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import connect, init_db
from .recipe_data import seed_recipes
from .recipe_store import seed_library
from .routers import barcodes, bottles, ingredients, panel, recipes
from .taxonomy import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once on startup, and again on shutdown after the `yield`."""
    init_db()
    conn = connect()
    seed(conn)
    seed_recipes(conn)
    seed_library(conn)
    conn.close()
    yield


app = FastAPI(
    title="Bar Inventory API",
    description="What's on the shelf, and what that means you can drink.",
    version="0.6.0",
    lifespan=lifespan,
)


# CORS: allow LAN devices (panel, phones) on any port. Development uses the Vite proxy instead.

DEFAULT_ORIGIN_REGEX = (
    r"http://(localhost|127\.0\.0\.1|homeassistant(\.local)?"
    r"|10\.0\.0\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})(:\d+)?"
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=os.getenv("BAR_CORS_REGEX", DEFAULT_ORIGIN_REGEX),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Compression: /panel/recipes is ~750 KB of JSON, ~65 KB gzipped.

app.add_middleware(GZipMiddleware, minimum_size=1024)


# Routes

app.include_router(ingredients.router)
app.include_router(bottles.router)
app.include_router(recipes.router)
app.include_router(barcodes.router)
app.include_router(panel.router)


@app.get("/api/health", tags=["meta"])
def health():
    """Cheap liveness check."""
    return {"status": "ok", "service": "bar-inventory", "version": app.version}


# Serve the built React app when frontend/dist exists (production on the Pi).

STATIC_DIR = Path(
    os.getenv("BAR_STATIC_DIR")
    or Path(__file__).resolve().parents[2] / "frontend" / "dist"
).resolve()

if (STATIC_DIR / "index.html").is_file():
    # Hashed filenames, so a new build never serves stale assets.
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    # Must be the last route: the catch-all would swallow /api routes.
    @app.get("/{full_path:path}", include_in_schema=False)
    def react_app(full_path: str):
        # Unmatched /api and /panel paths get a JSON 404, not HTML.
        if full_path.startswith(("api/", "panel/")):
            raise HTTPException(status_code=404, detail="Not found")

        # Serve real files from dist; is_relative_to blocks path traversal.
        candidate = (STATIC_DIR / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(STATIC_DIR):
            return FileResponse(candidate)

        # Everything else is a React Router page, so return index.html.
        return FileResponse(
            STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"}
        )
