# ============================================================
# Shared Center — 告警检查服务
# ============================================================
import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from database import SessionLocal
from models import AlertRule, KvEntry, Device, WebhookConfig
import httpx


def _trigger(rule: AlertRule, event_data: dict):
    """执行告警动作（支持逗号分隔多动作，如 "webhook,log"）"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rule.last_triggered = now_str

    target = rule.action_target or ""
    actions = [a.strip() for a in rule.action.split(",") if a.strip()]

    # 日志动作（基础日志，始终打印）
    print(f"[Alert] 触发: {rule.name} | {rule.trigger_key} {rule.condition} {rule.threshold} | actions={actions}")

    # 正式日志动作
    if "log" in actions:
        _write_alert_log(rule, event_data, now_str)

    # Webhook 动作
    if "webhook" in actions:
        if not target:
            print(f"[Alert] Webhook 动作缺少 target，跳过")
            return
        db = SessionLocal()
        try:
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


def _write_alert_log(rule: AlertRule, event_data: dict, now_str: str):
    """写入告警日志到 system_logs 表"""
    from models import SystemLog
    db = SessionLocal()
    try:
        log_entry = SystemLog(
            level="warn",
            module="alert",
            message=f"告警触发: {rule.name}",
            detail=json.dumps({
                "rule_id": rule.id,
                "key": rule.trigger_key,
                "condition": rule.condition,
                "threshold": rule.threshold,
                **event_data
            }, ensure_ascii=False),
            created_at=now_str
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        print(f"[Alert] 日志写入失败: {e}")
        db.rollback()
    finally:
        db.close()


def _write_webhook_error(rule: AlertRule, wh: WebhookConfig, error: str, now_str: str):
    """写入 Webhook 发送失败日志到 system_logs 表"""
    from models import SystemLog
    db = SessionLocal()
    try:
        log_entry = SystemLog(
            level="error",
            module="webhook",
            message=f"Webhook 发送失败: {wh.name}",
            detail=json.dumps({
                "webhook_id": wh.id,
                "webhook_name": wh.name,
                "url": wh.url,
                "rule": rule.name,
                "key": rule.trigger_key,
                "error": error
            }, ensure_ascii=False),
            created_at=now_str
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        print(f"[Alert] Webhook 错误日志写入失败: {e}")
        db.rollback()
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
        **event_data,
        "通知时间": now_str
    }

    payload = _build_payload(wh, event, payload_data)

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
            err_msg = f"Webhook「{wh.name}」返回 HTTP {resp.status_code}: {resp.text[:200]}"
            print(f"[Alert] {err_msg}")
            _write_webhook_error(rule, wh, err_msg, now_str)
        else:
            wh.fail_count = 0
            print(f"[Alert] Webhook 发送成功: {resp.status_code}")
    except Exception as e:
        wh.last_sent = now_str
        wh.fail_count += 1
        err_msg = f"Webhook「{wh.name}」连接失败: {type(e).__name__}: {e}"
        print(f"[Alert] {err_msg}")
        _write_webhook_error(rule, wh, err_msg, now_str)


def check_kv_change(key: str, old_value: str | None, new_value: str):
    """KV 值变更时检查告警规则"""
    db = SessionLocal()
    try:
        rules = db.query(AlertRule).filter(
            AlertRule.enabled == True,
            AlertRule.trigger_key == key,
            AlertRule.condition.in_(["eq", "neq", "gt", "lt", "changed"])
        ).all()

        print(f"[Alert] check_kv_change: key={key} old={old_value} new={new_value} matched_rules={len(rules)}")

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


def check_stale_unchanged():
    """周期检查 stale（值超时 / ISO 8601）和 unchanged（久未更新）规则"""
    db = SessionLocal()
    try:
        rules = db.query(AlertRule).filter(
            AlertRule.enabled == True,
            AlertRule.condition.in_(["stale", "unchanged"])
        ).all()

        if not rules:
            return

        now = datetime.now()

        for rule in rules:
            try:
                threshold_seconds = int(rule.threshold)
            except (ValueError, TypeError):
                continue  # 阈值无效，跳过

            triggered = False
            event_data = {"key": rule.trigger_key}

            if rule.condition == "unchanged":
                # 检查 KV updated_at（元数据）
                kv = db.query(KvEntry).filter(KvEntry.key == rule.trigger_key).first()
                if kv and kv.updated_at:
                    try:
                        updated_at = datetime.strptime(kv.updated_at, "%Y-%m-%d %H:%M:%S")
                        elapsed = (now - updated_at).total_seconds()
                        if elapsed > threshold_seconds:
                            triggered = True
                            event_data["elapsed_seconds"] = int(elapsed)
                            event_data["updated_at"] = kv.updated_at
                    except ValueError:
                        pass

            elif rule.condition == "stale":
                # 解析 KV 值为 ISO 8601 时间戳
                kv = db.query(KvEntry).filter(KvEntry.key == rule.trigger_key).first()
                if kv and kv.value:
                    try:
                        value_str = kv.value.strip()
                        # 替换尾部 Z 为 +00:00，兼容 fromisoformat
                        if value_str.endswith("Z"):
                            value_str = value_str[:-1] + "+00:00"
                        value_time = datetime.fromisoformat(value_str)
                        # 去掉时区信息以便与 naive datetime 比较
                        if value_time.tzinfo is not None:
                            value_time = value_time.replace(tzinfo=None)
                        elapsed = (now - value_time).total_seconds()
                        if elapsed > threshold_seconds:
                            triggered = True
                            event_data["elapsed_seconds"] = int(elapsed)
                            event_data["value_time"] = kv.value
                    except (ValueError, TypeError):
                        pass  # 无法解析 ISO 8601，跳过

            if triggered:
                _trigger(rule, event_data)
                db.commit()
    except Exception as e:
        print(f"[Alert] stale/unchanged 检查出错: {e}")
        db.rollback()
    finally:
        db.close()
