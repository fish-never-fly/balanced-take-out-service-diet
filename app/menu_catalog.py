"""本地模拟外卖菜单的读取、完整性校验和筛选功能。"""

import json
from pathlib import Path
from typing import Any


class MenuCatalogError(ValueError):
    """表示模拟菜单文件结构不完整或字段值不合法。"""

    pass


class MenuCatalog:
    """封装模拟菜单文件，向接口和推荐算法提供可信的菜品列表。"""

    def __init__(self, file_path: str | Path) -> None:
        """保存菜单文件路径；此时不读取文件，读取操作由 load 触发。"""

        self.file_path = Path(file_path)

    def load(self) -> list[dict[str, Any]]:
        """读取 JSON、校验每道菜并检查菜品 ID 是否唯一。"""

        # 使用 UTF-8 读取中文数据，并要求顶层必须包含 items 数组。
        payload = json.loads(self.file_path.read_text(encoding="utf-8"))
        items = payload.get("items")
        if not isinstance(items, list):
            raise MenuCatalogError("menu dataset must contain an items list")
        # 逐条执行字段和数值校验，避免后续推荐代码收到缺失营养数据的菜品。
        validated = [self._validate(item) for item in items]

        # 唯一 ID 是推荐结果定位菜品的基础，因此在加载阶段直接拒绝重复值。
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
        """按可选条件筛选模拟菜品，并限制返回数量。"""

        # 每次查询重新调用 load，以便开发过程中修改 JSON 后无需重启即可看到新数据。
        items = self.load()

        # 平台和分类采用精确匹配；没有传入对应参数时保留全部菜品。
        if platform:
            items = [item for item in items if item["platform"] == platform]
        if category:
            items = [item for item in items if item["category"] == category]
        # 最高价格采用包含边界的筛选，即价格恰好等于上限的菜品仍会返回。
        if max_price_yuan is not None:
            items = [item for item in items if item["price_yuan"] <= max_price_yuan]
        return items[:limit]

    @staticmethod
    def _validate(item: Any) -> dict[str, Any]:
        """校验单道菜的基本字段、营养字段和非负数值。"""

        # 菜品必须是 JSON 对象，不能是字符串、数组或其他类型。
        if not isinstance(item, dict):
            raise MenuCatalogError("each menu item must be an object")
        # 这些字段是显示菜单和执行推荐所需的最小信息集合。
        required = {"id", "platform", "store_name", "dish_name", "category", "price_yuan", "nutrition"}
        missing = required - item.keys()
        if missing:
            raise MenuCatalogError(f"menu item is missing fields: {sorted(missing)}")
        nutrition = item["nutrition"]
        # 所有营养数值均表示一份菜品的含量，推荐算法可直接与每日目标比较。
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
        # 价格和营养值必须是非负数字，防止字符串或负值破坏排序和评分。
        numeric_values = [item["price_yuan"], *[nutrition[field] for field in nutrient_fields]]
        if any(not isinstance(value, (int, float)) or value < 0 for value in numeric_values):
            raise MenuCatalogError(f"menu item {item['id']} has invalid numeric values")
        return item
