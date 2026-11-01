# -*- coding: utf-8 -*-
"""
考题二：FastAPI 记账接口 pytest 测试用例。

覆盖范围：
- 正常新增流水、字段回显与 id 自增
- 边界 / 异常：金额非正、类型非法、日期格式错误、分类为空、分页非法
- 查询筛选（类型、分类、日期区间）与分页
- 区间汇总：收入合计、支出合计、结余；空区间返回 0；缺少日期参数 4xx
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

# 将项目根目录加入 sys.path，确保能正确导入 src 下的模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.main import create_app
from src.store import RecordStore


# ================= 辅助函数 =================

def make_client() -> TestClient:
    """创建带全新内存存储的测试客户端，保证用例之间互不影响。"""
    app = create_app(RecordStore())
    return TestClient(app)


def add(client: TestClient, **payload) -> dict:
    """发送新增流水请求并返回响应 JSON。"""
    resp = client.post("/records", json=payload)
    return resp


# ================= 正常用例 =================

def test_add_records_success():
    """
    正常用例：新增一条收入、一条支出，断言 201 状态码、字段回显正确、id 自增。
    """
    client = make_client()

    income = {
        "amount": 5000.0,
        "type": "income",
        "category": "工资",
        "date": "2026-11-01",
    }
    expense = {
        "amount": 35.5,
        "type": "expense",
        "category": "餐饮",
        "date": "2026-11-01",
    }

    r1 = add(client, **income)
    assert r1.status_code == 201, "新增收入应返回 201"
    body1 = r1.json()
    assert body1["id"] == 1
    assert body1["amount"] == 5000.0
    assert body1["type"] == "income"
    assert body1["category"] == "工资"
    assert body1["date"] == "2026-11-01"

    r2 = add(client, **expense)
    assert r2.status_code == 201, "新增支出应返回 201"
    body2 = r2.json()
    assert body2["id"] == 2, "第二条流水 id 应自增为 2"
    assert body2["type"] == "expense"


# ================= 边界 / 异常用例：新增校验 =================

def test_amount_must_be_positive():
    """
    边界用例1：金额为 0 与负数均应被拒绝，返回 422。
    """
    client = make_client()

    zero = client.post("/records", json={
        "amount": 0, "type": "expense", "category": "餐饮", "date": "2026-11-01"
    })
    assert zero.status_code == 422, "金额为 0 应返回 422"

    negative = client.post("/records", json={
        "amount": -50, "type": "expense", "category": "餐饮", "date": "2026-11-01"
    })
    assert negative.status_code == 422, "金额为负数应返回 422"


def test_invalid_type_rejected():
    """
    边界用例2：类型不是 income / expense 时应返回 422。
    """
    client = make_client()
    resp = client.post("/records", json={
        "amount": 100, "type": "loan", "category": "借款", "date": "2026-11-01"
    })
    assert resp.status_code == 422, "非法类型应返回 422"
    # 错误信息为结构化结构，包含 detail 字段列表
    assert "detail" in resp.json()


def test_invalid_date_format_rejected():
    """
    边界用例3：日期格式错误（不存在的月份）与非日期字符串均应返回 422。
    """
    client = make_client()

    bad_month = client.post("/records", json={
        "amount": 100, "type": "expense", "category": "交通", "date": "2026-13-40"
    })
    assert bad_month.status_code == 422, "非法日期 2026-13-40 应返回 422"

    not_date = client.post("/records", json={
        "amount": 100, "type": "expense", "category": "交通", "date": "abc"
    })
    assert not_date.status_code == 422, "非日期字符串应返回 422"


def test_empty_category_rejected():
    """
    边界用例4：分类为空字符串应返回 422。
    """
    client = make_client()
    resp = client.post("/records", json={
        "amount": 100, "type": "expense", "category": "   ", "date": "2026-11-01"
    })
    assert resp.status_code == 422, "分类为空应返回 422"


# ================= 查询筛选与分页 =================

def seed_two_days(client: TestClient) -> None:
    """灌入跨两天的多条流水，供筛选、分页、汇总测试使用。"""
    client.post("/records", json={"amount": 5000.0, "type": "income", "category": "工资", "date": "2026-11-01"})
    client.post("/records", json={"amount": 35.5, "type": "expense", "category": "餐饮", "date": "2026-11-01"})
    client.post("/records", json={"amount": 20.0, "type": "expense", "category": "交通", "date": "2026-11-01"})
    client.post("/records", json={"amount": 80.0, "type": "expense", "category": "餐饮", "date": "2026-11-02"})
    client.post("/records", json={"amount": 2000.0, "type": "income", "category": "兼职", "date": "2026-11-02"})


def test_list_filter_by_type_and_category():
    """按类型、分类筛选，断言只返回匹配的流水。"""
    client = make_client()
    seed_two_days(client)

    expenses = client.get("/records", params={"type": "expense"}).json()
    assert expenses["total"] == 3, "应筛出 3 条支出"
    assert all(item["type"] == "expense" for item in expenses["items"])

    food = client.get("/records", params={"category": "餐饮"}).json()
    assert food["total"] == 2, "应筛出 2 条餐饮"
    assert all(item["category"] == "餐饮" for item in food["items"])


def test_list_filter_by_date_range():
    """按日期区间筛选，只返回区间内流水。"""
    client = make_client()
    seed_two_days(client)

    resp = client.get("/records", params={
        "start_date": "2026-11-02", "end_date": "2026-11-02"
    }).json()
    assert resp["total"] == 2, "11 月 2 日应有 2 条流水"


def test_list_pagination():
    """分页参数生效：第一页 2 条，第二页 1 条，total 为全部匹配数。"""
    client = make_client()
    seed_two_days(client)

    page1 = client.get("/records", params={"type": "expense", "page": 1, "page_size": 2}).json()
    assert page1["total"] == 3
    assert len(page1["items"]) == 2
    assert page1["page"] == 1 and page1["page_size"] == 2

    page2 = client.get("/records", params={"type": "expense", "page": 2, "page_size": 2}).json()
    assert len(page2["items"]) == 1


def test_invalid_pagination_rejected():
    """分页参数非法（页码为 0、每页超过上限）返回 422。"""
    client = make_client()
    r1 = client.get("/records", params={"page": 0})
    assert r1.status_code == 422, "page=0 应返回 422"
    r2 = client.get("/records", params={"page_size": 200})
    assert r2.status_code == 422, "page_size 超过 100 应返回 422"


def test_invalid_query_type_rejected():
    """列表查询传入非法 type 取值时返回 422。"""
    client = make_client()
    resp = client.get("/records", params={"type": "loan"})
    assert resp.status_code == 422, "查询类型非法应返回 422"
    assert "detail" in resp.json()


# ================= 区间汇总 =================

def test_summary_calculation():
    """汇总：收入合计、支出合计、结余与人工手算一致。"""
    client = make_client()
    seed_two_days(client)

    resp = client.get("/summary", params={
        "start_date": "2026-11-01", "end_date": "2026-11-02"
    })
    assert resp.status_code == 200
    body = resp.json()
    # 收入 5000 + 2000 = 7000；支出 35.5 + 20 + 80 = 135.5；结余 = 6864.5
    assert body["total_income"] == 7000.0
    assert body["total_expense"] == 135.5
    assert body["balance"] == 6864.5


def test_summary_empty_range_returns_zero():
    """区间内无流水时，三项金额均为 0，不报错。"""
    client = make_client()
    seed_two_days(client)

    resp = client.get("/summary", params={
        "start_date": "2026-12-20", "end_date": "2026-12-25"
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_income"] == 0
    assert body["total_expense"] == 0
    assert body["balance"] == 0


def test_summary_missing_date_rejected():
    """汇总缺少日期参数返回 422。"""
    client = make_client()
    resp = client.get("/summary", params={"start_date": "2026-11-01"})
    assert resp.status_code == 422, "缺少 end_date 应返回 422"
