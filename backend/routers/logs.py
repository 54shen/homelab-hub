# ============================================================
# Shared Center — 系统日志 API
# ============================================================
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from models import SystemLog
from schemas import SystemLogOut, SystemLogListOut, ApiResponse
from auth import auth_optional

router = APIRouter(prefix="/api", tags=["系统日志"])


@router.get("/logs", response_model=SystemLogListOut)
def list_logs(
    level: str | None = Query(None),
    module: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    q = db.query(SystemLog)
    if level:
        q = q.filter(SystemLog.level == level)
    if module:
        q = q.filter(SystemLog.module == module)

    total = q.count()
    items = q.order_by(SystemLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return SystemLogListOut(items=[SystemLogOut.from_orm(r) for r in items], total=total)


@router.get("/logs/export")
def export_logs(
    level: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
    db: Session = Depends(get_db)
):
    from fastapi.responses import StreamingResponse
    import io, csv

    q = db.query(SystemLog)
    if level:
        q = q.filter(SystemLog.level == level)
    if start:
        q = q.filter(SystemLog.created_at >= start)
    if end:
        q = q.filter(SystemLog.created_at <= end)

    rows = q.order_by(SystemLog.created_at.desc()).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ID", "Level", "Module", "Message", "Detail", "Created At"])
    for r in rows:
        writer.writerow([r.id, r.level, r.module, r.message, r.detail, r.created_at])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue().encode("utf-8-sig")]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=logs_export.csv"})


@router.post("/logs/clear", response_model=ApiResponse)
def clear_logs(db: Session = Depends(get_db), _auth=Depends(auth_optional)):
    db.query(SystemLog).delete()
    db.commit()
    return ApiResponse(success=True, message="已清空")
