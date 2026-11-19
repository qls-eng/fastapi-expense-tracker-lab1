# -*- coding: utf-8 -*-
"""
考题二：FastAPI 记账接口主程序。

接口一览：
- POST   /records             新增一条流水（金额 > 0、类型合法、分类非空、日期格式合法）
- GET    /records             按类型 / 分类 / 日期区间筛选，分页返回
- GET    /records/export      按同样筛选条件导出 CSV（utf-8-sig）
- GET    /summary             指定日期区间内收入合计、支出合计、结余
- GET    /summary/by-category 按分类聚合，附各分类占同类型总额的百分比

启动方式：在项目根目录执行  uvicorn src.main:app --host 127.0.0.1 --port 8000
"""

from datetime import date
from io import StringIO
from typing import Iterable, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from src.schemas import CategorySummaryOut, RecordIn, RecordOut, SummaryOut
from src.store import RecordStore

import csv

CSV_COLUMNS = ("id", "amount", "type", "category", "date")


def _ensure_date_order(start_date: date, end_date: date) -> None:
    """校验日期区间顺序，起止颠倒时返回结构化 422。"""
    if start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail=[{"field": "start_date", "message": "起始日期不能晚于结束日期"}],
        )


def _build_csv(records: Iterable[dict]) -> bytes:
    """把流水列表渲染成 CSV 字节串（utf-8-sig，Excel 直接打开不乱码）。"""
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for record in records:
        writer.writerow([record[col] for col in CSV_COLUMNS])
    return buffer.getvalue().encode("utf-8-sig")


def create_app(store: Optional[RecordStore] = None) -> FastAPI:
    """创建 FastAPI 应用，便于测试时注入独立的内存存储。"""
    app = FastAPI(title="Lab1 考题二：简易记账接口", version="1.0.0")
    app.state.store = store or RecordStore()

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        """把校验错误统一整理成结构化的 422 响应。"""
        errors = []
        for err in exc.errors():
            # err["loc"] 形如 ("body", "amount") 或 ("query", "page")
            field = ".".join(str(x) for x in err["loc"][1:]) or str(err["loc"][0])
            errors.append({"field": field, "message": err["msg"]})
        return JSONResponse(status_code=422, content={"detail": errors})

    @app.post("/records", response_model=RecordOut, status_code=201)
    def add_record(payload: RecordIn):
        """新增一条流水。"""
        record = app.state.store.add(
            {
                "amount": payload.amount,
                "type": payload.type,
                "category": payload.category,
                "date": payload.date,
            }
        )
        return record

    @app.get("/records")
    def list_records(
        record_type: Optional[str] = Query(None, alias="type", description="income / expense"),
        category: Optional[str] = Query(None, description="分类精确匹配"),
        start_date: Optional[date] = Query(None, description="起始日期（含）YYYY-MM-DD"),
        end_date: Optional[date] = Query(None, description="结束日期（含）YYYY-MM-DD"),
        page: int = Query(1, ge=1, description="页码，从 1 开始"),
        page_size: int = Query(10, ge=1, le=100, description="每页条数，1~100"),
    ):
        """按条件筛选流水并分页返回。"""
        # 查询类型取值合法性校验，非法取值返回 422
        if record_type is not None and record_type not in ("income", "expense"):
            raise HTTPException(
                status_code=422,
                detail=[{"field": "type", "message": "类型只能为 income 或 expense"}],
            )
        records = app.state.store.query(
            record_type=record_type,
            category=category,
            start_date=start_date,
            end_date=end_date,
        )
        total = len(records)
        start = (page - 1) * page_size
        end = start + page_size
        items = records[start:end]
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    @app.get("/summary", response_model=SummaryOut)
    def summary(
        start_date: date = Query(..., description="起始日期（含）YYYY-MM-DD"),
        end_date: date = Query(..., description="结束日期（含）YYYY-MM-DD"),
    ):
        """返回指定日期区间内的收入、支出与结余。"""
        _ensure_date_order(start_date, end_date)
        return app.state.store.summarize(start_date, end_date)

    @app.get("/summary/by-category", response_model=CategorySummaryOut)
    def summary_by_category(
        start_date: date = Query(..., description="起始日期（含）YYYY-MM-DD"),
        end_date: date = Query(..., description="结束日期（含）YYYY-MM-DD"),
        record_type: Optional[str] = Query(None, alias="type", description="income / expense，缺省统计全部"),
    ):
        """按分类聚合区间内的流水，并给出各分类占同类型总额的百分比。"""
        _ensure_date_order(start_date, end_date)
        if record_type is not None and record_type not in ("income", "expense"):
            raise HTTPException(
                status_code=422,
                detail=[{"field": "type", "message": "类型只能为 income 或 expense"}],
            )

        totals = app.state.store.summarize(start_date, end_date)
        items = app.state.store.summarize_by_category(start_date, end_date, record_type)

        rendered = []
        for item in items:
            base = totals["total_income"] if item["type"] == "income" else totals["total_expense"]
            percent = round(item["total"] / base * 100, 2) if base else 0.0
            rendered.append({**item, "percent": percent})

        return {
            "start_date": start_date,
            "end_date": end_date,
            "total_income": totals["total_income"],
            "total_expense": totals["total_expense"],
            "items": rendered,
        }

    @app.get(
        "/records/export",
        response_class=Response,
        responses={
            200: {
                "description": "CSV 文件（utf-8-sig 编码，可直接用 Excel 打开）",
                "content": {
                    "text/csv": {
                        "schema": {"type": "string", "format": "binary"},
                        "example": "id,amount,type,category,date\r\n1,5000.0,income,工资,2026-11-01",
                    }
                },
            },
            422: {"description": "参数校验失败（非法 type、起止日期颠倒等）"},
        },
    )
    def export_records(
        record_type: Optional[str] = Query(None, alias="type", description="income / expense"),
        category: Optional[str] = Query(None, description="分类精确匹配"),
        start_date: Optional[date] = Query(None, description="起始日期（含）YYYY-MM-DD"),
        end_date: Optional[date] = Query(None, description="结束日期（含）YYYY-MM-DD"),
    ):
        """按与 /records 相同的筛选条件导出 CSV 文件。"""
        if record_type is not None and record_type not in ("income", "expense"):
            raise HTTPException(
                status_code=422,
                detail=[{"field": "type", "message": "类型只能为 income 或 expense"}],
            )
        if start_date is not None and end_date is not None:
            _ensure_date_order(start_date, end_date)

        records = app.state.store.query(
            record_type=record_type,
            category=category,
            start_date=start_date,
            end_date=end_date,
        )
        content = _build_csv(records)
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="records.csv"',
                "X-Total-Records": str(len(records)),
            },
        )

    @app.get("/")
    def health():
        """健康检查，便于确认服务已启动。"""
        return {"status": "ok", "message": "记账接口已启动"}

    return app


# 模块级应用实例，供 uvicorn 启动使用
app = create_app()


if __name__ == "__main__":
    import uvicorn

    # 仅绑定本地回环地址，不对外暴露
    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=False)
