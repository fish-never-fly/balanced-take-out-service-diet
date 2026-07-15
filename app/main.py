import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from .menu_catalog import MenuCatalog
from .nutrition import NutritionInputError, NutritionRequest, calculate_daily_nutrition


app = FastAPI(title="Nutrition Analysis Service", version="1.0.0")
menu_catalog = MenuCatalog(
    os.getenv(
        "NUTRITION_MENU_FILE",
        str(Path(__file__).resolve().parent.parent / "examples" / "nutrition_menu.json"),
    )
)
INDEX_HTML = (Path(__file__).resolve().parent / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/nutrition")
def nutrition(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        request = NutritionRequest.from_dict(payload)
    except NutritionInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return calculate_daily_nutrition(request)


@app.get("/menu-items")
def list_menu_items(
    platform: str | None = Query(default=None, pattern="^(meituan|eleme|jd)$"),
    category: str | None = None,
    max_price_yuan: float | None = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict[str, Any]]:
    return menu_catalog.query(
        platform=platform,
        category=category,
        max_price_yuan=max_price_yuan,
        limit=limit,
    )
