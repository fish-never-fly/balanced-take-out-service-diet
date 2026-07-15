import json
from pathlib import Path
from typing import Any


class MenuCatalogError(ValueError):
    pass


class MenuCatalog:
    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path)

    def load(self) -> list[dict[str, Any]]:
        payload = json.loads(self.file_path.read_text(encoding="utf-8"))
        items = payload.get("items")
        if not isinstance(items, list):
            raise MenuCatalogError("menu dataset must contain an items list")
        validated = [self._validate(item) for item in items]
        ids = [item["id"] for item in validated]
        if len(ids) != len(set(ids)):
            raise MenuCatalogError("menu item ids must be unique")
        return validated

    def query(
        self,
        platform: str | None = None,
        category: str | None = None,
        max_price_yuan: float | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        items = self.load()
        if platform:
            items = [item for item in items if item["platform"] == platform]
        if category:
            items = [item for item in items if item["category"] == category]
        if max_price_yuan is not None:
            items = [item for item in items if item["price_yuan"] <= max_price_yuan]
        return items[:limit]

    @staticmethod
    def _validate(item: Any) -> dict[str, Any]:
        if not isinstance(item, dict):
            raise MenuCatalogError("each menu item must be an object")
        required = {"id", "platform", "store_name", "dish_name", "category", "price_yuan", "nutrition"}
        missing = required - item.keys()
        if missing:
            raise MenuCatalogError(f"menu item is missing fields: {sorted(missing)}")
        nutrition = item["nutrition"]
        nutrient_fields = {
            "energy_kcal",
            "protein_g",
            "fat_g",
            "carbohydrate_g",
            "fiber_g",
            "sodium_mg",
            "added_sugar_g",
        }
        if not isinstance(nutrition, dict) or nutrient_fields - nutrition.keys():
            raise MenuCatalogError(f"menu item {item['id']} has incomplete nutrition data")
        numeric_values = [item["price_yuan"], *[nutrition[field] for field in nutrient_fields]]
        if any(not isinstance(value, (int, float)) or value < 0 for value in numeric_values):
            raise MenuCatalogError(f"menu item {item['id']} has invalid numeric values")
        return item
