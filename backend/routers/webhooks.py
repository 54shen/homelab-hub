# ============================================================
# Shared Center — Webhook 管理 API
# ============================================================
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import WebhookConfig
from schemas import WebhookCreate, WebhookUpdate, WebhookOut, ApiResponse
from auth import auth_write
import httpx

router = APIRouter(prefix="/api", tags=["Webhook"])


@router.get("/webhooks", response_model=list[WebhookOut])
def list_webhooks(db: Session = Depends(get_db)):
    return db.query(WebhookConfig).order_by(WebhookConfig.id.desc()).all()


@router.post("/webhooks", response_model=ApiResponse)
def create_webhook(req: WebhookCreate, db: Session = Depends(get_db), token=Depends(auth_write)):
    wh = WebhookConfig(**req.dict())
    db.add(wh)
    db.commit()
    return ApiResponse(success=True, message="已创建")


@router.put("/webhooks/{webhook_id}", response_model=ApiResponse)
def update_webhook(webhook_id: int, req: WebhookUpdate, db: Session = Depends(get_db), token=Depends(auth_write)):
    wh = db.query(WebhookConfig).filter(WebhookConfig.id == webhook_id).first()
    if not wh:
        raise HTTPException(404, "Webhook 不存在")
    for k, v in req.dict(exclude_none=True).items():
        setattr(wh, k, v)
    db.commit()
    return ApiResponse(success=True, message="已更新")


@router.delete("/webhooks/{webhook_id}", response_model=ApiResponse)
def delete_webhook(webhook_id: int, db: Session = Depends(get_db), token=Depends(auth_write)):
    wh = db.query(WebhookConfig).filter(WebhookConfig.id == webhook_id).first()
    if wh:
        db.delete(wh)
        db.commit()
    return ApiResponse(success=True, message="已删除")


@router.post("/webhooks/{webhook_id}/test", response_model=ApiResponse)
async def test_webhook(webhook_id: int, db: Session = Depends(get_db), token=Depends(auth_write)):
    wh = db.query(WebhookConfig).filter(WebhookConfig.id == webhook_id).first()
    if not wh:
        raise HTTPException(404, "Webhook 不存在")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            method = wh.method.upper()
            payload = {"event": "test", "webhook": wh.name, "timestamp": now_str}
            if method == "GET":
                resp = await client.get(wh.url, headers=wh.headers, params=payload)
            elif method == "PUT":
                resp = await client.put(wh.url, headers=wh.headers, json=payload)
            else:
                resp = await client.post(wh.url, headers=wh.headers, json=payload)

            wh.last_sent = now_str
            if resp.status_code >= 400:
                wh.fail_count += 1
                db.commit()
                return ApiResponse(success=False, message=f"请求失败 HTTP {resp.status_code}")
            wh.fail_count = 0
            db.commit()
            return ApiResponse(success=True, message=f"请求成功 HTTP {resp.status_code}")
    except Exception as e:
        wh.last_sent = now_str
        wh.fail_count += 1
        db.commit()
        return ApiResponse(success=False, message=f"连接失败: {str(e)}")
