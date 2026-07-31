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
import json

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


def _build_payload(wh: WebhookConfig, event: str, event_data: dict | None = None) -> dict:
    """构建 Webhook 请求体，使用自定义 Body 模板"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    default = {"event": event, "webhook": wh.name, "timestamp": now_str}

    if wh.body and wh.body.strip():
        try:
            body = json.loads(wh.body)
        except json.JSONDecodeError:
            return default

        # 标签映射
        labels = {
            "alert": "告警规则", "key": "监控变量", "condition": "触发条件",
            "threshold": "阈值", "old_value": "旧值", "new_value": "新值",
            "elapsed_seconds": "已过秒数", "value_time": "上报时间", "updated_at": "最后更新"
        }

        # 构建 data 文本
        if event_data:
            lines = []
            for k, v in event_data.items():
                if v is None or v == "":
                    continue
                label = labels.get(k, k)
                lines.append(f"- {label}：{v}")
            data_text = "\n".join(lines) if lines else "(无详情)"
        else:
            data_text = ""

        # 递归替换所有字符串值中的 {{…}} 占位符
        def replace_placeholders(obj):
            if isinstance(obj, str):
                obj = obj.replace("{{event}}", event)
                obj = obj.replace("{{timestamp}}", now_str)
                obj = obj.replace("{{webhook}}", wh.name)
                obj = obj.replace("{{data}}", data_text)
                return obj
            elif isinstance(obj, dict):
                return {k: replace_placeholders(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_placeholders(item) for item in obj]
            return obj

        return replace_placeholders(body)
    return default


@router.post("/webhooks/{webhook_id}/test", response_model=ApiResponse)
async def test_webhook(webhook_id: int, db: Session = Depends(get_db), token=Depends(auth_write)):
    wh = db.query(WebhookConfig).filter(WebhookConfig.id == webhook_id).first()
    if not wh:
        raise HTTPException(404, "Webhook 不存在")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            method = wh.method.upper()
            payload = _build_payload(wh, "test")

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
