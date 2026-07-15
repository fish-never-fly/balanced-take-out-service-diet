"""身体信息校验与每日营养需求估算。

计算结果面向健康成年人，并根据高血糖、高血脂和高血压标记适当收紧部分上限。
这些结果用于一般饮食规划和程序测试，不能替代医生诊断或个体化营养处方。
"""

from dataclasses import dataclass
from typing import Any


# 活动系数用于把基础代谢率换算为每日总能量消耗。
# 久坐表示很少运动，适量运动表示规律的中等强度运动，剧烈运动表示高频高强度训练。
ACTIVITY_FACTORS: dict[str, float] = {
    "sedentary": 1.2,
    "moderate": 1.55,
    "vigorous": 1.725,
}


class NutritionInputError(ValueError):
    """表示身体信息缺失、类型错误或超出程序支持范围。"""

    pass


@dataclass(frozen=True, slots=True)
class NutritionRequest:
    """保存一次营养分析需要的标准化输入。

    frozen=True 防止计算过程中意外修改用户输入；slots=True 减少实例开销并限制属性集合。
    三个健康字段是布尔值，未提供时按没有对应健康问题处理。
    """

    # 身高、体重、年龄和公式中的生理性别用于计算 BMI 与基础代谢。
    height_cm: float
    weight_kg: float
    age: int
    sex: str
    activity_level: str = "sedentary"

    # 健康标记用于调整碳水、脂肪、糖、纤维和钠的推荐范围。
    high_blood_glucose: bool = False
    high_blood_lipids: bool = False
    high_blood_pressure: bool = False

    def __post_init__(self) -> None:
        """在对象创建后检查数值范围和性别枚举。"""

        # 当前公式只面向成年人，并设置合理的工程边界以拦截明显录入错误。
        if not 100 <= self.height_cm <= 250:
            raise NutritionInputError("height_cm must be between 100 and 250")
        if not 25 <= self.weight_kg <= 300:
            raise NutritionInputError("weight_kg must be between 25 and 300")
        if not 18 <= self.age <= 100:
            raise NutritionInputError("age must be between 18 and 100")
        if self.sex not in {"male", "female"}:
            raise NutritionInputError("sex must be male or female")
        if self.activity_level not in ACTIVITY_FACTORS:
            raise NutritionInputError("activity_level must be sedentary, moderate, or vigorous")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NutritionRequest":
        """把接口收到的 JSON 字典转换为经过校验的请求对象。"""

        # 所有入口都复用这一转换过程，避免网页、接口测试和未来客户端采用不同规则。
        try:
            return cls(
                height_cm=float(payload["height_cm"]),
                weight_kg=float(payload["weight_kg"]),
                age=int(payload["age"]),
                sex=str(payload["sex"]).lower(),
                activity_level=str(payload.get("activity_level", "sedentary")).lower(),
                high_blood_glucose=_boolean(payload.get("high_blood_glucose", False)),
                high_blood_lipids=_boolean(payload.get("high_blood_lipids", False)),
                high_blood_pressure=_boolean(payload.get("high_blood_pressure", False)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            # 隐藏底层转换异常细节，向调用方返回稳定、可理解的输入提示。
            raise NutritionInputError("height_cm, weight_kg, age, and sex are required") from exc


def calculate_daily_nutrition(request: NutritionRequest) -> dict[str, Any]:
    """根据标准化身体信息计算每日营养摄入参考范围。

    返回值分为 input、body、daily_targets、basis 和 notice，分别用于回显输入、
    展示身体指标、提供每日目标、说明计算依据以及提示适用范围。
    """

    # 将厘米转换为米后计算 BMI；BMI 同时用于分类和健康体重区间展示。
    height_m = request.height_cm / 100
    bmi = request.weight_kg / height_m**2

    # 使用 Mifflin-St Jeor 公式估算基础代谢率。公式中的常数因生理性别不同，
    # 男性使用 +5，女性使用 -161，这是当前公式要求的二分类输入。
    sex_constant = 5 if request.sex == "male" else -161
    basal_metabolic_rate = (
        10 * request.weight_kg + 6.25 * request.height_cm - 5 * request.age + sex_constant
    )
    # 根据用户选择的活动水平，把基础代谢率换算为每日总能量消耗中心值。
    # 由于公式、运动量和个体代谢都存在误差，最终目标用中心值上下 5% 表示合理区间。
    activity_factor = ACTIVITY_FACTORS[request.activity_level]
    estimated_daily_expenditure = basal_metabolic_rate * activity_factor
    energy_low = estimated_daily_expenditure * 0.95
    energy_high = estimated_daily_expenditure * 1.05
    energy_midpoint = (energy_low + energy_high) / 2

    # 根据健康标记调整宏量营养素供能比例：高血糖时缩小碳水比例并降低添加糖，
    # 高血脂时降低脂肪比例上限；未勾选时采用一般成年人的宽泛参考范围。
    carbohydrate_min_ratio = 0.45 if request.high_blood_glucose else 0.50
    carbohydrate_max_ratio = 0.50 if request.high_blood_glucose else 0.65
    fat_max_ratio = 0.25 if request.high_blood_lipids else 0.30
    sugar_max_ratio = 0.05 if request.high_blood_glucose else 0.10
    # 膳食纤维先按性别设置最低目标；高血糖或高血脂时将最低值提高到 30 克。
    fiber_floor = 30 if request.sex == "male" else 25
    if request.high_blood_glucose or request.high_blood_lipids:
        fiber_floor = max(fiber_floor, 30)
    dietary_fiber = max(energy_midpoint / 1000 * 14, fiber_floor)

    # 以结构化字典返回结果，便于网页直接展示，也便于后续推荐算法读取目标值。
    return {
        "input": {
            # 回显规范化后的输入，方便客户端确认本次计算采用了哪些条件。
            "height_cm": round(request.height_cm, 1),
            "weight_kg": round(request.weight_kg, 1),
            "age": request.age,
            "sex": request.sex,
            "activity_level": request.activity_level,
            "health_flags": {
                "high_blood_glucose": request.high_blood_glucose,
                "high_blood_lipids": request.high_blood_lipids,
                "high_blood_pressure": request.high_blood_pressure,
            },
        },
        "body": {
            # 身体指标包含 BMI、BMI 分类、基础代谢和中国成人健康体重区间。
            "bmi": round(bmi, 1),
            "bmi_category": _bmi_category(bmi),
            "basal_metabolic_rate_kcal": round(basal_metabolic_rate),
            "activity_factor": activity_factor,
            "estimated_daily_expenditure_kcal": round(estimated_daily_expenditure),
            "healthy_weight_kg": {
                "min": round(18.5 * height_m**2, 1),
                "max": round(23.9 * height_m**2, 1),
            },
        },
        "daily_targets": {
            # 热量及主要营养素统一按“每人每日”输出；范围字段包含 min 和 max。
            "energy_kcal": _range(energy_low, energy_high, 0),

            # 蛋白质按每千克体重 1.0 至 1.2 克估算。
            "protein_g": _range(request.weight_kg, request.weight_kg * 1.2, 1),

            # 脂肪和饱和脂肪先按热量比例计算，再用每克脂肪 9 千卡换算成克数。
            "fat_g": _range(energy_low * 0.20 / 9, energy_high * fat_max_ratio / 9, 1),
            "saturated_fat_max_g": round(
                energy_midpoint * (0.07 if request.high_blood_lipids else 0.10) / 9,
                1,
            ),
            # 碳水化合物按供能比例计算，并用每克碳水 4 千卡换算成克数。
            "carbohydrate_g": _range(
                energy_low * carbohydrate_min_ratio / 4,
                energy_high * carbohydrate_max_ratio / 4,
                1,
            ),
            # 纤维取“每 1000 千卡 14 克”与前述最低目标中的较大值。
            "dietary_fiber_g": round(dietary_fiber, 1),

            # 饮水量按每千克体重 30 至 35 毫升估算；高血压时收紧钠上限。
            "water_ml": _range(request.weight_kg * 30, request.weight_kg * 35, 0),
            "sodium_max_mg": 1500 if request.high_blood_pressure else 2000,

            # 添加糖使用热量中点换算，高血糖时从不超过 10% 收紧为不超过 5%。
            "added_sugar_max_g": round(energy_midpoint * sugar_max_ratio / 4, 1),
        },
        "basis": {
            # 将主要计算依据随结果返回，便于前端解释数值来源和后续审计。
            "energy": (
                "Mifflin-St Jeor BMR multiplied by the selected activity factor, "
                "shown with a 5% estimation margin"
            ),
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
            # 明确本程序的适用边界，避免将一般估算误解为医疗方案。
            "General adult estimate, not a diagnosis or treatment plan. If any health flag "
            "is selected, confirm targets with a doctor or registered dietitian."
        ),
    }


def _bmi_category(bmi: float) -> str:
    """按照中国成人常用 BMI 界值返回英文分类标识。"""

    # 分类标识保持英文，便于接口调用方稳定处理；网页可按需翻译显示。
    if bmi < 18.5:
        return "underweight"
    if bmi < 24:
        return "healthy"
    if bmi < 28:
        return "overweight"
    return "obesity"


def _range(minimum: float, maximum: float, digits: int) -> dict[str, float | int]:
    """把两个数值格式化为统一的 min/max 区间对象。"""

    # digits 控制小数位：热量和饮水量取整数，克数通常保留一位小数。
    return {
        "min": round(minimum, digits),
        "max": round(maximum, digits),
    }


def _boolean(value: Any) -> bool:
    """严格解析健康标记，只接受布尔值或数值 0/1。"""

    # 不接受 "false" 等非空字符串，因为 Python 会把非空字符串视为真，容易产生误判。
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    raise NutritionInputError("health flags must be boolean values")
