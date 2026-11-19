## 考题二 第1轮：需求澄清与数据模型

**我的提问：**
请按 FastAPI 设计一个记账接口的数据模型：流水字段为金额、类型（income / expense）、分类、日期。要求金额大于 0、类型枚举合法、分类非空、日期为 YYYY-MM-DD；另外设计流水响应模型与区间汇总模型（收入合计、支出合计、结余）。用 pydantic v2，加中文注释。

**AI 输出摘要：**
AI 给出 `RecordIn`、`RecordOut`、`SummaryOut` 三个模型，金额用 `Field(gt=0)`，类型用 `Literal`，日期用 `datetime.date`。

**人工修改：**
- 首次运行时 pydantic 报错：模型字段名 `date` 与导入的类型 `date` 同名，类命名空间内类型注解无法解析。人工将导入改为 `from datetime import date as DateType`，注解统一写 `DateType`，问题解决。

**运行结果：**
模型类成功构建，服务应用可以正常导入。

## 考题二 第2轮：内存存储与线程安全

**我的提问：**
请写一个线程安全的内存流水仓库：自增 ID、新增、按类型 / 分类 / 日期区间查询、区间汇总；新增与查询都要考虑并发，查询时先复制快照再过滤；结余 = 收入 − 支出。

**AI 输出摘要：**
AI 给出 `RecordStore` 类，内部 `list` + `threading.Lock`，`add` 在锁内分配 ID 并追加，`query` 与 `summarize` 在锁内复制快照后在锁外过滤统计。

**人工修改：**
- 金额入库时统一 `round(..., 2)`，分类入库前 `strip()`，避免浮点误差与首尾空格影响筛选。

**运行结果：**
单元测试中连续新增多条流水，ID 按 1、2、3 自增，筛选与汇总结果正确。

## 考题二 第3轮：FastAPI 路由与统一错误处理

**我的提问：**
基于存储仓库创建 FastAPI 应用：`POST /records` 返回 201；`GET /records` 支持类型、分类、起止日期筛选与分页（page 从 1 开始，page_size 1~100）；`GET /summary` 必填起止日期；校验错误统一返回 422 与结构化 detail。提供 `create_app(store)` 工厂便于测试注入独立存储。

**AI 输出摘要：**
AI 给出 `create_app` 工厂、三个路由、自定义 `RequestValidationError` 异常处理器，把错误整理为 `{"detail": [{"field": ..., "message": ...}]}`；分页做切片；汇总区间无数据时金额归零。

**人工修改：**
- 去掉了未使用的 `ValidationError` 导入；
- 健康检查接口 `/` 单独返回状态，便于启动后确认服务在线；
- 补充 `GET /records` 的 `type` 取值校验：传入非 income / expense 的值直接返回 422，避免非法类型静默得到空列表。

**运行结果：**
真实启动 uvicorn 后，`GET /` 返回 `{"status": "ok"}`；新增、筛选、汇总接口调用正常；负金额请求返回 422。

## 考题二 第4轮：pytest 测试用例

**我的提问：**
请为接口写 pytest，用 TestClient，每个用例使用全新内存存储；覆盖正常新增、金额非正、类型非法、日期格式错误、分类为空、类型 / 分类 / 日期区间筛选、分页、汇总计算、空区间归零、缺少汇总日期参数、分页非法、列表查询类型非法。

**AI 输出摘要：**
AI 给出测试用例骨架，按正常、边界异常、查询分页、汇总分组组织。

**人工修改：**
- 分类全空格用例第一次失败：pydantic v2 中 `Field(strip_whitespace=True)` 已被弃用且未生效。人工改为 `@field_validator("category")` 先 `strip()`，为空再抛 `ValueError("分类不能为空")`，用例通过。
- 人工补充 `test_invalid_query_type_rejected`，覆盖 `GET /records?type=loan` 返回 422。

**运行结果：**
`pytest tests/ -v` → **13 passed**，运行记录见 `docs/images/pytest_output.txt`；真实服务调用记录见 `docs/images/live_api_check.txt`。

**踩坑记录：**
1. pydantic 模型字段名与导入类型同名（`date: date`）会导致注解解析失败，需用类型别名。
2. pydantic v2 不再支持在 `Field(...)` 上传 `strip_whitespace`，字符串清洗应使用 `field_validator`。
3. 本机 Python 为 3.14.5，依赖安装在项目内 `.venv`，不污染全局环境。

## 考题二 第5轮（R5）：实验后补做——按分类汇总与导出 CSV

**背景说明：**
这两个接口不在指导书要求之内。前三轮已完成"记一笔 / 查明细 / 看汇总"的最小闭环，第 4 轮 13 个用例全部通过。本轮是实验结束后（2026-11-18）认为"汇总只给总额看不出钱花在哪、明细只能看不能带走"，主动追补的两项功能。时间与性质如实记录，未修改前四轮任何内容。

**我的提问：**
```
在现有记账接口上再加两件事：
1) 按分类汇总：起止日期内，按 (type, category) 分组，给出每组总额、条数、占比；
2) 导出 CSV：按和 /records 一样的筛选条件，把明细导出成 CSV，Excel 能直接打开。

约束：不要动已有接口的对外行为；新接口要有测试；占比口径写清楚。
```

**AI 输出摘要：**
- `store.py` 新增 `summarize_by_category()`：按 `(type, category)` 聚合，返回总额与条数；
- `schemas.py` 新增 `CategoryStat`（type/category/total/count/percent）与 `CategorySummaryOut`（带 `total_income`/`total_expense` 作百分比分母）；
- `main.py` 新增 `GET /summary/by-category` 与 `GET /records/export`，导出用 `csv.writer` + `\r\n` + `utf-8-sig`，响应头带 `X-Total-Records`；
- 测试新增 9 个用例（含 BOM 校验、空结果仅表头、起止颠倒 422）。

**人工修改 / 审查发现：**
1. **排序不稳定**：AI 初版只按总额降序排，同额分类（如两条都 20 元）的顺序取决于字典内部迭代顺序，测试无法写强断言。人工定为"收入在前 → 同类型金额降序 → 同额分类字典序"，变成可预期的契约。
2. **占比分母含糊**：初版对每个分类算占比时用的是"全部收支总额"，但 `type=expense` 筛选后各分类占比会加起来远不到 100%。人工改为分母取**同类型总额**，并在响应里回传 `total_income`/`total_expense` 让调用方可自校验。
3. **`/summary` 缺起止颠倒校验**：上一轮复盘里写过"日期倒置未校验"这条改进项，本轮补上 `_ensure_date_order()`，起止颠倒统一返回结构化 422。
4. **CSV 编码**：初版用 `utf-8`，Excel 双击打开中文乱码。改为 `utf-8-sig`（带 BOM），并加用例断言首字节为 `b'\xef\xbb\xbf'`。
5. **空导出**：初版空结果直接返回空 body，前端解析会报错。改为空结果也输出表头行。

**运行结果：**
`pytest tests/ -v` → **22 passed, 1 warning in 5.08s**（原 13 个 + 新增 9 个）；输出已覆盖写入 `docs/images/pytest_output.txt`。

真实调用核对（5 条种子数据）：

```text
summary: total_income=7000.0  total_expense=135.5  balance=6864.5
by-category: 工资 5000.0/1条/71.43%  兼职 2000.0/1条/28.57%  餐饮 115.5/2条/85.24%  交通 20.0/1条/14.76%
export: content-type=text/csv; charset=utf-8  X-Total-Records=5  attachment; filename="records.csv"
        BOM=b'\xef\xbb\xbf'  行数=6（表头+5）  首行=1,5000.0,income,工资,2026-11-01
export?type=expense: X-Total-Records=3
/summary 起止颠倒: 422
```

**本轮判定：**
两接口完成且与手算一致；占比口径（同类型总额）已在报告与 README 写明，避免"四条加起来 100.01"这类误读。

## 考题二 第6轮（R6）：补 Swagger 截图时发现文档声明与实际响应不符

**背景说明：**
第 5 轮完成后，接口文档截图还只覆盖 records / summary / validation 三类，新增的两个接口没有文档图。本轮补图时发现一处真实问题，一并修掉。

**我的提问：**
```
把 /summary/by-category 和 /records/export 的 Swagger 展开截图补上。
要求：真实打开本机 /docs 截图，不要手工拼图。
```

**AI 输出摘要：**
用无头 Edge（DevTools 协议）打开 `http://127.0.0.1:8000/docs`，等 `.opblock` 渲染完成后按深链接逐个展开目标接口，再按元素实际尺寸裁切截图；产出总览图与两张展开图。

**人工审查发现：**
1. **媒体类型声明错误**：导出的截图里 `/records/export` 的 200 响应被展示成 `application/json`、示例只有 `"string"`，而接口实际返回 `text/csv`。原因是路由只写了 `media_type="text/csv; charset=utf-8"`，OpenAPI 仍按默认 json 生成。修法：在路由上加 `response_class=Response` + `responses={200: {"content": {"text/csv": {"schema": ..., "example": "id,amount,type,category,date\r\n1,5000.0,income,工资,2026-11-01"}}}}`。改完 `/openapi.json` 里 200 的媒体类型确认为 `text/csv`。
2. **首次截图失败**：先连的是浏览器级调试 target，`Page.enable` 报 `'Page.enable' wasn't found`；改为从 `/json/list` 取页面级 target 后正常。
3. **展开失败**：点"Expand all"后条目高度仍是 44px（未展开），改用 Swagger 的深链接（`#/default/<operationId>`）驱动展开，并断言 `is-open` 且高度 > 150px 后再截图。

**运行结果：**
`pytest tests/ -q` → **22 passed, 1 warning in 3.85s**（改动只影响文档声明，未动业务逻辑）；三张 Swagger 图重新产出并已读图复核，导出的 200 明确显示 `text/csv` 与 CSV 示例。

**本轮判定：**
截图是真实渲染结果，未做任何拼接或改字；发现的文档声明问题已修正并回归测试，没有把"截图看着不对"当作可接受状态。
