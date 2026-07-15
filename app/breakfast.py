"""经典早餐组合及其每份营养估算。

所有数据用于推荐算法模拟。天然存在于牛奶、水果中的糖不计入 added_sugar_g，
只有额外加入食品的糖计入添加糖。实际营养值会因品牌、份量和烹饪方式变化。
"""

from copy import deepcopy
from typing import Any


# 每套早餐都使用与模拟外卖菜单相同的营养字段，便于直接累加全天摄入。
BREAKFAST_PRESETS: tuple[dict[str, Any], ...] = (
    {
        "id": "none",
        "name": "未吃早餐",
        "serving_description": "不计入任何早餐摄入",
        "nutrition": {
            "energy_kcal": 0,
            "protein_g": 0,
            "fat_g": 0,
            "carbohydrate_g": 0,
            "fiber_g": 0,
            "sodium_mg": 0,
            "added_sugar_g": 0,
        },
    },
    {
        "id": "soy_egg_bread",
        "name": "无糖豆浆＋鸡蛋＋全麦面包",
        "serving_description": "无糖豆浆 300ml、煮鸡蛋 1 个、全麦面包 2 片",
        "nutrition": {
            "energy_kcal": 380,
            "protein_g": 22,
            "fat_g": 13,
            "carbohydrate_g": 46,
            "fiber_g": 5,
            "sodium_mg": 480,
            "added_sugar_g": 4,
        },
    },
    {
        "id": "milk_oat_banana",
        "name": "牛奶燕麦香蕉",
        "serving_description": "纯牛奶 250ml、原味燕麦 50g、香蕉 1 根",
        "nutrition": {
            "energy_kcal": 430,
            "protein_g": 17,
            "fat_g": 11,
            "carbohydrate_g": 68,
            "fiber_g": 9,
            "sodium_mg": 160,
            "added_sugar_g": 0,
        },
    },
    {
        "id": "congee_bun_egg",
        "name": "小米粥＋肉包＋鸡蛋",
        "serving_description": "小米粥 300g、肉包 1 个、煮鸡蛋 1 个",
        "nutrition": {
            "energy_kcal": 540,
            "protein_g": 22,
            "fat_g": 16,
            "carbohydrate_g": 78,
            "fiber_g": 4,
            "sodium_mg": 850,
            "added_sugar_g": 3,
        },
    },
    {
        "id": "tofu_youtiao",
        "name": "豆腐脑＋油条",
        "serving_description": "咸豆腐脑 1 碗、普通油条 1 根",
        "nutrition": {
            "energy_kcal": 620,
            "protein_g": 20,
            "fat_g": 31,
            "carbohydrate_g": 66,
            "fiber_g": 4,
            "sodium_mg": 1250,
            "added_sugar_g": 5,
        },
    },
    {
        "id": "sandwich_milk",
        "name": "鸡蛋鸡肉三明治＋牛奶",
        "serving_description": "鸡蛋鸡肉全麦三明治 1 份、纯牛奶 250ml",
        "nutrition": {
            "energy_kcal": 560,
            "protein_g": 27,
            "fat_g": 21,
            "carbohydrate_g": 65,
            "fiber_g": 6,
            "sodium_mg": 900,
            "added_sugar_g": 7,
        },
    },
    {
        "id": "sweet_potato_egg_milk",
        "name": "红薯＋鸡蛋＋牛奶",
        "serving_description": "蒸红薯 250g、煮鸡蛋 1 个、纯牛奶 250ml",
        "nutrition": {
            "energy_kcal": 450,
            "protein_g": 22,
            "fat_g": 13,
            "carbohydrate_g": 61,
            "fiber_g": 8,
            "sodium_mg": 250,
            "added_sugar_g": 0,
        },
    },
)


class BreakfastPresetError(ValueError):
    """表示客户端提交了不存在的早餐组合 ID。"""

    pass


def list_breakfast_presets() -> list[dict[str, Any]]:
    """返回早餐组合副本，防止调用方修改模块中的原始常量。"""

    return deepcopy(list(BREAKFAST_PRESETS))


def get_breakfast_preset(preset_id: str) -> dict[str, Any]:
    """按 ID 查找一套早餐组合，不存在时抛出输入异常。"""

    for preset in BREAKFAST_PRESETS:
        if preset["id"] == preset_id:
            return deepcopy(preset)
    raise BreakfastPresetError(f"unknown breakfast preset: {preset_id}")
