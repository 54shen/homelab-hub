# ============================================================
# Shared Center — Webhook 管理 API
# ============================================================
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from models import WebhookConfig, Device
from schemas import WebhookCreate, WebhookUpdate, WebhookOut, ApiResponse
from auth import auth_write
import httpx
import json
import re

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


# 匹配 {{属性:设备名}} 语法，如 {{ip:大爷的ROG}}
_DEVICE_ATTR_RE = re.compile(r'\{\{(\w+):([^}]+)\}\}')


def _resolve_device_attrs(text: str) -> str:
    """解析 {{属性:设备名}} 语法，从数据库查询指定设备的属性值"""
    matches = list(_DEVICE_ATTR_RE.finditer(text))
    if not matches:
        return text

    db = SessionLocal()
    try:
        result = text
        for m in matches:
            attr = m.group(1)
            device_name = m.group(2).strip()
            device = db.query(Device).filter(Device.name == device_name).first()
            if device and hasattr(device, attr):
                val = getattr(device, attr)
                result = result.replace(m.group(0), str(val) if val is not None else "")
            else:
                result = result.replace(m.group(0), "")  # 找不到 → 空字符串
        return result
    finally:
        db.close()


def _resolve_text(text: str, wh_name: str, event: str, event_data: dict | None, now_str: str) -> str:
    """替换文本中所有 {{...}} 模板变量（不含 {{data}} 和 {{rule_body}}，这两个由 _build_payload 处理）"""
    result = text
    result = result.replace("{{event}}", event)
    result = result.replace("{{timestamp}}", now_str)
    result = result.replace("{{webhook}}", wh_name)
    if event_data:
        for k, v in event_data.items():
            if v is not None:
                result = result.replace("{{" + k + "}}", str(v))
    # 最后解析 {{属性:设备名}} 写死设备引用
    result = _resolve_device_attrs(result)
    return result


def resolve_url(url: str, wh_name: str, event: str, event_data: dict | None = None) -> str:
    """替换 URL 中所有 {{...}} 模板变量，支持拼接设备 IP 等"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return _resolve_text(url, wh_name, event, event_data, now_str)


def _build_payload(wh: WebhookConfig, event: str, event_data: dict | None = None, rule_body_template: str | None = None) -> dict:
    """构建 Webhook 请求体 — JSON 合并模式

    1. 解析 wh.body（强制字段）和 rule body+ / body_extra（告警字段）为 JSON
    2. 合并：{ ...default, ...base, ...extra }
    3. 递归替换所有 {{…}} 占位符
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    default = {"event": event, "webhook": wh.name, "timestamp": now_str}

    # ---- 解析 JSON ----
    def _parse_json(raw: str | None) -> dict:
        if raw and raw.strip():
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass
        return {}

    base = _parse_json(wh.body)            # Body (强制字段，如 to_user)
    content_template = (rule_body_template and rule_body_template.strip()) or (wh.body_extra and wh.body_extra.strip()) or ""
    extra = _parse_json(content_template)   # Body+ (告警字段)
    if not extra and content_template:
        # 非 JSON 文本 → 包裹为 text 字段
        extra = {"text": content_template}

    # ---- 合并 JSON ----
    merged = {**default, **base, **extra}

    # ---- 构建 {{data}} 文本（兼容旧版） ----
    labels = {
        "alert": "告警规则", "key": "监控变量", "condition": "触发条件",
        "threshold": "阈值", "old_value": "旧值", "new_value": "新值",
        "elapsed_seconds": "已过秒数", "value_time": "上报时间", "updated_at": "最后更新"
    }
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

    # ---- 递归替换所有 {{…}} 占位符 ----
    def replace_placeholders(obj):
        if isinstance(obj, str):
            obj = _resolve_text(obj, wh.name, event, event_data, now_str)
            obj = obj.replace("{{data}}", data_text)
            return obj
        elif isinstance(obj, dict):
            return {k: replace_placeholders(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [replace_placeholders(item) for item in obj]
        return obj

    return replace_placeholders(merged)
    return default


@router.post("/webhooks/{webhook_id}/test", response_model=ApiResponse)
async def test_webhook(webhook_id: int, db: Session = Depends(get_db), token=Depends(auth_write)):
    wh = db.query(WebhookConfig).filter(WebhookConfig.id == webhook_id).first()
    if not wh:
        raise HTTPException(404, "Webhook 不存在")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    event_data = {
        "alert": "【测试告警】", "key": "test.variable", "condition": "eq",
        "threshold": "99", "old_value": "old_val", "new_value": "new_val",
        "elapsed_seconds": "0", "value_time": now_str, "updated_at": now_str,
        "device": "test-device", "status": "online", "last_heartbeat": now_str,
        "ip": "127.0.0.1", "通知时间": now_str
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            method = wh.method.upper()
            # 测试时填充 mock 数据，避免 {{变量}} 原样发送
            payload = _build_payload(wh, "test", event_data=event_data)
            url = resolve_url(wh.url, wh.name, "test", event_data)

            if method == "GET":
                resp = await client.get(url, headers=wh.headers, params=payload)
            elif method == "PUT":
                resp = await client.put(url, headers=wh.headers, json=payload)
            else:
                resp = await client.post(url, headers=wh.headers, json=payload)

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
