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
GET /breakfast-presets
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
  "breakfast_id": "soy_egg_bread",
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

在穷举午餐和晚餐组合前，程序会先按价格从低到高、ID 从小到大筛选菜品。
如果某道菜与已保留菜在热量、蛋白质、脂肪、碳水、纤维、钠和添加糖上的相对
差异均不超过 12%，则认为属于同一营养近似组，该组只保留一道：最低价优先，
同价时保留 ID 更小的菜。接口会返回筛选前数量、保留数量、删除数量和部分替代
示例。生成两餐组合时还会跳过菜名相同的组合，避免午餐和晚餐重复选择同名菜。

### 性能优化

- 菜单文件按修改时间缓存，文件未变化时不重复解析和校验 JSON。
- 营养值在组合搜索前转换为固定顺序数值元组，减少字典查询。
- 无精确解时只流式保留偏离最小的三组，不保存全部组合详情。
- 精确解只保存真正满足全部条件的组合，仍可完整按价格排序返回。
- 营养近似筛选使用热量对数桶，只比较可能落入 12% 阈值的候选。
- 使用热量偏离作为总偏离下界，对不可能进入结果的组合执行安全剪枝。

推荐响应中的 `evaluated_combinations`、`fully_scored_combinations` 和
`pruned_combinations` 可用于观察组合总数、完整评分数量和剪枝数量。

## 早餐影响

页面提供七种早餐选项：未吃早餐，以及豆浆鸡蛋全麦面包、牛奶燕麦香蕉、
小米粥肉包鸡蛋、豆腐脑油条、鸡蛋鸡肉三明治牛奶、红薯鸡蛋牛奶六种经典组合。

每套早餐都包含明确的份量假设和每份营养估算。推荐算法使用：

```text
全天营养摄入 = 早餐估算摄入 + 午餐营养 + 晚餐营养
```

然后将全天总量与原始每日目标比较。这样早餐已经摄入的蛋白质会降低午晚餐的
补充压力，早餐中过多的脂肪、钠或添加糖也会直接影响推荐评分。早餐数据为工程
估算，实际值会随食品品牌、份量和烹饪方式变化。

模拟菜单位于 `examples/nutrition_menu.json`，包含 160 道菜品及每份价格、热量、蛋白质、脂肪、碳水、膳食纤维、钠和添加糖。数据仅用于测试。

其中 29 个 `comparison_group` 各包含四个营养含量相近的价格档位，最高价约为
最低价的 2.6 倍，可用于验证推荐算法在营养接近时是否正确考虑价格。重新生成数据：

```powershell
python generate_menu_data.py
```

## 测试

```powershell
python -m unittest discover -s tests -v
```
