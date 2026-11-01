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
