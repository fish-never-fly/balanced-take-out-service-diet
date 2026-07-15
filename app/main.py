"""FastAPI 应用入口。

本模块只负责三件事：提供静态首页、接收身体信息并返回营养分析结果、
读取并查询本地模拟外卖数据。程序不会访问任何真实外卖平台。
"""

import os
from pathlib import Path
from typing import Any

# FastAPI 负责 HTTP 路由、参数校验和错误响应，HTMLResponse 用于返回首页文件。
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

# 菜单模块负责模拟数据读取，营养模块负责身体信息校验和营养公式计算。
from .breakfast import BreakfastPresetError, get_breakfast_preset, list_breakfast_presets
from .menu_catalog import MenuCatalog
from .nutrition import NutritionInputError, NutritionRequest, calculate_daily_nutrition
from .recommendation import RecommendationError, recommend_takeaway_plans


# 创建 Web 应用实例；标题和版本会显示在 /docs 自动接口文档中。
app = FastAPI(title="Nutrition Analysis Service", version="1.5.0")

# 默认读取项目内置的模拟菜单。部署或测试时可通过环境变量替换数据文件，
# 从而不必修改源代码即可使用另一份相同结构的 JSON。
menu_catalog = MenuCatalog(
    os.getenv(
        "NUTRITION_MENU_FILE",
        str(Path(__file__).resolve().parent.parent / "examples" / "nutrition_menu.json"),
    )
)

# 服务启动时读取首页文本，后续访问根路径时可以直接返回，不必重复读取磁盘。
INDEX_HTML = (Path(__file__).resolve().parent / "static" / "index.html").read_text(encoding="utf-8")


# 返回单页 Web 界面，其中包含身体信息表单、营养结果和模拟菜单预览。
@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """返回应用首页。"""
    return INDEX_HTML


# 健康检查接口用于确认服务进程是否正常响应，不执行营养计算或文件读取。
@app.get("/health")
def health() -> dict[str, str]:
    """返回固定状态，供部署环境或人工检查使用。"""
    return {"status": "ok"}


# 营养分析接口接收 JSON 身体信息，并返回统一结构的每日营养目标。
@app.post("/nutrition")
def nutrition(payload: dict[str, Any]) -> dict[str, Any]:
    """校验用户身体信息并计算每日营养摄入参考值。"""

    # 先把松散的 JSON 字典转换为 NutritionRequest，确保字段类型和范围有效。
    # 如果输入不合法，则将业务层异常转换为前端容易识别的 HTTP 422 响应。
    try:
        request = NutritionRequest.from_dict(payload)
    except NutritionInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return calculate_daily_nutrition(request)


# 推荐接口复用身体信息计算结果，并从全部模拟菜品中寻找两餐组合。
@app.post("/recommendations")
def recommendations(payload: dict[str, Any]) -> dict[str, Any]:
    """返回营养分析结果以及午餐、晚餐外卖推荐组合。"""

    try:
        request = NutritionRequest.from_dict(payload)
        breakfast = get_breakfast_preset(str(payload.get("breakfast_id", "none")))
        nutrition_analysis = calculate_daily_nutrition(request)
        recommendation = recommend_takeaway_plans(
            menu_catalog.load(),
            nutrition_analysis,
            breakfast=breakfast,
        )
    except (BreakfastPresetError, NutritionInputError, RecommendationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"nutrition": nutrition_analysis, "recommendation": recommendation}


# 早餐组合接口供页面生成下拉选项，所有数值都是每份经典搭配的工程估算。
@app.get("/breakfast-presets")
def breakfast_presets() -> list[dict[str, Any]]:
    """返回可选择的经典早餐组合及估算营养值。"""

    return list_breakfast_presets()


# 模拟菜单查询接口支持按平台、分类、最高价格和返回数量筛选。
@app.get("/menu-items")
def list_menu_items(
    platform: str | None = Query(default=None, pattern="^(meituan|eleme|jd)$"),
    category: str | None = None,
    max_price_yuan: float | None = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict[str, Any]]:
    """返回经过可选条件筛选的模拟菜品列表。"""

    # 这里只查询本地 JSON 中的模拟数据，不会连接、抓取或调用任何外卖平台。
    return menu_catalog.query(
        platform=platform,
        category=category,
        max_price_yuan=max_price_yuan,
        limit=limit,
    )
