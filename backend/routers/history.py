# ============================================================
# Shared Center — 历史记录 API
# ============================================================
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from models import KvHistory
from schemas import KvHistoryOut, HistoryListOut

router = APIRouter(prefix="/api", tags=["历史记录"])


@router.get("/history", response_model=HistoryListOut)
def list_history(
    key: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    q = db.query(KvHistory)

    if key:
        q = q.filter(KvHistory.key == key)
    if start:
        q = q.filter(KvHistory.changed_at >= start)
    if end:
        q = q.filter(KvHistory.changed_at <= end)
    if not start and not end:
        # 默认最近30天
        default_start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        q = q.filter(KvHistory.changed_at >= default_start)

    total = q.count()
    items = q.order_by(KvHistory.changed_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return HistoryListOut(items=[KvHistoryOut.from_orm(r) for r in items], total=total)


@router.get("/history/export")
def export_history(
    key: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
    db: Session = Depends(get_db)
):
    from fastapi.responses import StreamingResponse
    import io, csv

    q = db.query(KvHistory)
    if key:
        q = q.filter(KvHistory.key == key)
    if start:
        q = q.filter(KvHistory.changed_at >= start)
    if end:
        q = q.filter(KvHistory.changed_at <= end)

    rows = q.order_by(KvHistory.changed_at.desc()).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ID", "Key", "Old Value", "New Value", "Source", "Changed At"])
    for r in rows:
        writer.writerow([r.id, r.key, r.old_value, r.new_value, r.source, r.changed_at])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=history_export.csv"}
    )
