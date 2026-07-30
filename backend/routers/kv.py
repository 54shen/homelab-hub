# ============================================================
# Shared Center — KV 变量 API
# ============================================================
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from websocket_manager import broadcast
from database import get_db
from models import KvEntry, KvHistory
from schemas import (
    KvSetRequest, KvBatchRequest, KvBatchDeleteRequest,
    KvEntryOut, ApiResponse
)
from auth import get_current_token, require_permission
import json

router = APIRouter(prefix="/api", tags=["KV 变量"])


def _log_history(db: Session, key: str, old_val: str | None, new_val: str, source: str):
    h = KvHistory(key=key, old_value=old_val, new_value=new_val, source=source)
    db.add(h)


@router.get("/list", response_model=list[KvEntryOut])
def list_kv(prefix: str | None = Query(None), db: Session = Depends(get_db)):
    q = db.query(KvEntry)
    if prefix:
        q = q.filter(KvEntry.key.like(f"{prefix}%"))
    return q.order_by(KvEntry.updated_at.desc()).all()


@router.get("/kv/{key}", response_model=KvEntryOut)
def get_kv(key: str, db: Session = Depends(get_db)):
    entry = db.query(KvEntry).filter(KvEntry.key == key).first()
    if not entry:
        from fastapi import HTTPException
        raise HTTPException(404, f"变量 '{key}' 不存在")
    return entry


@router.post("/kv", response_model=ApiResponse)
async def set_kv(req: KvSetRequest, db: Session = Depends(get_db)):
    entry = db.query(KvEntry).filter(KvEntry.key == req.key).first()
    now_str = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if entry:
        old = entry.value
        entry.value = str(req.value)
        entry.type = req.type
        entry.source = req.source
        entry.retention_days = req.retention_days
        entry.updated_at = now_str
        if req.expire_seconds is not None:
            entry.expire_seconds = req.expire_seconds
        _log_history(db, req.key, old, str(req.value), req.source)
    else:
        entry = KvEntry(
            key=req.key,
            value=str(req.value),
            type=req.type,
            source=req.source,
            retention_days=req.retention_days,
            expire_seconds=req.expire_seconds,
            updated_at=now_str
        )
        db.add(entry)
        _log_history(db, req.key, None, str(req.value), req.source)

    db.commit()
    await broadcast("kv.changed", {"key": req.key, "value": str(req.value), "source": req.source})
    return ApiResponse(success=True, message="OK")


@router.post("/kv/batch", response_model=ApiResponse)
def batch_set_kv(req: KvBatchRequest, db: Session = Depends(get_db)):
    for item in req.items:
        set_kv(item, db)
    return ApiResponse(success=True, message=f"已写入 {len(req.items)} 个变量")


@router.delete("/kv/{key}", response_model=ApiResponse)
async def delete_kv(key: str, db: Session = Depends(get_db)):
    entry = db.query(KvEntry).filter(KvEntry.key == key).first()
    if entry:
        _log_history(db, key, entry.value, "(已删除)", "admin")
        db.delete(entry)
        db.commit()
        await broadcast("kv.deleted", {"key": key})
    return ApiResponse(success=True, message="OK")


@router.post("/kv/batch-delete", response_model=ApiResponse)
def batch_delete_kv(req: KvBatchDeleteRequest, db: Session = Depends(get_db)):
    for key in req.keys:
        delete_kv(key, db)
    return ApiResponse(success=True, message=f"已删除 {len(req.keys)} 个变量")


@router.get("/kv/export")
def export_kv(prefix: str | None = Query(None), db: Session = Depends(get_db)):
    from fastapi.responses import StreamingResponse
    import io
    q = db.query(KvEntry)
    if prefix:
        q = q.filter(KvEntry.key.like(f"{prefix}%"))
    data = [{c.name: getattr(r, c.name) for c in KvEntry.__table__.columns} for r in q.all()]
    buf = io.BytesIO(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
    return StreamingResponse(buf, media_type="application/json",
                             headers={"Content-Disposition": "attachment; filename=kv_export.json"})


@router.post("/kv/import", response_model=ApiResponse)
async def import_kv(file: __import__("fastapi").UploadFile, db: Session = Depends(get_db)):
    content = await file.read()
    items = json.loads(content)
    count = 0
    for item in items:
        if "key" in item and "value" in item:
            set_kv(KvSetRequest(key=item["key"], value=str(item["value"]),
                                type=item.get("type", "string"),
                                source=item.get("source", "import"),
                                retention_days=item.get("retention_days", 180)), db)
            count += 1
    return ApiResponse(success=True, message=f"已导入 {count} 个变量")
