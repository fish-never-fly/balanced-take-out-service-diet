import unittest
from pathlib import Path

from app.menu_catalog import MenuCatalog
from app.nutrition import NutritionInputError, NutritionRequest, calculate_daily_nutrition


class NutritionTest(unittest.TestCase):
    def test_calculates_daily_targets(self) -> None:
        result = calculate_daily_nutrition(
            NutritionRequest(height_cm=170, weight_kg=65, age=30, sex="female")
        )

        self.assertEqual(result["body"]["bmi"], 22.5)
        self.assertEqual(result["body"]["bmi_category"], "healthy")
        self.assertEqual(result["body"]["basal_metabolic_rate_kcal"], 1402)
        self.assertEqual(result["daily_targets"]["energy_kcal"], {"min": 1682.0, "max": 1927.0})

    def test_health_flags_tighten_relevant_targets(self) -> None:
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
        with self.assertRaises(NutritionInputError):
            NutritionRequest(height_cm=80, weight_kg=65, age=30, sex="female")


class MenuCatalogTest(unittest.TestCase):
    def setUp(self) -> None:
        file_path = Path(__file__).resolve().parent.parent / "examples" / "nutrition_menu.json"
        self.catalog = MenuCatalog(file_path)

    def test_loads_complete_synthetic_menu(self) -> None:
        items = self.catalog.load()

        self.assertEqual(len(items), 24)
        self.assertEqual(len({item["id"] for item in items}), 24)

    def test_filters_menu_by_platform_and_price(self) -> None:
        items = self.catalog.query(platform="meituan", max_price_yuan=30)

        self.assertTrue(items)
        self.assertTrue(all(item["platform"] == "meituan" for item in items))
        self.assertTrue(all(item["price_yuan"] <= 30 for item in items))


if __name__ == "__main__":
    unittest.main()
