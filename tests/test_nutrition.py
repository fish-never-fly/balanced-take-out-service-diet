"""营养计算和模拟菜单的回归测试。"""

import unittest
from pathlib import Path

from app.menu_catalog import MenuCatalog
from app.nutrition import NutritionInputError, NutritionRequest, calculate_daily_nutrition
from app.recommendation import recommend_takeaway_plans


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
        # 数据集应包含 44 道菜，并且每个 ID 必须唯一。
        items = self.catalog.load()

        self.assertEqual(len(items), 44)
        self.assertEqual(len({item["id"] for item in items}), 44)

    def test_filters_menu_by_platform_and_price(self) -> None:
        # 组合筛选后，每条结果都必须同时满足平台和最高价格条件。
        items = self.catalog.query(platform="meituan", max_price_yuan=30)

        self.assertTrue(items)
        self.assertTrue(all(item["platform"] == "meituan" for item in items))
        self.assertTrue(all(item["price_yuan"] <= 30 for item in items))


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
        # 当前 44 道模拟菜品没有两餐组合同时满足全部每日目标，因此应返回前三名。
        result = recommend_takeaway_plans(self.items, self.analysis)

        self.assertEqual(result["mode"], "closest")
        self.assertEqual(result["evaluated_combinations"], 946)
        self.assertEqual(len(result["plans"]), 3)
        scores = [plan["deviation_score"] for plan in result["plans"]]
        self.assertEqual(scores, sorted(scores))

    def test_returns_all_exact_matches_sorted_by_price(self) -> None:
        # 三道测试菜任意两道都满足宽泛目标，结果应返回全部三个组合并按价格排序。
        items = [
            self._item("a", 10),
            self._item("b", 20),
            self._item("c", 5),
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

    @staticmethod
    def _item(item_id: str, price: float) -> dict[str, object]:
        """创建一条营养值固定的最小测试菜品。"""

        return {
            "id": item_id,
            "platform": "meituan",
            "store_name": "测试商家",
            "dish_name": f"测试菜品 {item_id}",
            "category": "测试",
            "price_yuan": price,
            "nutrition": {
                "energy_kcal": 60,
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
