"""根据每日营养目标，从模拟菜单中选择午餐和晚餐组合。

算法先穷举任意两道不同菜品的无序组合。如果组合完全满足所有可比较的营养条件，
则返回全部满足条件的组合并按总价格升序排列；如果没有完全满足的组合，则计算
加权偏离系数，并返回偏离程度最小的三个组合。
"""

from itertools import combinations
from typing import Any


# 基础权值总和为 1，体现热量和蛋白质优先，其次为三大营养素、钠、纤维和添加糖。
# 如果用户勾选三高，对应营养物质的权值会在 _build_weights 中进一步提高。
BASE_WEIGHTS: dict[str, float] = {
    "energy_kcal": 0.20,
    "protein_g": 0.20,
    "fat_g": 0.15,
    "carbohydrate_g": 0.15,
    "fiber_g": 0.10,
    "sodium_mg": 0.15,
    "added_sugar_g": 0.05,
}


# 每个元组依次表示：菜单营养字段、每日目标字段、约束类型。
# range 要求位于上下限内，minimum 只要求不低于下限，maximum 只要求不超过上限。
NUTRIENT_RULES: tuple[tuple[str, str, str], ...] = (
    ("energy_kcal", "energy_kcal", "range"),
    ("protein_g", "protein_g", "range"),
    ("fat_g", "fat_g", "range"),
    ("carbohydrate_g", "carbohydrate_g", "range"),
    ("fiber_g", "dietary_fiber_g", "minimum"),
    ("sodium_mg", "sodium_max_mg", "maximum"),
    ("added_sugar_g", "added_sugar_max_g", "maximum"),
)


class RecommendationError(ValueError):
    """表示菜单数量不足或营养目标结构不完整。"""

    pass


def recommend_takeaway_plans(
    items: list[dict[str, Any]],
    nutrition_analysis: dict[str, Any],
    breakfast_ratio: float = 0.25,
) -> dict[str, Any]:
    """扣除早餐占比后，返回满足条件的全部组合或偏离最小的三个组合。"""

    # 午餐和晚餐必须各选一道不同菜品，因此至少需要两个候选项。
    if len(items) < 2:
        raise RecommendationError("at least two menu items are required")
    if not 0 <= breakfast_ratio <= 0.5:
        raise RecommendationError("breakfast_ratio must be between 0 and 0.5")

    try:
        daily_targets = nutrition_analysis["daily_targets"]
        health_flags = nutrition_analysis["input"]["health_flags"]
    except KeyError as exc:
        raise RecommendationError("nutrition analysis is missing required targets") from exc

    # 假设早餐按同一比例承担各项营养需求，将每日目标同比扣除后得到两餐剩余目标。
    remaining_targets = _deduct_breakfast(daily_targets, breakfast_ratio)

    # 健康标记会调整不同营养物质的重要程度，归一化后的权值用于所有组合评分。
    weights = _build_weights(health_flags)
    evaluated: list[dict[str, Any]] = []

    # combinations 只生成无序且不重复的两菜组合，避免 A+B 与 B+A 被重复展示。
    for lunch, dinner in combinations(items, 2):
        totals = _sum_nutrition(lunch, dinner)
        deviations = _evaluate_deviations(totals, remaining_targets, weights)
        raw_score = sum(entry["weighted_deviation"] for entry in deviations.values())

        evaluated.append(
            {
                "lunch": _item_summary(lunch),
                "dinner": _item_summary(dinner),
                "total_price_yuan": round(lunch["price_yuan"] + dinner["price_yuan"], 2),
                "nutrition_totals": totals,
                "deviation_score": round(raw_score, 6),
                "deviations": deviations,
                "is_exact_match": raw_score <= 1e-12,
            }
        )

    # 先寻找完全满足所有条件的组合；精确组合只按价格和菜品 ID 排序。
    exact_matches = [plan for plan in evaluated if plan["is_exact_match"]]
    if exact_matches:
        plans = sorted(
            exact_matches,
            key=lambda plan: (
                plan["total_price_yuan"],
                plan["lunch"]["id"],
                plan["dinner"]["id"],
            ),
        )
        mode = "exact"
        message = "找到完全满足营养条件的组合，已按总价格从低到高排列。"
    else:
        # 没有精确组合时，先按加权偏离系数排序；系数相同则优先选择价格更低的组合。
        plans = sorted(
            evaluated,
            key=lambda plan: (
                plan["deviation_score"],
                plan["total_price_yuan"],
                plan["lunch"]["id"],
                plan["dinner"]["id"],
            ),
        )[:3]
        mode = "closest"
        message = "没有组合完全满足全部条件，以下为加权偏离程度最小的三个组合。"

    return {
        "mode": mode,
        "message": message,
        "breakfast_ratio": breakfast_ratio,
        "remaining_ratio": round(1 - breakfast_ratio, 6),
        "remaining_targets": remaining_targets,
        "evaluated_combinations": len(evaluated),
        "exact_match_count": len(exact_matches),
        "weights": {key: round(value, 6) for key, value in weights.items()},
        "plans": plans,
    }


def _deduct_breakfast(
    daily_targets: dict[str, Any],
    breakfast_ratio: float,
) -> dict[str, Any]:
    """按早餐占比扣除每日目标，生成午餐和晚餐共同需要完成的剩余目标。"""

    remaining_ratio = 1 - breakfast_ratio
    result: dict[str, Any] = {}

    # 区间目标的上下限同比缩放，例如热量、蛋白质、脂肪和碳水。
    for key in ("energy_kcal", "protein_g", "fat_g", "carbohydrate_g"):
        target = daily_targets[key]
        result[key] = {
            "min": round(target["min"] * remaining_ratio, 2),
            "max": round(target["max"] * remaining_ratio, 2),
        }

    # 下限和上限型目标也同比缩放，表示早餐已占用相应比例的需求或允许量。
    for key in ("dietary_fiber_g", "sodium_max_mg", "added_sugar_max_g"):
        result[key] = round(daily_targets[key] * remaining_ratio, 2)

    return result


def _build_weights(health_flags: dict[str, bool]) -> dict[str, float]:
    """根据三高情况调整基础权值，并重新归一化为总和 1。"""

    weights = BASE_WEIGHTS.copy()

    # 高血糖时更重视碳水总量和添加糖是否超标。
    if health_flags.get("high_blood_glucose"):
        weights["carbohydrate_g"] *= 1.5
        weights["added_sugar_g"] *= 2.0

    # 高血脂时提高脂肪偏离在总评分中的影响。
    if health_flags.get("high_blood_lipids"):
        weights["fat_g"] *= 1.75

    # 高血压时提高钠超标在总评分中的影响。
    if health_flags.get("high_blood_pressure"):
        weights["sodium_mg"] *= 2.0

    total = sum(weights.values())
    return {key: value / total for key, value in weights.items()}


def _sum_nutrition(
    lunch: dict[str, Any],
    dinner: dict[str, Any],
) -> dict[str, float]:
    """将午餐和晚餐每份营养值相加，得到两餐合计。"""

    return {
        field: round(lunch["nutrition"][field] + dinner["nutrition"][field], 2)
        for field in BASE_WEIGHTS
    }


def _evaluate_deviations(
    totals: dict[str, float],
    daily_targets: dict[str, Any],
    weights: dict[str, float],
) -> dict[str, dict[str, Any]]:
    """逐营养物质计算偏离比例、权值和加权偏离系数。"""

    result: dict[str, dict[str, Any]] = {}
    for nutrient, target_key, rule in NUTRIENT_RULES:
        value = totals[nutrient]
        target = daily_targets[target_key]
        ratio = _deviation_ratio(value, target, rule)
        weight = weights[nutrient]
        result[nutrient] = {
            "value": value,
            "target": target,
            "rule": rule,
            "deviation_ratio": round(ratio, 6),
            "weight": round(weight, 6),
            "weighted_deviation": round(ratio * weight, 6),
        }
    return result


def _deviation_ratio(value: float, target: Any, rule: str) -> float:
    """根据约束类型计算无量纲偏离比例，满足条件时返回 0。"""

    if rule == "range":
        minimum = float(target["min"])
        maximum = float(target["max"])
        if value < minimum:
            return (minimum - value) / minimum
        if value > maximum:
            return (value - maximum) / maximum
        return 0.0

    if rule == "minimum":
        minimum = float(target)
        return max(0.0, (minimum - value) / minimum)

    if rule == "maximum":
        maximum = float(target)
        return max(0.0, (value - maximum) / maximum)

    raise RecommendationError(f"unsupported nutrient rule: {rule}")


def _item_summary(item: dict[str, Any]) -> dict[str, Any]:
    """提取页面展示和结果追踪所需的菜品字段。"""

    return {
        "id": item["id"],
        "platform": item["platform"],
        "store_name": item["store_name"],
        "dish_name": item["dish_name"],
        "category": item["category"],
        "price_yuan": item["price_yuan"],
        "nutrition": item["nutrition"],
    }
