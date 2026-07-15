from dataclasses import dataclass
from typing import Any


class NutritionInputError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class NutritionRequest:
    height_cm: float
    weight_kg: float
    age: int
    sex: str
    high_blood_glucose: bool = False
    high_blood_lipids: bool = False
    high_blood_pressure: bool = False

    def __post_init__(self) -> None:
        if not 100 <= self.height_cm <= 250:
            raise NutritionInputError("height_cm must be between 100 and 250")
        if not 25 <= self.weight_kg <= 300:
            raise NutritionInputError("weight_kg must be between 25 and 300")
        if not 18 <= self.age <= 100:
            raise NutritionInputError("age must be between 18 and 100")
        if self.sex not in {"male", "female"}:
            raise NutritionInputError("sex must be male or female")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NutritionRequest":
        try:
            return cls(
                height_cm=float(payload["height_cm"]),
                weight_kg=float(payload["weight_kg"]),
                age=int(payload["age"]),
                sex=str(payload["sex"]).lower(),
                high_blood_glucose=_boolean(payload.get("high_blood_glucose", False)),
                high_blood_lipids=_boolean(payload.get("high_blood_lipids", False)),
                high_blood_pressure=_boolean(payload.get("high_blood_pressure", False)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise NutritionInputError("height_cm, weight_kg, age, and sex are required") from exc


def calculate_daily_nutrition(request: NutritionRequest) -> dict[str, Any]:
    height_m = request.height_cm / 100
    bmi = request.weight_kg / height_m**2
    sex_constant = 5 if request.sex == "male" else -161
    basal_metabolic_rate = (
        10 * request.weight_kg + 6.25 * request.height_cm - 5 * request.age + sex_constant
    )
    energy_low = basal_metabolic_rate * 1.2
    energy_high = basal_metabolic_rate * 1.375
    energy_midpoint = (energy_low + energy_high) / 2
    carbohydrate_min_ratio = 0.45 if request.high_blood_glucose else 0.50
    carbohydrate_max_ratio = 0.50 if request.high_blood_glucose else 0.65
    fat_max_ratio = 0.25 if request.high_blood_lipids else 0.30
    sugar_max_ratio = 0.05 if request.high_blood_glucose else 0.10
    fiber_floor = 30 if request.sex == "male" else 25
    if request.high_blood_glucose or request.high_blood_lipids:
        fiber_floor = max(fiber_floor, 30)
    dietary_fiber = max(energy_midpoint / 1000 * 14, fiber_floor)

    return {
        "input": {
            "height_cm": round(request.height_cm, 1),
            "weight_kg": round(request.weight_kg, 1),
            "age": request.age,
            "sex": request.sex,
            "health_flags": {
                "high_blood_glucose": request.high_blood_glucose,
                "high_blood_lipids": request.high_blood_lipids,
                "high_blood_pressure": request.high_blood_pressure,
            },
        },
        "body": {
            "bmi": round(bmi, 1),
            "bmi_category": _bmi_category(bmi),
            "basal_metabolic_rate_kcal": round(basal_metabolic_rate),
            "healthy_weight_kg": {
                "min": round(18.5 * height_m**2, 1),
                "max": round(23.9 * height_m**2, 1),
            },
        },
        "daily_targets": {
            "energy_kcal": _range(energy_low, energy_high, 0),
            "protein_g": _range(request.weight_kg, request.weight_kg * 1.2, 1),
            "fat_g": _range(energy_low * 0.20 / 9, energy_high * fat_max_ratio / 9, 1),
            "saturated_fat_max_g": round(
                energy_midpoint * (0.07 if request.high_blood_lipids else 0.10) / 9,
                1,
            ),
            "carbohydrate_g": _range(
                energy_low * carbohydrate_min_ratio / 4,
                energy_high * carbohydrate_max_ratio / 4,
                1,
            ),
            "dietary_fiber_g": round(dietary_fiber, 1),
            "water_ml": _range(request.weight_kg * 30, request.weight_kg * 35, 0),
            "sodium_max_mg": 1500 if request.high_blood_pressure else 2000,
            "added_sugar_max_g": round(energy_midpoint * sugar_max_ratio / 4, 1),
        },
        "basis": {
            "energy": "Mifflin-St Jeor BMR, sedentary to lightly active range",
            "protein": "1.0-1.2 g per kg body weight",
            "fat": f"20%-{round(fat_max_ratio * 100)}% of daily energy",
            "carbohydrate": (
                f"{round(carbohydrate_min_ratio * 100)}%-"
                f"{round(carbohydrate_max_ratio * 100)}% of daily energy"
            ),
            "dietary_fiber": "14 g per 1000 kcal with an adult minimum target",
            "water": "30-35 ml per kg body weight",
        },
        "notice": (
            "General adult estimate, not a diagnosis or treatment plan. If any health flag "
            "is selected, confirm targets with a doctor or registered dietitian."
        ),
    }


def _bmi_category(bmi: float) -> str:
    if bmi < 18.5:
        return "underweight"
    if bmi < 24:
        return "healthy"
    if bmi < 28:
        return "overweight"
    return "obesity"


def _range(minimum: float, maximum: float, digits: int) -> dict[str, float | int]:
    return {
        "min": round(minimum, digits),
        "max": round(maximum, digits),
    }


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    raise NutritionInputError("health flags must be boolean values")
