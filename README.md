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
POST /recommendations
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

## 两餐外卖推荐

`POST /recommendations` 接收与 `/nutrition` 相同的身体信息。程序从模拟菜单中
穷举两道不同菜品，分别作为午餐和晚餐，并将两餐营养总和与每日目标比较。

完全满足热量、蛋白质、脂肪、碳水、纤维、钠和添加糖条件时，接口返回全部
满足条件的组合并按总价格升序排列。如果没有完全满足的组合，则按照热量、
蛋白质、脂肪、碳水、纤维、钠和添加糖的重要程度加权，计算：

```text
单项加权偏离 = 偏离比例 × 营养权值
组合偏离系数 = 所有单项加权偏离之和
```

最终返回组合偏离系数最小的三个方案。高血糖会提高碳水和添加糖权重，
高血脂会提高脂肪权重，高血压会提高钠权重。

模拟菜单位于 `examples/nutrition_menu.json`，包含 44 道菜品及每份价格、热量、蛋白质、脂肪、碳水、膳食纤维、钠和添加糖。数据仅用于测试。

## 测试

```powershell
python -m unittest discover -s tests -v
```
