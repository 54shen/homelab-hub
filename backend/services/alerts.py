# ============================================================
# Shared Center — 告警检查服务
# ============================================================
import json
from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal
from models import AlertRule, KvEntry, Device, WebhookConfig
import httpx


def _trigger(rule: AlertRule, event_data: dict):
    """执行告警动作"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rule.last_triggered = now_str

    target = rule.action_target or ""

    # 记录日志（所有动作都记录）
    print(f"[Alert] 触发: {rule.name} | {rule.trigger_key} {rule.condition} {rule.threshold}")

    # Webhook 动作
    if rule.action == "webhook":
        if not target:
            return
        db = SessionLocal()
        try:
            # 解析 webhook ID
            if target.startswith("webhook:"):
                wh_id = int(target.split(":")[1])
                wh = db.query(WebhookConfig).filter(WebhookConfig.id == wh_id, WebhookConfig.enabled == True).first()
                if wh:
                    _send_webhook(wh, rule, event_data, now_str)
            db.commit()
        except Exception as e:
            print(f"[Alert] Webhook 发送失败: {e}")
        finally:
            db.close()


def _send_webhook(wh: WebhookConfig, rule: AlertRule, event_data: dict, now_str: str):
    """发送单个 Webhook"""
    from routers.webhooks import _build_payload

    event = "alert.triggered"
    payload_data = {
        "alert": rule.name,
        "key": rule.trigger_key,
        "condition": rule.condition,
        "threshold": rule.threshold,
        **event_data
    }

    # 构建 payload（包含额外告警上下文）
    if wh.body and wh.body.strip():
        body_str = wh.body
        body_str = body_str.replace("{{event}}", event)
        body_str = body_str.replace("{{timestamp}}", now_str)
        body_str = body_str.replace("{{webhook}}", wh.name)
        body_str = body_str.replace("{{data}}", json.dumps(payload_data, ensure_ascii=False))
        try:
            payload = json.loads(body_str)
        except json.JSONDecodeError:
            payload = {"event": event, "data": payload_data, "timestamp": now_str}
    else:
        payload = {"event": event, "data": payload_data, "timestamp": now_str, "webhook": wh.name}

    try:
        method = wh.method.upper()
        if method == "GET":
            resp = httpx.get(wh.url, headers=wh.headers, params=payload, timeout=10)
        elif method == "PUT":
            resp = httpx.put(wh.url, headers=wh.headers, json=payload, timeout=10)
        else:
            resp = httpx.post(wh.url, headers=wh.headers, json=payload, timeout=10)

        wh.last_sent = now_str
        if resp.status_code >= 400:
            wh.fail_count += 1
        else:
            wh.fail_count = 0
    except Exception:
        wh.last_sent = now_str
        wh.fail_count += 1


def check_kv_change(key: str, old_value: str | None, new_value: str):
    """KV 值变更时检查告警规则"""
    db = SessionLocal()
    try:
        rules = db.query(AlertRule).filter(
            AlertRule.enabled == True,
            AlertRule.trigger_key == key,
            AlertRule.condition.in_(["eq", "neq", "gt", "lt", "changed"])
        ).all()

        for rule in rules:
            triggered = False
            event_data = {"key": key, "old_value": old_value, "new_value": new_value}

            try:
                if rule.condition == "changed":
                    triggered = True
                elif rule.condition == "eq":
                    triggered = str(new_value) == str(rule.threshold)
                elif rule.condition == "neq":
                    triggered = str(new_value) != str(rule.threshold)
                elif rule.condition == "gt":
                    triggered = float(new_value) > float(rule.threshold)
                elif rule.condition == "lt":
                    triggered = float(new_value) < float(rule.threshold)
            except (ValueError, TypeError):
                pass  # 无法比较，跳过

            if triggered:
                _trigger(rule, event_data)
                db.commit()
    except Exception as e:
        print(f"[Alert] 检查出错: {e}")
        db.rollback()
    finally:
        db.close()


def check_device_offline_alert(device_name: str):
    """设备离线时检查告警规则"""
    db = SessionLocal()
    try:
        trigger_key = f"__device__:{device_name}"
        rules = db.query(AlertRule).filter(
            AlertRule.enabled == True,
            AlertRule.trigger_key == trigger_key,
            AlertRule.condition == "offline"
        ).all()

        for rule in rules:
            device = db.query(Device).filter(Device.name == device_name).first()
            event_data = {
                "device": device_name,
                "status": "offline",
                "last_heartbeat": device.last_heartbeat if device else "",
                "ip": device.ip if device else ""
            }
            _trigger(rule, event_data)
            db.commit()
    except Exception as e:
        print(f"[Alert] 离线检查出错: {e}")
        db.rollback()
    finally:
        db.close()
