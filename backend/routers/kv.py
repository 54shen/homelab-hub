# ============================================================
# Shared Center — KV 变量 API
# ============================================================
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from websocket_manager import broadcast
from database import get_db
from models import KvEntry, KvHistory
from schemas import (
    KvSetRequest, KvBatchRequest, KvBatchDeleteRequest,
    KvEntryOut, ApiResponse
)
from auth import auth_write
from constants import is_clipboard_key
import json

router = APIRouter(prefix="/api", tags=["KV 变量"])


# ---- 内部同步实现（供批量操作复用） ----

def _set_kv_sync(req: KvSetRequest, db: Session):
    """写入变量（同步，不广播）→ 返回 (now_str, changed, old_value)

    值无变化时完全静默：不写 history、不更新 entry。
    """
    # autoflush=False 时,先 flush 让同一会话内刚写入的 key 对后续查询可见
    # (否则批量写入中重复 key 会走"新建"分支 → UNIQUE 冲突)
    db.flush()
    entry = db.query(KvEntry).filter(KvEntry.key == req.key).first()
    now_str = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if entry:
        old = entry.value
        new_val = str(req.value)
        # ---- 值没变 → 什么都不做 ----
        if old == new_val:
            return now_str, False, old

        # ---- 值变更 → 更新 entry + 触发告警 ----
        from services.alerts import check_kv_change
        check_kv_change(req.key, old, new_val)

        entry.value = new_val
        entry.type = req.type
        entry.source = req.source
        entry.retention_days = req.retention_days
        entry.updated_at = now_str
        if req.expire_seconds is not None:
            entry.expire_seconds = req.expire_seconds
        # 记录历史（retention_days 从 entry 快照）
        db.add(KvHistory(
            key=req.key, old_value=old, new_value=new_val,
            source=req.source, retention_days=entry.retention_days,
            changed_at=now_str
        ))
        return now_str, True, old

    # ---- 新 key → 创建 entry ----
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
    # 记录历史（新建 key，old_value=None）
    db.add(KvHistory(
        key=req.key, old_value=None, new_value=str(req.value),
        source=req.source, retention_days=req.retention_days,
        changed_at=now_str
    ))
    return now_str, True, None


def _delete_kv_sync(key: str, db: Session):
    """删除变量（同步，不广播）"""
    entry = db.query(KvEntry).filter(KvEntry.key == key).first()
    if entry:
        db.delete(entry)


# ---- 路由 ----

@router.get("/list", response_model=list[KvEntryOut])
def list_kv(prefix: str | None = Query(None), db: Session = Depends(get_db)):
    q = db.query(KvEntry)
    if prefix:
        q = q.filter(KvEntry.key.like(f"{prefix}%"))
    return q.order_by(KvEntry.updated_at.desc()).all()


# 注意:导出路由必须注册在 GET /kv/{key} 之前,否则 key="export" 会被 {key} 抢先匹配
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


@router.get("/kv/{key}", response_model=KvEntryOut)
def get_kv(key: str, db: Session = Depends(get_db)):
    entry = db.query(KvEntry).filter(KvEntry.key == key).first()
    if not entry:
        from fastapi import HTTPException
        raise HTTPException(404, f"变量 '{key}' 不存在")
    return entry


@router.post("/kv", response_model=ApiResponse)
async def set_kv(req: KvSetRequest, db: Session = Depends(get_db), token=Depends(auth_write)):
    now_str, changed, old_value = _set_kv_sync(req, db)
    db.commit()

    # 心跳超时 KV 同步到 Device 表
    if req.key.endswith(".心跳超时"):
        try:
            device_name = req.key.rsplit(".", 1)[0]
            from models import Device
            dev = db.query(Device).filter(Device.name == device_name).first()
            if dev:
                dev.heartbeat_timeout = int(req.value)
                db.commit()
        except (ValueError, Exception):
            pass

    # 只有值真正变化时才广播 WS（静态 key 的重复上报不会触发前端更新）
    if changed:
        await broadcast("kv.changed", {"key": req.key, "value": str(req.value), "old_value": old_value, "source": req.source, "changed_at": now_str})
    return ApiResponse(success=True, message="OK")


@router.post("/kv/batch", response_model=ApiResponse)
def batch_set_kv(req: KvBatchRequest, db: Session = Depends(get_db), token=Depends(auth_write)):
    for item in req.items:
        _set_kv_sync(item, db)
    db.commit()
    return ApiResponse(success=True, message=f"已写入 {len(req.items)} 个变量")


@router.delete("/kv/{key}", response_model=ApiResponse)
async def delete_kv(key: str, db: Session = Depends(get_db), token=Depends(auth_write)):
    if is_clipboard_key(key):
        raise HTTPException(403, "剪切板为内置变量，不允许删除")
    _delete_kv_sync(key, db)
    db.commit()
    await broadcast("kv.deleted", {"key": key})
    return ApiResponse(success=True, message="OK")


@router.post("/kv/batch-delete", response_model=ApiResponse)
def batch_delete_kv(req: KvBatchDeleteRequest, db: Session = Depends(get_db), token=Depends(auth_write)):
    # 内置变量（剪切板）跳过，不允许删除
    keys = [k for k in req.keys if not is_clipboard_key(k)]
    skipped = len(req.keys) - len(keys)
    for key in keys:
        _delete_kv_sync(key, db)
    db.commit()
    msg = f"已删除 {len(keys)} 个变量"
    if skipped:
        msg += f"（已跳过 {skipped} 个内置变量）"
    return ApiResponse(success=True, message=msg)


@router.post("/kv/import", response_model=ApiResponse)
async def import_kv(file: __import__("fastapi").UploadFile, db: Session = Depends(get_db), token=Depends(auth_write)):
    content = await file.read()
    items = json.loads(content)
    count = 0
    for item in items:
        if "key" in item and "value" in item:
            _set_kv_sync(KvSetRequest(
                key=item["key"], value=str(item["value"]),
                type=item.get("type", "string"),
                source=item.get("source", "import"),
                retention_days=item.get("retention_days", 180)
            ), db)
            count += 1
    db.commit()
    return ApiResponse(success=True, message=f"已导入 {count} 个变量")
