# Lab1 考题二：FastAPI 简易记账接口（Python Vibe Coding 实验一）

基于 FastAPI 实现的简易记账 HTTP 服务：支持新增流水、按类型 / 分类 / 日期区间筛选分页查询、按日期区间汇总收入、支出与结余。数据存放在进程内存中，所有非法输入返回 4xx 状态码与结构化错误信息，pytest 覆盖正常与边界异常用例。

## 功能

1. **新增流水** `POST /records`
   - 字段：金额 `amount`、类型 `type`（income 收入 / expense 支出）、分类 `category`、日期 `date`（YYYY-MM-DD）
   - 校验：金额必须大于 0；类型只能是收入或支出；分类非空；日期格式合法
2. **筛选分页查询** `GET /records`
   - 可选条件：类型、分类、起始日期、结束日期
   - 分页参数：`page`（从 1 开始）、`page_size`（1~100）
3. **区间汇总** `GET /summary`
   - 返回区间内收入合计、支出合计与结余（结余 = 收入合计 − 支出合计）
4. **结构化错误**：参数不合法统一返回 422，响应体为 `{"detail": [{"field": "...", "message": "..."}]}`

## 目录结构

```
fastapi-expense-tracker-lab1/
├── src/
│   ├── __init__.py
│   ├── main.py            # FastAPI 应用、路由、统一校验错误处理
│   ├── schemas.py         # pydantic 请求 / 响应模型与字段校验
│   └── store.py           # 线程安全的内存流水仓库
├── tests/
│   ├── __init__.py
│   └── test_api.py        # pytest 测试用例（正常 + 边界 + 异常）
├── docs/
│   ├── 需求澄清_考题二.md
│   ├── 实验报告.md
│   ├── ai对话记录.md
│   ├── 复盘.md
│   └── images/
│       ├── api_docs_swagger.png        # Swagger 接口文档截图
│       ├── api_summary_response.png    # 区间汇总真实响应截图
│       ├── api_records_response.png    # 支出明细筛选响应截图
│       ├── api_validation_error.png    # 非法类型 422 响应截图
│       ├── pytest_output.txt           # pytest 运行结果记录
│       └── live_api_check.txt          # 真实启动后接口调用记录
├── .gitignore
├── requirements.txt
└── README.md
```

## 环境要求

- Python 3.10+（本机实测 Python 3.14.5）
- 依赖见 `requirements.txt`：fastapi、uvicorn、pydantic、pytest、httpx

## 运行方式

在项目根目录创建虚拟环境并安装依赖：

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
```

启动服务：

```bash
uvicorn src.main:app --host 127.0.0.1 --port 8000
```

启动后：

- 健康检查：http://127.0.0.1:8000/
- 自动接口文档（Swagger）：http://127.0.0.1:8000/docs

## 运行测试

```bash
pytest tests/ -v
```

共 13 个用例：

- 正常：新增收入 / 支出、字段回显、id 自增
- 边界 / 异常：金额为 0 或负数、类型非法、日期格式错误、分类全空格、列表查询类型非法、分页参数非法
- 查询：按类型筛选、按分类筛选、日期区间筛选、分页
- 汇总：区间收入 / 支出 / 结余计算、空区间归零、缺少日期参数 422

## 接口示例

### 新增收入

```bash
POST /records
{
  "amount": 5000.0,
  "type": "income",
  "category": "工资",
  "date": "2026-11-01"
}
```

### 按支出筛选并分页

```bash
GET /records?type=expense&page=1&page_size=10
```

### 区间汇总

```bash
GET /summary?start_date=2026-11-01&end_date=2026-11-02
```

## 设计说明

- **数据存储**：进程内存列表 + 线程互斥锁；服务重启后数据清空。新增流水在锁内分配自增 ID 并写入；查询先复制快照再过滤，避免遍历期间列表被并发修改。
- **参数校验**：请求体由 pydantic v2 模型校验；查询参数由 FastAPI 结合 `Query(ge=...)` 约束校验；校验错误经统一异常处理器整理为结构化 422 响应。
- **并发保证**：写操作串行化在同一把锁内，保证 ID 自增不重复、列表更新原子；本项目为单进程内存存储，如需多进程 / 多机部署应替换为 SQLite 或数据库并使用事务。

## 边界与异常处理

- 金额为 0、负数 → 422
- 类型不是 income / expense → 422
- 分类为空或全空格 → 422
- 日期格式错误或不存在的日期 → 422
- 页码为 0、每页条数超过 100 → 422
- 汇总缺少日期参数 → 422
- 查询结果为空、汇总区间无流水 → 返回空列表 / 三项金额为 0，不报错

## 设计说明与过程文档

- [需求澄清](docs/需求澄清_考题二.md)
- [实验报告](docs/实验报告.md)
- [AI 协作对话记录](docs/ai对话记录.md)
- [复盘](docs/复盘.md)
