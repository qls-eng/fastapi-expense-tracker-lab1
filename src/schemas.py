# -*- coding: utf-8 -*-
"""
考题二：FastAPI 记账接口 —— 请求 / 响应数据模型。

使用 pydantic v2 完成入参校验：金额必须为正、类型只能是收入或支出、
分类非空、日期必须是合法 YYYY-MM-DD。
"""

from datetime import date as DateType
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class RecordIn(BaseModel):
    """新增流水的请求体模型。"""

    # 金额必须大于 0，不允许 0、负数
    amount: float = Field(gt=0, description="金额，必须大于 0")
    # 类型只能是收入或支出
    type: Literal["income", "expense"] = Field(description="类型：income 收入 / expense 支出")
    # 分类不能为空；首尾空格在校验器中去除，全空格视为空
    category: str = Field(description="分类，如 餐饮、工资、交通")
    # 日期，pydantic 自动校验 YYYY-MM-DD 格式与日期合法性
    date: DateType = Field(description="日期，格式 YYYY-MM-DD")

    @field_validator("category")
    @classmethod
    def category_not_blank(cls, value: str) -> str:
        """去除首尾空格后校验分类非空，全空格视为非法输入。"""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("分类不能为空")
        return cleaned


class RecordOut(BaseModel):
    """流水响应模型（含自增 id）。"""

    id: int
    amount: float
    type: Literal["income", "expense"]
    category: str
    date: DateType


class SummaryOut(BaseModel):
    """区间汇总响应模型。"""

    start_date: DateType
    end_date: DateType
    total_income: float = Field(description="区间内收入合计")
    total_expense: float = Field(description="区间内支出合计")
    balance: float = Field(description="结余 = 收入合计 - 支出合计")


class CategoryStat(BaseModel):
    """单个分类的聚合结果。"""

    type: Literal["income", "expense"] = Field(description="所属类型")
    category: str = Field(description="分类名")
    total: float = Field(description="该分类区间内金额合计")
    count: int = Field(description="该分类区间内条数")
    percent: float = Field(description="占同类型总额的百分比，保留两位小数")


class CategorySummaryOut(BaseModel):
    """按分类汇总的响应模型。"""

    start_date: DateType
    end_date: DateType
    total_income: float = Field(description="区间内收入合计，作百分比分母")
    total_expense: float = Field(description="区间内支出合计，作百分比分母")
    items: list[CategoryStat] = Field(description="各分类聚合明细，收入在前、同类按金额降序")
