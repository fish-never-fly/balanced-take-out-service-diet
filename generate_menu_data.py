"""确定性生成 420 道模拟外卖菜品。

数据由两部分组成：
1. 60 个相似组，每组三个价格档位，共 180 道拥有相似菜的菜品。
2. 240 道差异化菜品，任意两道之间至少有一项核心营养相对差异超过 10%。
"""

import json
from itertools import product
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
MENU_FILE = PROJECT_ROOT / "examples" / "nutrition_menu.json"
SIMILAR_GROUP_COUNT = 60
SIMILAR_VARIANTS_PER_GROUP = 3
DISTINCT_ITEM_COUNT = 240
TARGET_ITEM_COUNT = SIMILAR_GROUP_COUNT * SIMILAR_VARIANTS_PER_GROUP + DISTINCT_ITEM_COUNT


PROTEIN_NAMES = (
    "香草鸡胸",
    "黑椒牛肉",
    "蒜香虾仁",
    "清蒸鱼柳",
    "菌菇豆腐",
    "番茄鸡蛋",
    "金枪鱼玉米",
    "香煎三文鱼",
    "照烧鸡腿",
    "芹菜瘦肉",
)
STAPLE_NAMES = (
    ("糙米饭", "杂粮饭"),
    ("藜麦饭", "轻食饭"),
    ("荞麦面", "面食"),
    ("全麦意面", "意面"),
    ("紫米饭", "杂粮饭"),
    ("五谷饭", "杂粮饭"),
)
PLATFORMS = ("meituan", "eleme", "jd")


# 三档菜品的核心营养变化均控制在 10% 内，但价格差异明显。
SIMILAR_VARIANTS: tuple[dict[str, Any], ...] = (
    {
        "label": "实惠版",
        "tier": "economy",
        "store": "街坊实惠餐厅",
        "price_factor": 0.72,
        "factors": (1.02, 0.98, 1.03, 1.01, 0.97, 1.04, 1.02),
    },
    {
        "label": "标准版",
        "tier": "standard",
        "store": "城市标准食堂",
        "price_factor": 1.00,
        "factors": (1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00),
    },
    {
        "label": "精品版",
        "tier": "premium",
        "store": "精品健康餐厅",
        "price_factor": 1.90,
        "factors": (0.98, 1.03, 0.97, 0.98, 1.05, 0.93, 0.90),
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


def main() -> None:
    """生成相似组与差异化菜品，校验数量后覆盖写回 JSON。"""

    similar_items = _generate_similar_groups()
    distinct_items = _generate_distinct_items(start_id=len(similar_items) + 1)
    items = similar_items + distinct_items

    if len(items) != TARGET_ITEM_COUNT:
        raise RuntimeError(f"expected {TARGET_ITEM_COUNT} items, generated {len(items)}")

    payload = {
        "dataset": "synthetic_takeaway_menu_v3",
        "description": (
            "用于推荐算法测试的420道模拟外卖数据：180道属于60个营养相似组，"
            "240道差异化菜品两两之间至少有一项核心营养差异超过10%。"
        ),
        "items": items,
    }
    MENU_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _generate_similar_groups() -> list[dict[str, Any]]:
    """通过十种蛋白来源和六种主食组合生成 60 个三菜相似组。"""

    items: list[dict[str, Any]] = []
    next_id = 1
    for protein_index, protein_name in enumerate(PROTEIN_NAMES):
        for staple_index, (staple_name, category) in enumerate(STAPLE_NAMES):
            group_index = protein_index * len(STAPLE_NAMES) + staple_index
            base_values = _similar_group_base_values(protein_index, staple_index)
            base_price = 23 + protein_index * 1.7 + staple_index * 2.1
            serving_g = 390 + staple_index * 18 + protein_index * 4

            for variant_index, variant in enumerate(SIMILAR_VARIANTS):
                items.append(
                    {
                        "id": f"sim-{next_id:03d}",
                        "platform": PLATFORMS[(group_index + variant_index) % len(PLATFORMS)],
                        "store_name": variant["store"],
                        "dish_name": f"{protein_name}{staple_name}（{variant['label']}）",
                        "category": category,
                        "serving_g": serving_g,
                        "price_yuan": round(base_price * variant["price_factor"], 1),
                        "comparison_group": f"similar-{group_index + 1:03d}",
                        "price_tier": variant["tier"],
                        "data_role": "similar_group",
                        "nutrition": _scaled_nutrition(base_values, variant["factors"]),
                    }
                )
                next_id += 1
    return items


def _similar_group_base_values(
    protein_index: int,
    staple_index: int,
) -> tuple[float, ...]:
    """为每个相似组生成合理且确定的基础营养值。"""

    return (
        470 + protein_index * 19 + staple_index * 27,
        24 + protein_index * 2.4 + staple_index * 0.6,
        11 + protein_index % 5 * 2.8 + staple_index * 0.7,
        54 + staple_index * 8 + protein_index % 3 * 3,
        5 + staple_index * 1.1 + protein_index % 4 * 0.5,
        580 + protein_index % 6 * 95 + staple_index * 45,
        1 + (protein_index + staple_index) % 6,
    )


def _generate_distinct_items(start_id: int) -> list[dict[str, Any]]:
    """从离散营养网格中抽取 240 个互不相似的营养组合。"""

    protein_levels = (15.0, 19.0, 24.0, 31.0, 40.0)
    fat_levels = (8.0, 11.0, 15.0, 21.0, 29.0)
    carbohydrate_levels = (35.0, 46.0, 60.0, 78.0, 102.0)
    fiber_levels = (3.0, 4.0, 5.5, 7.5, 10.5)
    nutrient_grid = list(
        product(protein_levels, fat_levels, carbohydrate_levels, fiber_levels)
    )

    # 37 与网格长度 625 互质，按步长抽样可让营养组合分散在整个网格中。
    selected = [nutrient_grid[(index * 37) % len(nutrient_grid)] for index in range(DISTINCT_ITEM_COUNT)]
    items: list[dict[str, Any]] = []
    for index, (protein, fat, carbohydrate, fiber) in enumerate(selected):
        energy = round(protein * 4 + fat * 9 + carbohydrate * 4)
        item_id = start_id + index
        items.append(
            {
                "id": f"sim-{item_id:03d}",
                "platform": PLATFORMS[index % len(PLATFORMS)],
                "store_name": f"差异化营养厨房{index % 40 + 1:02d}",
                "dish_name": f"特色营养套餐{index + 1:03d}",
                "category": f"差异化套餐{index % 8 + 1}",
                "serving_g": 300 + index * 17 % 350,
                "price_yuan": round(18 + index * 7 % 55 + (index % 3) * 0.3, 1),
                "price_tier": "distinct",
                "data_role": "distinct",
                "nutrition": {
                    "energy_kcal": energy,
                    "protein_g": protein,
                    "fat_g": fat,
                    "carbohydrate_g": carbohydrate,
                    "fiber_g": fiber,
                    "sodium_mg": 350 + index * 73 % 1500,
                    "added_sugar_g": round(index * 3 % 15, 1),
                },
            }
        )
    return items


def _scaled_nutrition(
    base_values: tuple[float, ...],
    factors: tuple[float, ...],
) -> dict[str, float | int]:
    """缩放相似组营养值，热量和钠取整数，其余保留一位小数。"""

    result: dict[str, float | int] = {}
    for field, value, factor in zip(NUTRIENT_FIELDS, base_values, factors, strict=True):
        scaled = value * factor
        result[field] = round(scaled) if field in {"energy_kcal", "sodium_mg"} else round(scaled, 1)
    return result


if __name__ == "__main__":
    main()
