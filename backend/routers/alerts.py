# ============================================================
# Shared Center — 告警规则 API
# ============================================================
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import AlertRule
from schemas import AlertRuleCreate, AlertRuleUpdate, AlertRuleToggle, AlertRuleOut, ApiResponse

router = APIRouter(prefix="/api", tags=["告警规则"])


@router.get("/alerts", response_model=list[AlertRuleOut])
def list_alerts(db: Session = Depends(get_db)):
    return db.query(AlertRule).order_by(AlertRule.id.desc()).all()


@router.post("/alerts", response_model=ApiResponse)
def create_alert(req: AlertRuleCreate, db: Session = Depends(get_db)):
    rule = AlertRule(**req.dict())
    db.add(rule)
    db.commit()
    return ApiResponse(success=True, message="已创建")


@router.put("/alerts/{rule_id}", response_model=ApiResponse)
def update_alert(rule_id: int, req: AlertRuleUpdate, db: Session = Depends(get_db)):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, "规则不存在")
    for k, v in req.dict(exclude_none=True).items():
        setattr(rule, k, v)
    db.commit()
    return ApiResponse(success=True, message="已更新")


@router.post("/alerts/{rule_id}/toggle", response_model=ApiResponse)
def toggle_alert(rule_id: int, req: AlertRuleToggle, db: Session = Depends(get_db)):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, "规则不存在")
    rule.enabled = req.enabled
    db.commit()
    return ApiResponse(success=True, message="OK")


@router.delete("/alerts/{rule_id}", response_model=ApiResponse)
def delete_alert(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if rule:
        db.delete(rule)
        db.commit()
    return ApiResponse(success=True, message="已删除")
