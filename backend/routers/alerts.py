# ============================================================
# Shared Center — 告警规则 API
# ============================================================
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import AlertRule
from schemas import AlertRuleCreate, AlertRuleUpdate, AlertRuleToggle, AlertRuleOut, ApiResponse
from auth import auth_write
from websocket_manager import broadcast

router = APIRouter(prefix="/api", tags=["告警规则"])


def _alert_to_dict(rule: AlertRule) -> dict:
    return {
        "id": rule.id, "name": rule.name, "description": rule.description,
        "trigger_key": rule.trigger_key, "condition": rule.condition,
        "threshold": rule.threshold, "action": rule.action,
        "action_target": rule.action_target, "enabled": rule.enabled,
        "last_triggered": rule.last_triggered, "body": rule.body
    }


def _ensure_webhook_target(action: str | None, action_target: str | None) -> None:
    """防呆:选了 webhook 动作必须至少指定一个 Webhook 通知渠道,否则 400"""
    actions = [a.strip() for a in (action or "").split(",") if a.strip()]
    if "webhook" in actions and not (action_target or "").strip():
        raise HTTPException(400, "选择 Webhook 动作时必须指定 Webhook 通知渠道")


@router.get("/alerts", response_model=list[AlertRuleOut])
def list_alerts(db: Session = Depends(get_db)):
    return db.query(AlertRule).order_by(AlertRule.id.desc()).all()


@router.post("/alerts", response_model=ApiResponse)
async def create_alert(req: AlertRuleCreate, db: Session = Depends(get_db), token=Depends(auth_write)):
    _ensure_webhook_target(req.action, req.action_target)
    rule = AlertRule(**req.dict())
    db.add(rule)
    db.commit()
    await broadcast("alert.created", _alert_to_dict(rule))
    return ApiResponse(success=True, message="已创建")


@router.put("/alerts/{rule_id}", response_model=ApiResponse)
async def update_alert(rule_id: int, req: AlertRuleUpdate, db: Session = Depends(get_db), token=Depends(auth_write)):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, "规则不存在")
    # 防呆:按合并后的最终状态校验(部分更新)
    new_action = req.action if req.action is not None else rule.action
    new_target = req.action_target if req.action_target is not None else (rule.action_target or "")
    _ensure_webhook_target(new_action, new_target)
    for k, v in req.dict(exclude_none=True).items():
        setattr(rule, k, v)
    db.commit()
    await broadcast("alert.updated", _alert_to_dict(rule))
    return ApiResponse(success=True, message="已更新")


@router.post("/alerts/{rule_id}/toggle", response_model=ApiResponse)
async def toggle_alert(rule_id: int, req: AlertRuleToggle, db: Session = Depends(get_db), token=Depends(auth_write)):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, "规则不存在")
    rule.enabled = req.enabled
    db.commit()
    await broadcast("alert.updated", _alert_to_dict(rule))
    return ApiResponse(success=True, message="OK")


@router.delete("/alerts/{rule_id}", response_model=ApiResponse)
async def delete_alert(rule_id: int, db: Session = Depends(get_db), token=Depends(auth_write)):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if rule:
        db.delete(rule)
        db.commit()
        await broadcast("alert.deleted", {"id": rule_id})
    return ApiResponse(success=True, message="已删除")
