# 营养分析与外卖搭配推荐系统

这是一个基于 FastAPI 的营养分析与模拟外卖推荐程序。系统根据用户的身高、体重、年龄、性别、活动水平及“三高”情况，估算每日营养摄入目标；再结合早餐摄入、午晚餐预算和本地模拟菜单，推荐适合作为午餐与晚餐的两餐组合。

项目内置美团、饿了么、京东三个平台的**模拟菜品与商家数据**，并可通过浏览器定位功能模拟查询当前位置附近的商家。程序不会连接、调用或抓取任何真实外卖平台。

## 主要功能

- 根据身体信息计算 BMI、基础代谢率和每日总能量消耗。
- 估算每日热量、蛋白质、脂肪、碳水、膳食纤维、水、钠和添加糖目标。
- 支持久坐、适量运动、剧烈运动三种活动水平。
- 根据高血糖、高血脂、高血压标记调整营养目标与推荐权重。
- 提供七种经典早餐选项，将早餐估算摄入计入全天营养总量。
- 从 420 道模拟菜品中选择午餐和晚餐，并分别展示两餐营养含量。
- 午餐优先安排热量、复合碳水和蛋白质相对更高的菜品。
- 支持午晚餐总预算上限，自动排除超出预算的组合。
- 自动去除营养相近但价格更高的菜品，降低搜索量和推荐价格。
- 最多展示 10 种满足目标的组合；不足 3 种时以偏离最小的方案补足。
- 模拟美团、饿了么、京东三平台菜品查询和当前位置附近商家查询。

## 项目结构

```text
takeaway-importer/
├─ app/
│  ├─ main.py                 # FastAPI 应用入口与接口路由
│  ├─ nutrition.py            # 身体信息校验和每日营养目标计算
│  ├─ breakfast.py            # 经典早餐组合及营养估算
│  ├─ recommendation.py       # 相似菜筛选与午晚餐组合推荐
│  ├─ menu_catalog.py         # 模拟菜单读取、缓存和查询
│  ├─ nearby.py               # 多平台附近商家位置模拟
│  └─ static/index.html       # 中文网页界面
├─ examples/
│  ├─ nutrition_menu.json     # 420 道模拟菜品数据
│  └─ nutrition_menu.txt      # 便于人工查看的文本版菜单
├─ tests/                     # 单元测试
├─ generate_menu_data.py      # 重新生成模拟菜单
├─ export_menu_txt.py         # 将 JSON 菜单导出为 TXT
├─ requirements.txt           # Python 依赖
└─ README.md
```

## 环境要求

- Python 3.10 或更高版本
- 支持现代 JavaScript 和 Geolocation API 的浏览器

## 安装与启动

在项目根目录运行：

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\uvicorn app.main:app --reload
```

启动后访问：

- 网页界面：`http://127.0.0.1:8000/`
- Swagger 接口文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`

不要直接通过 `file://` 打开 `app/static/index.html`。浏览器定位通常只允许在 `localhost` 或 HTTPS 环境中运行，直接打开本地文件也可能导致接口请求失败。

## 网页使用流程

1. 输入身高、体重、年龄和性别。
2. 选择久坐、适量运动或剧烈运动。
3. 根据实际情况选择是否有高血糖、高血脂或高血压。
4. 选择已经吃过的早餐组合。
5. 输入午餐与晚餐的总预算上限。
6. 提交后查看每日营养目标及推荐的午晚餐组合。
7. 如需体验定位模拟，点击获取当前位置按钮并允许浏览器访问位置。

## 营养计算说明

### 输入范围

| 字段 | 含义 | 支持范围 |
| --- | --- | --- |
| `height_cm` | 身高，厘米 | 100–250 |
| `weight_kg` | 体重，千克 | 25–300 |
| `age` | 年龄 | 18–100 |
| `sex` | 生理性别 | `male`、`female` |
| `activity_level` | 活动水平 | `sedentary`、`moderate`、`vigorous` |
| `high_blood_glucose` | 是否高血糖 | 布尔值 |
| `high_blood_lipids` | 是否高血脂 | 布尔值 |
| `high_blood_pressure` | 是否高血压 | 布尔值 |

活动系数如下：

| 活动水平 | 标识 | 系数 |
| --- | --- | --- |
| 久坐 | `sedentary` | 1.2 |
| 适量运动 | `moderate` | 1.55 |
| 剧烈运动 | `vigorous` | 1.725 |

程序使用 Mifflin-St Jeor 公式估算基础代谢率，再乘以活动系数得到每日总能量消耗，并将上下浮动 5% 作为热量参考范围。蛋白质、脂肪、碳水、纤维、水、钠和添加糖目标根据体重、热量及健康标记进一步计算。

### 营养分析接口

`POST /nutrition`

请求示例：

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

响应包含：

- `input`：规范化后的用户输入。
- `body`：BMI、BMI 分类、基础代谢率、活动系数、每日消耗和健康体重范围。
- `daily_targets`：各类营养物质的每日目标或上限。
- `basis`：主要计算依据。
- `notice`：适用范围与健康提示。

## 早餐影响

`GET /breakfast-presets` 返回七种早餐选项：

1. 未吃早餐。
2. 无糖豆浆＋鸡蛋＋全麦面包。
3. 牛奶燕麦香蕉。
4. 小米粥＋肉包＋鸡蛋。
5. 豆腐脑＋油条。
6. 鸡蛋鸡肉三明治＋牛奶。
7. 红薯＋鸡蛋＋牛奶。

每种早餐都包含固定份量假设及工程估算营养值。推荐算法按以下方式评价全天摄入：

```text
全天营养摄入 = 早餐估算摄入 + 午餐营养 + 晚餐营养
```

因此早餐中已经摄入的蛋白质、脂肪、碳水、钠和糖都会直接影响午晚餐推荐，而不是简单按固定比例扣减需求。

## 午晚餐推荐

### 推荐接口

`POST /recommendations`

该接口在身体信息之外接收：

- `breakfast_id`：早餐组合 ID，默认 `none`。
- `budget_yuan`：午餐与晚餐的总预算，不包含早餐；不传时不限制预算。

请求示例：

```json
{
  "height_cm": 170,
  "weight_kg": 65,
  "age": 30,
  "sex": "female",
  "activity_level": "moderate",
  "high_blood_glucose": false,
  "high_blood_lipids": false,
  "high_blood_pressure": false,
  "breakfast_id": "soy_egg_bread",
  "budget_yuan": 80
}
```

如果没有任何两菜组合满足预算，接口返回 HTTP 422。

### 相似菜品筛选

搜索组合前，程序先按价格从低到高、ID 从小到大检查菜品。两道菜在以下五项营养上的相对差异都不超过 10% 时，被视为营养相似：

- 热量
- 蛋白质
- 脂肪
- 碳水
- 膳食纤维

每组相似菜只保留价格最低的一道；同价时保留 ID 更小的一道。钠和添加糖不参与相似菜判断，但仍参与最终组合评分。同名菜也不能同时作为午餐和晚餐。

### 午餐与晚餐顺序

对于同一组两道菜，程序计算午餐优先分，得分更高的菜安排为午餐：

```text
午餐优先分 = 热量得分 × 40% + 复合碳水得分 × 35% + 蛋白质得分 × 25%
估算复合碳水 = 总碳水 - 添加糖
```

各项得分会使用用户对应的每日营养目标中点归一化。该设计使午餐倾向于选择高热量、高复合碳水和高蛋白质菜品。

### 组合选择规则

1. 排除总价超过 `budget_yuan` 的组合。
2. 排除午晚餐菜名相同的组合。
3. 将早餐、午餐和晚餐营养相加，与全天目标比较。
4. 满足全部营养条件的精确组合按总价升序排列，最多返回价格最低的 10 种。
5. 精确组合仅有 1–2 种时，使用偏离最小的非精确组合补足至 3 种。
6. 没有精确组合时，返回偏离程度最小的 3 种。

非精确组合采用加权偏离评分：

```text
单项偏离系数 = 偏离比例 × 营养权重
组合偏离系数 = 各营养物质单项偏离系数之和
```

高血糖会提高碳水和添加糖权重，高血脂会提高脂肪权重，高血压会提高钠权重。偏离系数越小，方案越接近用户的全天营养目标。

响应中的常用统计字段包括：

- `exact_match_count`：所有精确匹配组合数量。
- `returned_exact_count`：本次实际返回的精确组合数量。
- `supplemented_count`：用于补足结果的偏离组合数量。
- `result_limit`：精确组合最大展示数量。
- `evaluated_combinations`：经过基础条件检查的组合数量。
- `fully_scored_combinations`：完成全部偏离计算的组合数量。
- `pruned_combinations`：被安全剪枝跳过的组合数量。

每个推荐结果分别提供午餐、晚餐及两餐总计的价格和营养数据。

## 多平台与定位模拟

### 平台统计

`GET /platforms`

返回 `meituan`、`eleme`、`jd` 三个平台在当前模拟数据中的菜品数和商家数。默认数据中每个平台有 140 道菜品、43 家模拟商家。

### 模拟附近商家

`POST /nearby-stores`

请求示例：

```json
{
  "latitude": 31.2304,
  "longitude": 121.4737,
  "radius_m": 3000,
  "platforms": ["meituan", "eleme", "jd"],
  "store_limit": 30,
  "items_per_store": 6
}
```

参数范围：

| 字段 | 范围 |
| --- | --- |
| `latitude` | -90 至 90 |
| `longitude` | -180 至 180 |
| `radius_m` | 100–20000 |
| `store_limit` | 1–100 |
| `items_per_store` | 1–50 |

网页使用浏览器 Geolocation API 获取用户授权的经纬度。后端将菜单按平台和商家分组，再通过稳定哈希在用户周围生成模拟距离、坐标、配送费和起送价。同一位置和相同参数会得到相同结果。

此接口仅用于模拟“根据当前位置收集商家信息”的应用流程，不代表真实门店位置或真实平台数据。

### 查询模拟菜品

`GET /menu-items`

支持以下可选查询参数：

- `platform`：`meituan`、`eleme` 或 `jd`。
- `category`：按菜品分类精确筛选。
- `max_price_yuan`：最高单价，必须大于 0。
- `limit`：返回数量，范围 1–1000，默认 100。

示例：

```text
GET /menu-items?platform=meituan&max_price_yuan=30&limit=20
```

## 模拟菜单数据

默认菜单位于 `examples/nutrition_menu.json`，共 420 道菜，包含以下字段：

- 菜品 ID、平台、商家名称、菜品名称和分类。
- 份量、价格、相似组、价格档位和数据角色。
- 热量、蛋白质、脂肪、碳水、膳食纤维、钠和添加糖。

数据集包含：

- 60 个相似组，每组 3 道菜，共 180 道具有营养相似菜的菜品。
- 相似组内核心营养差异不超过 10%，并设置明显的价格差异。
- 240 道标记为 `data_role=distinct` 的差异化菜品，任意两道之间至少有一项核心营养差异超过 10%。
- 三个平台各 140 道菜品。

重新生成 JSON 数据：

```powershell
python generate_menu_data.py
```

将 JSON 菜单导出为便于查看的 TXT 文件：

```powershell
python export_menu_txt.py
```

也可以通过环境变量替换菜单文件：

```powershell
$env:NUTRITION_MENU_FILE = "C:\path\to\another_menu.json"
.venv\Scripts\uvicorn app.main:app --reload
```

替换文件需保持与默认 JSON 相同的数据结构。

## 性能优化

- 按菜单文件修改时间缓存解析结果，文件未变化时不重复读取和校验 JSON。
- 提前把营养字典转换为固定顺序数值元组，减少组合循环中的字典查询。
- 使用热量对数桶缩小相似菜候选范围。
- 精确解只保留价格最低的 10 个结果。
- 兜底解采用流式维护，只保留当前偏离最小的 3 个组合。
- 使用热量偏离作为总偏离下界，对不可能进入结果集的组合安全剪枝。

## API 一览

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/` | 返回网页界面 |
| `GET` | `/health` | 服务健康检查 |
| `POST` | `/nutrition` | 计算每日营养目标 |
| `POST` | `/recommendations` | 推荐午餐与晚餐组合 |
| `GET` | `/breakfast-presets` | 获取经典早餐选项 |
| `GET` | `/platforms` | 获取三平台模拟数据统计 |
| `POST` | `/nearby-stores` | 根据经纬度模拟附近商家 |
| `GET` | `/menu-items` | 查询和筛选模拟菜品 |

## 测试与检查

运行全部单元测试：

```powershell
python -m unittest discover -s tests -v
```

执行 Python 语法编译检查：

```powershell
python -m compileall -q app tests generate_menu_data.py export_menu_txt.py
```

## 免责声明

本项目中的营养目标、早餐营养和菜品营养均为一般性公式或工程模拟数据，仅适合软件开发、算法验证和教学演示，不能替代医生诊断、医学治疗或注册营养师制定的个体化方案。存在慢性病、妊娠、未成年、运动员训练或其他特殊营养需求时，应咨询专业人员。
