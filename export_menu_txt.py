"""把模拟外卖 JSON 导出为便于查看和导入表格软件的 UTF-8 TXT。"""

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_FILE = PROJECT_ROOT / "examples" / "nutrition_menu.json"
OUTPUT_FILE = PROJECT_ROOT / "examples" / "nutrition_menu.txt"


HEADERS = (
    "菜品ID",
    "平台",
    "商家名称",
    "菜品名称",
    "分类",
    "每份重量(g)",
    "价格(元)",
    "热量(kcal)",
    "蛋白质(g)",
    "脂肪(g)",
    "碳水(g)",
    "膳食纤维(g)",
    "钠(mg)",
    "添加糖(g)",
    "营养近似组",
    "价格档位",
    "数据角色",
)


def main() -> None:
    """读取 JSON 菜品并逐行写为制表符分隔文本。"""

    payload = json.loads(SOURCE_FILE.read_text(encoding="utf-8"))
    items = payload["items"]
    lines = [
        f"# 数据集：{payload['dataset']}",
        f"# 说明：{payload['description']}",
        f"# 菜品数量：{len(items)}",
        "\t".join(HEADERS),
    ]
    lines.extend("\t".join(_item_row(item)) for item in items)
    OUTPUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _item_row(item: dict[str, Any]) -> list[str]:
    """按固定字段顺序生成一道菜的文本列。"""

    nutrition = item["nutrition"]
    values = (
        item["id"],
        item["platform"],
        item["store_name"],
        item["dish_name"],
        item["category"],
        item.get("serving_g", ""),
        item["price_yuan"],
        nutrition["energy_kcal"],
        nutrition["protein_g"],
        nutrition["fat_g"],
        nutrition["carbohydrate_g"],
        nutrition["fiber_g"],
        nutrition["sodium_mg"],
        nutrition["added_sugar_g"],
        item.get("comparison_group", ""),
        item.get("price_tier", "original"),
        item.get("data_role", ""),
    )
    return [_clean(value) for value in values]


def _clean(value: Any) -> str:
    """移除可能破坏制表符文本结构的换行与制表符。"""

    return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")


if __name__ == "__main__":
    main()
