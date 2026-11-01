# -*- coding: utf-8 -*-
"""
考题二：FastAPI 记账接口主程序。

接口一览：
- POST   /records   新增一条流水（金额 > 0、类型合法、分类非空、日期格式合法）
- GET    /records  按类型 / 分类 / 日期区间筛选，分页返回
- GET    /summary  指定日期区间内收入合计、支出合计、结余

启动方式：在项目根目录执行  uvicorn src.main:app --host 127.0.0.1 --port 8000
"""

from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.schemas import RecordIn, RecordOut, SummaryOut
from src.store import RecordStore


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
        return app.state.store.summarize(start_date, end_date)

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
