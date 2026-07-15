"""营养计算和模拟菜单的回归测试。"""

import unittest
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

from app.breakfast import get_breakfast_preset, list_breakfast_presets
from app.menu_catalog import MenuCatalog
from app.nutrition import NutritionInputError, NutritionRequest, calculate_daily_nutrition
from app.recommendation import filter_similar_dishes, recommend_takeaway_plans


class NutritionTest(unittest.TestCase):
    """验证身体信息计算、健康条件调整和异常输入处理。"""

    def test_calculates_daily_targets(self) -> None:
        # 使用固定输入验证 BMI、基础代谢和热量范围，防止公式被意外改变。
        result = calculate_daily_nutrition(
            NutritionRequest(height_cm=170, weight_kg=65, age=30, sex="female")
        )

        self.assertEqual(result["body"]["bmi"], 22.5)
        self.assertEqual(result["body"]["bmi_category"], "healthy")
        self.assertEqual(result["body"]["basal_metabolic_rate_kcal"], 1402)
        self.assertEqual(result["body"]["activity_factor"], 1.2)
        self.assertEqual(result["daily_targets"]["energy_kcal"], {"min": 1598.0, "max": 1766.0})

    def test_activity_level_increases_energy_targets(self) -> None:
        # 使用相同身体信息分别计算三个活动等级，活动越强时热量目标必须越高。
        common = {"height_cm": 170, "weight_kg": 65, "age": 30, "sex": "female"}
        sedentary = calculate_daily_nutrition(NutritionRequest(**common, activity_level="sedentary"))
        moderate = calculate_daily_nutrition(NutritionRequest(**common, activity_level="moderate"))
        vigorous = calculate_daily_nutrition(NutritionRequest(**common, activity_level="vigorous"))

        self.assertLess(
            sedentary["daily_targets"]["energy_kcal"]["min"],
            moderate["daily_targets"]["energy_kcal"]["min"],
        )
        self.assertLess(
            moderate["daily_targets"]["energy_kcal"]["min"],
            vigorous["daily_targets"]["energy_kcal"]["min"],
        )

    def test_health_flags_tighten_relevant_targets(self) -> None:
        # 同时开启三高标记，确认钠、脂肪和碳水目标按预期收紧。
        result = calculate_daily_nutrition(
            NutritionRequest(
                height_cm=175,
                weight_kg=80,
                age=45,
                sex="male",
                high_blood_glucose=True,
                high_blood_lipids=True,
                high_blood_pressure=True,
            )
        )

        self.assertEqual(result["daily_targets"]["sodium_max_mg"], 1500)
        self.assertEqual(result["basis"]["fat"], "20%-25% of daily energy")
        self.assertEqual(result["basis"]["carbohydrate"], "45%-50% of daily energy")

    def test_rejects_out_of_range_input(self) -> None:
        # 80 厘米不在当前成人模型支持范围内，应在创建请求对象时直接拒绝。
        with self.assertRaises(NutritionInputError):
            NutritionRequest(height_cm=80, weight_kg=65, age=30, sex="female")


class MenuCatalogTest(unittest.TestCase):
    """验证模拟菜单的完整性、唯一性和筛选条件。"""

    def setUp(self) -> None:
        # 每个测试使用项目内同一份模拟菜单，避免依赖外部平台或网络。
        file_path = Path(__file__).resolve().parent.parent / "examples" / "nutrition_menu.json"
        self.catalog = MenuCatalog(file_path)

    def test_loads_complete_synthetic_menu(self) -> None:
        # 数据集应包含 160 道菜，并且每个 ID 必须唯一。
        items = self.catalog.load()

        self.assertEqual(len(items), 160)
        self.assertEqual(len({item["id"] for item in items}), 160)

    def test_similar_nutrition_groups_have_large_price_gaps(self) -> None:
        # 至少 20 组菜品应保持营养接近，同时最高价达到最低价的 2.5 倍以上。
        groups: dict[str, list[dict[str, object]]] = defaultdict(list)
        for item in self.catalog.load():
            if group := item.get("comparison_group"):
                groups[str(group)].append(item)

        self.assertGreaterEqual(len(groups), 20)
        for items in groups.values():
            prices = [float(item["price_yuan"]) for item in items]
            self.assertGreaterEqual(max(prices) / min(prices), 2.5)

            # 同组任意营养字段的最大值与最小值相差不超过 15%。
            for nutrient in items[0]["nutrition"]:
                values = [float(item["nutrition"][nutrient]) for item in items]
                if max(values) > 0:
                    self.assertLessEqual((max(values) - min(values)) / max(values), 0.15)

    def test_filters_menu_by_platform_and_price(self) -> None:
        # 组合筛选后，每条结果都必须同时满足平台和最高价格条件。
        items = self.catalog.query(platform="meituan", max_price_yuan=30)

        self.assertTrue(items)
        self.assertTrue(all(item["platform"] == "meituan" for item in items))
        self.assertTrue(all(item["price_yuan"] <= 30 for item in items))

    def test_reuses_validated_menu_cache(self) -> None:
        # 文件修改时间未变化时，第二次读取应直接复用已解析和校验的列表。
        first = self.catalog.load()
        second = self.catalog.load()

        self.assertIs(first, second)


class RecommendationTest(unittest.TestCase):
    """验证精确组合价格排序和无解时的前三名兜底逻辑。"""

    def setUp(self) -> None:
        file_path = Path(__file__).resolve().parent.parent / "examples" / "nutrition_menu.json"
        self.items = MenuCatalog(file_path).load()
        self.analysis = calculate_daily_nutrition(
            NutritionRequest(
                height_cm=170,
                weight_kg=65,
                age=30,
                sex="female",
                activity_level="moderate",
            )
        )

    def test_returns_three_closest_real_fixture_combinations(self) -> None:
        # 人为提高纤维目标以确保无精确解，从而稳定验证返回前三名的兜底分支。
        impossible_analysis = deepcopy(self.analysis)
        impossible_analysis["daily_targets"]["dietary_fiber_g"] = 1000
        result = recommend_takeaway_plans(self.items, impossible_analysis)

        self.assertEqual(result["mode"], "closest")
        retained_count = result["candidate_filter"]["retained_count"]
        self.assertGreater(result["candidate_filter"]["removed_count"], 0)
        self.assertEqual(
            result["evaluated_combinations"],
            retained_count * (retained_count - 1) // 2 - result["same_name_pairs_skipped"],
        )
        self.assertEqual(len(result["plans"]), 3)
        self.assertLessEqual(
            result["fully_scored_combinations"],
            result["evaluated_combinations"],
        )
        self.assertEqual(
            result["fully_scored_combinations"] + result["pruned_combinations"],
            result["evaluated_combinations"],
        )
        scores = [plan["deviation_score"] for plan in result["plans"]]
        self.assertEqual(scores, sorted(scores))

    def test_returns_all_exact_matches_sorted_by_price(self) -> None:
        # 三道测试菜任意两道都满足宽泛目标，结果应返回全部三个组合并按价格排序。
        items = [
            self._item("a", 10, energy_kcal=60),
            self._item("b", 20, energy_kcal=80),
            self._item("c", 5, energy_kcal=100),
        ]
        analysis = {
            "input": {
                "health_flags": {
                    "high_blood_glucose": False,
                    "high_blood_lipids": False,
                    "high_blood_pressure": False,
                }
            },
            "daily_targets": {
                "energy_kcal": {"min": 100, "max": 200},
                "protein_g": {"min": 10, "max": 20},
                "fat_g": {"min": 5, "max": 20},
                "carbohydrate_g": {"min": 10, "max": 40},
                "dietary_fiber_g": 2,
                "sodium_max_mg": 500,
                "added_sugar_max_g": 10,
            },
        }

        result = recommend_takeaway_plans(items, analysis)

        self.assertEqual(result["mode"], "exact")
        self.assertEqual(result["exact_match_count"], 3)
        self.assertEqual(
            [plan["total_price_yuan"] for plan in result["plans"]],
            [15, 25, 30],
        )

    def test_similar_expensive_item_is_removed_before_pairing(self) -> None:
        # 两道营养几乎相同的菜只保留便宜款，营养差异明显的第三道菜继续保留。
        cheap = self._item("cheap", 20, energy_kcal=500)
        expensive = self._item("expensive", 60, energy_kcal=505)
        different = self._item("different", 30, energy_kcal=700)

        retained, report = filter_similar_dishes([expensive, different, cheap])

        retained_ids = {item["id"] for item in retained}
        self.assertEqual(retained_ids, {"cheap", "different"})
        self.assertEqual(report["removed_count"], 1)
        self.assertEqual(report["removed_examples"][0]["kept_id"], "cheap")
        self.assertEqual(report["removed_examples"][0]["price_saving_yuan"], 40)

    def test_similar_equal_price_items_keep_only_one(self) -> None:
        # 营养和价格都相同的菜也只保留一条，按 ID 升序确定保留项。
        first = self._item("a-first", 20, energy_kcal=500)
        duplicate = self._item("b-duplicate", 20, energy_kcal=500)
        different = self._item("different", 30, energy_kcal=700)

        retained, report = filter_similar_dishes([duplicate, different, first])

        self.assertEqual({item["id"] for item in retained}, {"a-first", "different"})
        self.assertEqual(report["removed_count"], 1)
        self.assertEqual(report["removed_examples"][0]["price_saving_yuan"], 0)

    def test_same_dish_name_cannot_form_a_pair(self) -> None:
        # 即使营养差异较大而未被近似筛选删除，同名菜也不能同时作为午餐和晚餐。
        first = self._item("same-a", 20, energy_kcal=500, dish_name="同名套餐")
        second = self._item("same-b", 25, energy_kcal=700, dish_name="同名套餐")
        different = self._item("other", 30, energy_kcal=900, dish_name="其他套餐")

        result = recommend_takeaway_plans([first, second, different], self.analysis)

        self.assertEqual(result["candidate_filter"]["retained_count"], 3)
        self.assertEqual(result["same_name_pairs_skipped"], 1)
        self.assertEqual(result["evaluated_combinations"], 2)
        self.assertTrue(
            all(plan["lunch"]["dish_name"] != plan["dinner"]["dish_name"] for plan in result["plans"])
        )

    def test_breakfast_is_added_to_daily_totals(self) -> None:
        # 早餐营养应逐项加入午晚两餐，最终全天总量才用于偏离评分。
        breakfast = get_breakfast_preset("soy_egg_bread")
        result = recommend_takeaway_plans(
            self.items[:12],
            self.analysis,
            breakfast=breakfast,
        )
        first_plan = result["plans"][0]

        self.assertEqual(result["breakfast"]["id"], "soy_egg_bread")
        for nutrient, breakfast_value in breakfast["nutrition"].items():
            self.assertEqual(
                first_plan["daily_nutrition_totals"][nutrient],
                first_plan["meal_nutrition_totals"][nutrient] + breakfast_value,
            )

    def test_breakfast_presets_are_complete(self) -> None:
        # 七种选项包含“未吃早餐”和六种经典组合，且 ID 必须唯一。
        presets = list_breakfast_presets()

        self.assertEqual(len(presets), 7)
        self.assertEqual(len({preset["id"] for preset in presets}), 7)
        self.assertTrue(all("nutrition" in preset for preset in presets))

    @staticmethod
    def _item(
        item_id: str,
        price: float,
        energy_kcal: float = 60,
        dish_name: str | None = None,
    ) -> dict[str, object]:
        """创建一条营养值固定的最小测试菜品。"""

        return {
            "id": item_id,
            "platform": "meituan",
            "store_name": "测试商家",
            "dish_name": dish_name or f"测试菜品 {item_id}",
            "category": "测试",
            "price_yuan": price,
            "nutrition": {
                "energy_kcal": energy_kcal,
                "protein_g": 6,
                "fat_g": 3,
                "carbohydrate_g": 8,
                "fiber_g": 1.5,
                "sodium_mg": 100,
                "added_sugar_g": 1,
            },
        }


if __name__ == "__main__":
    unittest.main()
