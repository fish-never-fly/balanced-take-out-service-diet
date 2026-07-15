"""将基础模拟菜单确定性扩充到 160 道菜品。

脚本保留 sim-001 至 sim-044，并根据 29 个菜品模板生成四个价格档位。
同一 comparison_group 内的营养值仅小幅变化，但最高与最低价格相差约 2.6 倍，
用于测试推荐算法在营养相近时的价格排序和取舍逻辑。
"""

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
MENU_FILE = PROJECT_ROOT / "examples" / "nutrition_menu.json"
BASE_ITEM_COUNT = 44
TARGET_ITEM_COUNT = 160


# 字段依次为菜名、分类、每份克数、标准价格及七项每份营养值。
DISH_TEMPLATES: tuple[tuple[Any, ...], ...] = (
    ("香草鸡胸糙米饭", "杂粮饭", 440, 29.8, 560, 42, 14, 65, 8.0, 720, 2.0),
    ("西兰花牛肉饭", "盖饭", 470, 33.8, 690, 36, 23, 86, 6.0, 1120, 4.0),
    ("三文鱼藜麦碗", "轻食饭", 420, 39.8, 575, 35, 20, 62, 10.0, 680, 2.0),
    ("菌菇豆腐五谷饭", "素食", 450, 25.8, 505, 24, 13, 72, 12.0, 650, 1.0),
    ("番茄虾仁意面", "意面", 430, 31.8, 610, 32, 17, 82, 7.0, 930, 5.0),
    ("照烧鸡腿饭", "盖饭", 490, 28.8, 735, 38, 24, 94, 5.0, 1480, 12.0),
    ("南瓜牛肉杂粮饭", "杂粮饭", 460, 32.8, 640, 35, 19, 83, 9.0, 960, 4.0),
    ("黑椒虾仁荞麦面", "拌面", 430, 30.8, 585, 30, 16, 81, 8.0, 1080, 4.0),
    ("冬菇滑鸡蒸饭", "蒸饭", 480, 27.8, 655, 36, 20, 85, 5.0, 1180, 3.0),
    ("清蒸鱼柳紫米饭", "蒸菜饭", 440, 36.8, 525, 40, 11, 65, 7.0, 720, 1.0),
    ("鹰嘴豆时蔬沙拉", "沙拉", 380, 26.8, 420, 20, 15, 50, 13.0, 520, 2.0),
    ("鸡肉牛油果沙拉", "沙拉", 370, 34.8, 455, 36, 21, 28, 10.0, 610, 2.0),
    ("番茄牛腩杂粮饭", "汤饭", 620, 34.8, 650, 38, 20, 78, 7.0, 1260, 4.0),
    ("山药排骨汤配饭", "汤饭", 650, 31.8, 625, 31, 22, 76, 6.0, 1150, 2.0),
    ("鸡丝香菇粥", "粥", 580, 20.8, 395, 24, 9, 55, 3.0, 960, 1.0),
    ("玉米虾仁炒饭", "炒饭", 470, 27.8, 695, 29, 22, 96, 6.0, 1320, 3.0),
    ("鸡蛋番茄荞麦面", "汤面", 590, 24.8, 530, 25, 14, 77, 9.0, 1100, 4.0),
    ("牛肉蔬菜全麦卷", "卷饼", 330, 29.8, 485, 31, 18, 48, 8.0, 880, 3.0),
    ("鸡胸红薯能量碗", "轻食饭", 430, 30.8, 510, 41, 12, 61, 9.0, 650, 2.0),
    ("豆皮木耳蔬菜饭", "素食", 440, 23.8, 495, 25, 14, 68, 11.0, 790, 2.0),
    ("咖喱鸡肉土豆饭", "咖喱饭", 510, 29.8, 755, 37, 25, 96, 6.0, 1420, 7.0),
    ("萝卜牛肉汤配饭", "炖汤饭", 650, 35.8, 610, 39, 17, 74, 7.0, 1190, 2.0),
    ("芦笋虾仁糙米饭", "杂粮饭", 430, 35.8, 535, 34, 13, 68, 8.0, 760, 2.0),
    ("香煎豆腐藜麦碗", "素食", 420, 28.8, 485, 25, 17, 59, 12.0, 700, 2.0),
    ("低脂鸡肉丸意面", "意面", 450, 30.8, 620, 38, 16, 82, 7.0, 1050, 5.0),
    ("牛肉彩椒意面", "意面", 460, 34.8, 675, 35, 22, 85, 7.0, 1170, 5.0),
    ("金枪鱼玉米三明治", "三明治", 300, 25.8, 445, 29, 15, 48, 6.0, 820, 5.0),
    ("鸡蛋菠菜全麦三明治", "三明治", 290, 23.8, 420, 23, 17, 44, 7.0, 690, 4.0),
    ("海带豆腐杂粮饭", "素食", 450, 22.8, 470, 22, 12, 69, 11.0, 780, 1.0),
)


# 四档价格制造明显价差；营养因子只做小幅浮动，保持同组菜品具有可比性。
VARIANTS: tuple[dict[str, Any], ...] = (
    {
        "label": "实惠版",
        "tier": "economy",
        "store": "街坊实惠餐厅",
        "price_factor": 0.72,
        "nutrition_factors": (1.02, 0.98, 1.03, 1.01, 0.97, 1.04, 1.02),
    },
    {
        "label": "标准版",
        "tier": "standard",
        "store": "城市标准食堂",
        "price_factor": 1.00,
        "nutrition_factors": (1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00),
    },
    {
        "label": "品质版",
        "tier": "quality",
        "store": "品质营养厨房",
        "price_factor": 1.45,
        "nutrition_factors": (0.99, 1.02, 0.98, 0.99, 1.03, 0.96, 0.95),
    },
    {
        "label": "精品版",
        "tier": "premium",
        "store": "精品健康餐厅",
        "price_factor": 1.90,
        "nutrition_factors": (0.98, 1.03, 0.97, 0.98, 1.05, 0.93, 0.90),
    },
)


NUTRIENT_FIELDS = (
    "energy_kcal",
    "protein_g",
    "fat_g",
    "carbohydrate_g",
    "fiber_g",
    "sodium_mg",
    "added_sugar_g",
)
PLATFORMS = ("meituan", "eleme", "jd")


def main() -> None:
    """保留基础菜品、生成价格档位变体并覆盖写回模拟菜单文件。"""

    payload = json.loads(MENU_FILE.read_text(encoding="utf-8"))
    base_items = [
        item
        for item in payload["items"]
        if int(item["id"].removeprefix("sim-")) <= BASE_ITEM_COUNT
    ]
    if len(base_items) != BASE_ITEM_COUNT:
        raise RuntimeError(f"expected {BASE_ITEM_COUNT} base items, found {len(base_items)}")

    generated: list[dict[str, Any]] = []
    next_id = BASE_ITEM_COUNT + 1
    for template_index, template in enumerate(DISH_TEMPLATES):
        name, category, serving_g, base_price, *base_nutrients = template
        group_id = f"similar-{template_index + 1:02d}"
        for variant_index, variant in enumerate(VARIANTS):
            nutrition = _scaled_nutrition(base_nutrients, variant["nutrition_factors"])
            generated.append(
                {
                    "id": f"sim-{next_id:03d}",
                    "platform": PLATFORMS[(template_index + variant_index) % len(PLATFORMS)],
                    "store_name": variant["store"],
                    "dish_name": f"{name}（{variant['label']}）",
                    "category": category,
                    "serving_g": serving_g,
                    "price_yuan": round(base_price * variant["price_factor"], 1),
                    "comparison_group": group_id,
                    "price_tier": variant["tier"],
                    "nutrition": nutrition,
                }
            )
            next_id += 1

    items = base_items + generated
    if len(items) != TARGET_ITEM_COUNT:
        raise RuntimeError(f"expected {TARGET_ITEM_COUNT} items, generated {len(items)}")

    output = {
        "dataset": "synthetic_takeaway_menu_v2",
        "description": (
            "用于推荐算法测试的160道模拟外卖数据；同一comparison_group内营养相近、"
            "价格档位差异明显。所有数值按每份记录，不代表真实商家检测结果。"
        ),
        "items": items,
    }
    MENU_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _scaled_nutrition(
    base_values: list[float],
    factors: tuple[float, ...],
) -> dict[str, float | int]:
    """按变体因子缩放营养值，热量和钠取整数，其余字段保留一位小数。"""

    result: dict[str, float | int] = {}
    for field, value, factor in zip(NUTRIENT_FIELDS, base_values, factors, strict=True):
        scaled = value * factor
        result[field] = round(scaled) if field in {"energy_kcal", "sodium_mg"} else round(scaled, 1)
    return result


if __name__ == "__main__":
    main()
