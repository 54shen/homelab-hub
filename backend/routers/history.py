# ============================================================
# Shared Center — 历史记录 API
# ============================================================
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from models import KvHistory
from schemas import KvHistoryOut, KvHistoryListOut

router = APIRouter(prefix="/api", tags=["历史记录"])


@router.get("/history", response_model=KvHistoryListOut)
def list_history(
    key: str | None = Query(None, description="精确匹配某个 key"),
    search: str | None = Query(None, description="模糊搜索 key"),
    start: str | None = Query(None, description="起始时间 YYYY-MM-DD HH:MM:SS"),
    end: str | None = Query(None, description="结束时间"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """分页查询历史记录。key 精确匹配时用 ?key=，模糊搜索用 ?search=。"""
    q = db.query(KvHistory)

    if key:
        q = q.filter(KvHistory.key == key)
    elif search:
        q = q.filter(KvHistory.key.contains(search))

    if start:
        q = q.filter(KvHistory.changed_at >= start)
    if end:
        q = q.filter(KvHistory.changed_at <= end)

    total = q.count()
    items = (
        q.order_by(KvHistory.changed_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return KvHistoryListOut(
        items=[KvHistoryOut.from_orm(r) for r in items],
        total=total
    )


@router.get("/history/export")
def export_history(
    key: str | None = Query(None),
    search: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
    db: Session = Depends(get_db)
):
    """导出历史记录为 CSV（utf-8 BOM，Excel 友好）"""
    from fastapi.responses import StreamingResponse
    import io, csv

    q = db.query(KvHistory)

    if key:
        q = q.filter(KvHistory.key == key)
    elif search:
        q = q.filter(KvHistory.key.contains(search))
    if start:
        q = q.filter(KvHistory.changed_at >= start)
    if end:
        q = q.filter(KvHistory.changed_at <= end)

    rows = q.order_by(KvHistory.changed_at.desc()).all()

    buf = io.StringIO()
    buf.write("﻿")  # UTF-8 BOM
    writer = csv.writer(buf)
    writer.writerow(["ID", "Key", "Old Value", "New Value", "Source", "Changed At"])
    for r in rows:
        writer.writerow([r.id, r.key, r.old_value or "(新增)", r.new_value, r.source, r.changed_at])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue().encode("utf-8")]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
    )
