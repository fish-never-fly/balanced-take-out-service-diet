# 营养需求分析程序

程序根据成年人的身高、体重、年龄、性别、活动水平和三高情况，估算每日热量与主要营养物质需求，并保留一组模拟外卖菜单供后续推荐算法使用。

已移除附近外卖采集、平台 JSON 导入、商家数据库和商家查询功能。

## 启动

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\uvicorn app.main:app --reload
```

打开 `http://127.0.0.1:8000/` 使用网页，或打开 `http://127.0.0.1:8000/docs` 查看接口文档。

## 接口

```text
POST /nutrition
GET /menu-items
GET /menu-items?platform=meituan&max_price_yuan=30
GET /menu-items?category=沙拉
GET /health
```

营养计算示例：

```json
{
  "height_cm": 170,
  "weight_kg": 65,
  "age": 30,
  "sex": "female",
  "activity_level": "moderate",
  "high_blood_glucose": false,
  "high_blood_lipids": false,
  "high_blood_pressure": false
}
```

`activity_level` 支持 `sedentary`（久坐）、`moderate`（适量运动）和
`vigorous`（剧烈运动）。程序分别使用 1.2、1.55 和 1.725 活动系数，
并以估算每日总消耗上下 5% 作为热量参考范围。

模拟菜单位于 `examples/nutrition_menu.json`，包含 44 道菜品及每份价格、热量、蛋白质、脂肪、碳水、膳食纤维、钠和添加糖。数据仅用于测试。

## 测试

```powershell
python -m unittest discover -s tests -v
```
