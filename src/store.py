# -*- coding: utf-8 -*-
"""
考题二：内存记账存储（线程安全）。

数据保存在进程内存列表中，服务重启即清空，符合课堂练习定位。
新增流水与查询汇总都在同一把互斥锁内完成，保证：
1. 自增 ID 不会因并发写入而重复；
2. 遍历返回前先复制快照，避免查询过程中列表被其他线程修改。
"""

from datetime import date
from threading import Lock
from typing import Optional


class RecordStore:
    """线程安全的内存流水仓库。"""

    def __init__(self) -> None:
        self._records: list[dict] = []
        self._next_id: int = 1
        self._lock = Lock()

    def add(self, item: dict) -> dict:
        """
        新增一条流水，分配自增 id。

        参数 item 字段：amount、type、category、date（date 为 date 对象）。
        返回入库后的完整流水（含 id）。
        """
        with self._lock:
            record = {
                "id": self._next_id,
                "amount": round(float(item["amount"]), 2),
                "type": item["type"],
                "category": item["category"].strip(),
                "date": item["date"],
            }
            self._records.append(record)
            self._next_id += 1
            # 返回字典副本，避免外部引用直接修改内部对象
            return dict(record)

    def query(
        self,
        record_type: Optional[str] = None,
        category: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[dict]:
        """按条件筛选流水，按 id 升序返回快照副本。"""
        with self._lock:
            snapshot = [dict(r) for r in self._records]

        result = []
        for record in snapshot:
            if record_type is not None and record["type"] != record_type:
                continue
            if category is not None and record["category"] != category.strip():
                continue
            if start_date is not None and record["date"] < start_date:
                continue
            if end_date is not None and record["date"] > end_date:
                continue
            result.append(record)
        return result

    def summarize(self, start_date: date, end_date: date) -> dict:
        """统计指定日期区间（含两端）内的收入合计、支出合计与结余。"""
        with self._lock:
            snapshot = [dict(r) for r in self._records]

        total_income = 0.0
        total_expense = 0.0
        for record in snapshot:
            if record["date"] < start_date or record["date"] > end_date:
                continue
            if record["type"] == "income":
                total_income += record["amount"]
            elif record["type"] == "expense":
                total_expense += record["amount"]

        return {
            "start_date": start_date,
            "end_date": end_date,
            "total_income": round(total_income, 2),
            "total_expense": round(total_expense, 2),
            "balance": round(total_income - total_expense, 2),
        }
