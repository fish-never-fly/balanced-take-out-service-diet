"""根据每日营养目标选择午餐和晚餐组合。

性能设计：
1. 通过热量桶缩小营养近似菜的比较范围，每组只保留最低价菜。
2. 把菜品营养字典预转换为固定顺序元组，减少组合循环中的字符串键查询。
3. 精确匹配只保存精确结果；无精确解时流式维护最优三组，不保存全部组合。
4. 使用热量偏离作为安全下界，跳过不可能进入前三名或精确结果的组合。
"""

from dataclasses import dataclass
from itertools import combinations
from math import floor, log
from typing import Any


BASE_WEIGHTS: dict[str, float] = {
    "energy_kcal": 0.20,
    "protein_g": 0.20,
    "fat_g": 0.15,
    "carbohydrate_g": 0.15,
    "fiber_g": 0.10,
    "sodium_mg": 0.15,
    "added_sugar_g": 0.05,
}
NUTRIENT_FIELDS = tuple(BASE_WEIGHTS)
NUTRIENT_INDEX = {field: index for index, field in enumerate(NUTRIENT_FIELDS)}
NUTRITION_SIMILARITY_THRESHOLD = 0.12


# 每项依次为菜单字段、每日目标字段和约束类型。
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
    """表示菜单不足、输入结构错误或没有有效两菜组合。"""

    pass


@dataclass(frozen=True, slots=True)
class PreparedDish:
    """组合循环使用的紧凑菜品表示。"""

    source: dict[str, Any]
    nutrients: tuple[float, ...]
    normalized_name: str


@dataclass(frozen=True, slots=True)
class PairCandidate:
    """只保存最终候选需要的数据，避免为全部组合创建嵌套字典。"""

    lunch: PreparedDish
    dinner: PreparedDish
    total_price_yuan: float
    meal_totals: tuple[float, ...]
    daily_totals: tuple[float, ...]
    score: float

    def score_sort_key(self) -> tuple[float, float, str, str]:
        """兜底结果按偏离、价格和 ID 稳定排序。"""

        return (
            self.score,
            self.total_price_yuan,
            self.lunch.source["id"],
            self.dinner.source["id"],
        )

    def price_sort_key(self) -> tuple[float, str, str]:
        """精确结果按价格和 ID 稳定排序。"""

        return (
            self.total_price_yuan,
            self.lunch.source["id"],
            self.dinner.source["id"],
        )


def recommend_takeaway_plans(
    items: list[dict[str, Any]],
    nutrition_analysis: dict[str, Any],
    breakfast: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """将早餐计入全天摄入，返回全部精确组合或偏离最小的三组。"""

    if len(items) < 2:
        raise RecommendationError("at least two menu items are required")

    candidate_items, filter_report = filter_similar_dishes(items)
    prepared_items = [_prepare_dish(item) for item in candidate_items]

    try:
        daily_targets = nutrition_analysis["daily_targets"]
        health_flags = nutrition_analysis["input"]["health_flags"]
    except KeyError as exc:
        raise RecommendationError("nutrition analysis is missing required targets") from exc

    breakfast_data = breakfast or {
        "id": "none",
        "name": "未吃早餐",
        "serving_description": "不计入任何早餐摄入",
        "nutrition": {field: 0 for field in NUTRIENT_FIELDS},
    }
    _validate_breakfast(breakfast_data)
    breakfast_vector = _nutrition_vector(breakfast_data["nutrition"])

    weights = _build_weights(health_flags)
    weight_vector = tuple(weights[field] for field in NUTRIENT_FIELDS)
    energy_target = daily_targets["energy_kcal"]

    # exact_candidates 只保存精确解；top_three 的长度始终不超过 3。
    exact_candidates: list[PairCandidate] = []
    top_three: list[PairCandidate] = []
    same_name_pairs_skipped = 0
    considered_combinations = 0
    fully_scored_combinations = 0
    pruned_combinations = 0

    for lunch, dinner in combinations(prepared_items, 2):
        if lunch.normalized_name == dinner.normalized_name:
            same_name_pairs_skipped += 1
            continue

        considered_combinations += 1
        meal_totals = tuple(
            lunch.nutrients[index] + dinner.nutrients[index]
            for index in range(len(NUTRIENT_FIELDS))
        )
        daily_totals = tuple(
            meal_totals[index] + breakfast_vector[index]
            for index in range(len(NUTRIENT_FIELDS))
        )

        # 热量单项加权偏离是总偏离的下界，因此可用于不改变结果的安全剪枝。
        energy_ratio = _deviation_ratio(
            daily_totals[NUTRIENT_INDEX["energy_kcal"]],
            energy_target,
            "range",
        )
        energy_lower_bound = energy_ratio * weights["energy_kcal"]

        # 已找到精确解后，热量不满足的组合一定不可能成为新的精确解。
        if exact_candidates and energy_ratio > 0:
            pruned_combinations += 1
            continue

        # 尚无精确解时，如果仅热量偏离已劣于当前第三名，也无需计算其余六项。
        if (
            not exact_candidates
            and len(top_three) == 3
            and energy_lower_bound > top_three[-1].score
        ):
            pruned_combinations += 1
            continue

        fully_scored_combinations += 1
        score = _score_vector(daily_totals, daily_targets, weight_vector)
        candidate = PairCandidate(
            lunch=lunch,
            dinner=dinner,
            total_price_yuan=round(
                lunch.source["price_yuan"] + dinner.source["price_yuan"],
                2,
            ),
            meal_totals=meal_totals,
            daily_totals=daily_totals,
            score=score,
        )

        if score <= 1e-12:
            exact_candidates.append(candidate)
            top_three.clear()
        elif not exact_candidates:
            _keep_best_three(top_three, candidate)

    if considered_combinations == 0:
        raise RecommendationError("no valid two-dish combinations remain after filtering")

    if exact_candidates:
        selected = sorted(exact_candidates, key=PairCandidate.price_sort_key)
        mode = "exact"
        message = "找到完全满足营养条件的组合，已按总价格从低到高排列。"
    else:
        selected = sorted(top_three, key=PairCandidate.score_sort_key)
        mode = "closest"
        message = "没有组合完全满足全部条件，以下为加权偏离程度最小的三个组合。"

    # 仅在候选最终入选后构造详细偏离字典，显著降低大量菜品时的对象分配。
    plans = [
        _candidate_to_plan(candidate, daily_targets, weights)
        for candidate in selected
    ]
    return {
        "mode": mode,
        "message": message,
        "breakfast": breakfast_data,
        "candidate_filter": filter_report,
        "same_name_pairs_skipped": same_name_pairs_skipped,
        "evaluated_combinations": considered_combinations,
        "fully_scored_combinations": fully_scored_combinations,
        "pruned_combinations": pruned_combinations,
        "exact_match_count": len(exact_candidates),
        "weights": {key: round(value, 6) for key, value in weights.items()},
        "plans": plans,
    }


def filter_similar_dishes(
    items: list[dict[str, Any]],
    threshold: float = NUTRITION_SIMILARITY_THRESHOLD,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """通过热量桶缩小比较范围，每个营养近似组只保留最低价菜。"""

    if not 0 <= threshold <= 1:
        raise RecommendationError("nutrition similarity threshold must be between 0 and 1")

    ordered = sorted(items, key=lambda item: (item["price_yuan"], item["id"]))
    retained: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    energy_buckets: dict[int, list[dict[str, Any]]] = {}

    for candidate in ordered:
        if threshold == 0:
            possible_matches = retained
            bucket_index = 0
        else:
            bucket_index = _energy_bucket(candidate["nutrition"]["energy_kcal"], threshold)
            possible_matches = [
                kept
                for nearby_bucket in range(bucket_index - 1, bucket_index + 2)
                for kept in energy_buckets.get(nearby_bucket, ())
            ]

        similar_matches = [
            kept
            for kept in possible_matches
            if _nutrition_is_similar(kept["nutrition"], candidate["nutrition"], threshold)
        ]
        if not similar_matches:
            retained.append(candidate)
            energy_buckets.setdefault(bucket_index, []).append(candidate)
            continue

        # 处理顺序已按价格和 ID 排序；min 再次确保跨桶候选仍选择最优保留项。
        similar_kept = min(
            similar_matches,
            key=lambda item: (item["price_yuan"], item["id"]),
        )
        removed.append(
            {
                "removed_id": candidate["id"],
                "removed_name": candidate["dish_name"],
                "removed_price_yuan": candidate["price_yuan"],
                "kept_id": similar_kept["id"],
                "kept_name": similar_kept["dish_name"],
                "kept_price_yuan": similar_kept["price_yuan"],
                "price_saving_yuan": round(
                    candidate["price_yuan"] - similar_kept["price_yuan"],
                    2,
                ),
            }
        )

    if len(retained) < 2:
        retained = ordered[:2]
        retained_ids = {item["id"] for item in retained}
        removed = [entry for entry in removed if entry["removed_id"] not in retained_ids]

    report = {
        "original_count": len(items),
        "retained_count": len(retained),
        "removed_count": len(items) - len(retained),
        "similarity_threshold": threshold,
        "rule": "each similar nutrition group keeps only its cheapest item",
        "removed_examples": removed[:20],
    }
    return retained, report


def _energy_bucket(energy_kcal: float, threshold: float) -> int:
    """把热量映射到对数桶；营养近似菜只可能位于当前桶或相邻桶。"""

    safe_energy = max(float(energy_kcal), 1.0)
    bucket_width = log(1 / (1 - threshold))
    return floor(log(safe_energy) / bucket_width)


def _nutrition_is_similar(
    first: dict[str, float],
    second: dict[str, float],
    threshold: float,
) -> bool:
    """判断七项营养值的相对差异是否全部位于阈值内。"""

    for nutrient in NUTRIENT_FIELDS:
        first_value = float(first[nutrient])
        second_value = float(second[nutrient])
        denominator = max(abs(first_value), abs(second_value), 1.0)
        if abs(first_value - second_value) / denominator > threshold:
            return False
    return True


def _prepare_dish(item: dict[str, Any]) -> PreparedDish:
    """把字典菜品转换为组合循环使用的营养元组。"""

    return PreparedDish(
        source=item,
        nutrients=_nutrition_vector(item["nutrition"]),
        normalized_name=_normalized_dish_name(item["dish_name"]),
    )


def _nutrition_vector(nutrition: dict[str, float]) -> tuple[float, ...]:
    """按固定字段顺序生成营养数值元组。"""

    return tuple(float(nutrition[field]) for field in NUTRIENT_FIELDS)


def _normalized_dish_name(name: str) -> str:
    """统一菜名首尾空格和大小写，用于阻止同名菜重复进入组合。"""

    return name.strip().casefold()


def _keep_best_three(top_three: list[PairCandidate], candidate: PairCandidate) -> None:
    """流式维护偏离最小的三个候选，列表长度不会超过 3。"""

    top_three.append(candidate)
    top_three.sort(key=PairCandidate.score_sort_key)
    del top_three[3:]


def _score_vector(
    totals: tuple[float, ...],
    daily_targets: dict[str, Any],
    weights: tuple[float, ...],
) -> float:
    """直接在数值元组上计算总加权偏离，不创建中间字典。"""

    score = 0.0
    for nutrient, target_key, rule in NUTRIENT_RULES:
        index = NUTRIENT_INDEX[nutrient]
        score += _deviation_ratio(totals[index], daily_targets[target_key], rule) * weights[index]
    return score


def _candidate_to_plan(
    candidate: PairCandidate,
    daily_targets: dict[str, Any],
    weights: dict[str, float],
) -> dict[str, Any]:
    """把最终候选转换为接口需要的详细结构。"""

    meal_totals = _vector_to_dict(candidate.meal_totals)
    daily_totals = _vector_to_dict(candidate.daily_totals)
    deviations = _evaluate_deviations(daily_totals, daily_targets, weights)
    return {
        "lunch": _item_summary(candidate.lunch.source),
        "dinner": _item_summary(candidate.dinner.source),
        "total_price_yuan": candidate.total_price_yuan,
        "meal_nutrition_totals": meal_totals,
        "daily_nutrition_totals": daily_totals,
        "deviation_score": round(candidate.score, 6),
        "deviations": deviations,
        "is_exact_match": candidate.score <= 1e-12,
    }


def _vector_to_dict(vector: tuple[float, ...]) -> dict[str, float]:
    """仅在输出阶段把营养元组恢复为带字段名的字典。"""

    return {
        field: round(vector[index], 2)
        for index, field in enumerate(NUTRIENT_FIELDS)
    }


def _validate_breakfast(breakfast: dict[str, Any]) -> None:
    """确保早餐包含全部营养字段，且每个值都是非负数字。"""

    nutrition = breakfast.get("nutrition")
    if not isinstance(nutrition, dict):
        raise RecommendationError("breakfast nutrition must be an object")
    for field in NUTRIENT_FIELDS:
        value = nutrition.get(field)
        if not isinstance(value, (int, float)) or value < 0:
            raise RecommendationError(f"breakfast has invalid nutrient value: {field}")


def _build_weights(health_flags: dict[str, bool]) -> dict[str, float]:
    """根据三高情况调整基础权值，并重新归一化为总和 1。"""

    weights = BASE_WEIGHTS.copy()
    if health_flags.get("high_blood_glucose"):
        weights["carbohydrate_g"] *= 1.5
        weights["added_sugar_g"] *= 2.0
    if health_flags.get("high_blood_lipids"):
        weights["fat_g"] *= 1.75
    if health_flags.get("high_blood_pressure"):
        weights["sodium_mg"] *= 2.0

    total = sum(weights.values())
    return {key: value / total for key, value in weights.items()}


def _evaluate_deviations(
    totals: dict[str, float],
    daily_targets: dict[str, Any],
    weights: dict[str, float],
) -> dict[str, dict[str, Any]]:
    """仅为最终入选组合生成逐营养物质偏离详情。"""

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
    """根据约束类型计算偏离比例，满足条件时返回 0。"""

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
