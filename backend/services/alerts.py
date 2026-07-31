# ============================================================
# Shared Center — 告警检查服务（实时触发版）
# ============================================================
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import SessionLocal
from models import AlertRule, KvEntry, Device, WebhookConfig
from services.scheduler import get_scheduler
import httpx


def _trigger(rule: AlertRule, event_data: dict):
    """执行告警动作（支持逗号分隔多动作，如 "webhook,log"）"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rule.last_triggered = now_str

    target = rule.action_target or ""
    actions = [a.strip() for a in rule.action.split(",") if a.strip()]

    print(f"[Alert] 触发: {rule.name} | {rule.trigger_key} {rule.condition} {rule.threshold} | actions={actions}")

    if "log" in actions:
        _write_alert_log(rule, event_data, now_str)

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
    from routers.webhooks import _build_payload, resolve_url

    event = "alert.triggered"
    payload_data = {
        "alert": rule.name,
        "key": rule.trigger_key,
        "condition": rule.condition,
        "threshold": rule.threshold,
        **event_data,
        "通知时间": now_str
    }

    payload = _build_payload(wh, event, payload_data, rule_body_template=rule.body or None)
    url = resolve_url(wh.url, wh.name, event, payload_data)

    try:
        method = wh.method.upper()
        if method == "GET":
            resp = httpx.get(url, headers=wh.headers, params=payload, timeout=10)
        elif method == "PUT":
            resp = httpx.put(url, headers=wh.headers, json=payload, timeout=10)
        else:
            resp = httpx.post(url, headers=wh.headers, json=payload, timeout=10)

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


# ============================================================
# 实时检查：KV 写入时同步调用
# ============================================================

def check_kv_change(key: str, old_value: str | None, new_value: str):
    """KV 值变更时检查告警规则（所有条件统一在此实时处理）"""
    db = SessionLocal()
    try:
        rules = db.query(AlertRule).filter(
            AlertRule.enabled == True,
            AlertRule.trigger_key == key,
            AlertRule.condition.in_(["eq", "neq", "gt", "lt", "changed", "stale", "unchanged"])
        ).all()

        print(f"[Alert] check_kv_change: key={key} old={old_value} new={new_value} matched_rules={len(rules)}")

        for rule in rules:
            triggered = False
            event_data = {"key": key, "old_value": old_value, "new_value": new_value, "condition": rule.condition}

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
                elif rule.condition == "stale":
                    # 写入时预约阈值秒后精确触发
                    _schedule_stale_check(rule, new_value)
                elif rule.condition == "unchanged":
                    # 写入时预约阈值秒后精确触发
                    _schedule_unchanged_check(rule, key)
            except (ValueError, TypeError):
                pass

            if triggered:
                _trigger(rule, event_data)
                db.commit()
    except Exception as e:
        print(f"[Alert] 检查出错: {e}")
        db.rollback()
    finally:
        db.close()


# ============================================================
# 一次性预约调度（stale / unchanged / offline）
# ============================================================

def _parse_iso_timestamp(value_str: str) -> datetime | None:
    """解析 ISO 8601 时间戳，失败返回 None"""
    try:
        s = value_str.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        return None


def _schedule_stale_check(rule: AlertRule, value_str: str):
    """写入时预约 stale 检查：value_time + threshold 秒后验证并触发"""
    try:
        threshold_seconds = int(rule.threshold)
    except (ValueError, TypeError):
        return

    value_time = _parse_iso_timestamp(value_str)
    if value_time is None:
        return

    trigger_at = value_time + timedelta(seconds=threshold_seconds)
    job_id = f"stale_{rule.id}_{rule.trigger_key}"

    sched = get_scheduler()
    if sched.get_job(job_id):
        sched.remove_job(job_id)

    now = datetime.now()
    if trigger_at <= now:
        # 已经超时，立刻触发
        print(f"[Alert] stale 预约: {rule.name} 已超时，立即触发 (value={value_str}, threshold={threshold_seconds}s)")
        _execute_scheduled_stale(rule.id)
    else:
        delay = (trigger_at - now).total_seconds()
        print(f"[Alert] stale 预约: {rule.name} 将在 {delay:.0f} 秒后检查 (value={value_str}, threshold={threshold_seconds}s)")
        sched.add_job(
            _execute_scheduled_stale,
            'date',
            run_date=trigger_at,
            args=[rule.id],
            id=job_id,
            replace_existing=True
        )


def _schedule_unchanged_check(rule: AlertRule, key: str):
    """写入时预约 unchanged 检查：now + threshold 秒后验证是否仍无更新"""
    try:
        threshold_seconds = int(rule.threshold)
    except (ValueError, TypeError):
        return

    trigger_at = datetime.now() + timedelta(seconds=threshold_seconds)
    job_id = f"unchanged_{rule.id}_{key}"

    sched = get_scheduler()
    if sched.get_job(job_id):
        sched.remove_job(job_id)

    delay = threshold_seconds
    print(f"[Alert] unchanged 预约: {rule.name} 将在 {delay}s 后检查是否仍无更新")
    sched.add_job(
        _execute_scheduled_unchanged,
        'date',
        run_date=trigger_at,
        args=[rule.id, key],
        id=job_id,
        replace_existing=True
    )


# ---- 调度器回调（到时间后验证条件并触发）----

def _execute_scheduled_stale(rule_id: int):
    """stale 预约到期：重新验证 value_time + threshold <= now"""
    db = SessionLocal()
    try:
        rule = db.query(AlertRule).filter(AlertRule.id == rule_id, AlertRule.enabled == True).first()
        if not rule:
            return

        try:
            threshold_seconds = int(rule.threshold)
        except (ValueError, TypeError):
            return

        kv = db.query(KvEntry).filter(KvEntry.key == rule.trigger_key).first()
        if not kv or not kv.value:
            return

        value_time = _parse_iso_timestamp(kv.value)
        if value_time is None:
            return

        elapsed = (datetime.now() - value_time).total_seconds()
        if elapsed >= threshold_seconds:
            print(f"[Alert] stale 到期触发: {rule.name} elapsed={int(elapsed)}s >= threshold={threshold_seconds}s")
            _trigger(rule, {
                "key": rule.trigger_key,
                "elapsed_seconds": int(elapsed),
                "value_time": kv.value,
                "condition": "stale"
            })
            db.commit()
    except Exception as e:
        print(f"[Alert] stale 预约触发失败: {e}")
        db.rollback()
    finally:
        db.close()


def _execute_scheduled_unchanged(rule_id: int, key: str):
    """unchanged 预约到期：验证 updated_at 是否仍然超过阈值"""
    db = SessionLocal()
    try:
        rule = db.query(AlertRule).filter(AlertRule.id == rule_id, AlertRule.enabled == True).first()
        if not rule:
            return

        try:
            threshold_seconds = int(rule.threshold)
        except (ValueError, TypeError):
            return

        kv = db.query(KvEntry).filter(KvEntry.key == key).first()
        if not kv or not kv.updated_at:
            return

        try:
            updated_at = datetime.strptime(kv.updated_at, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return

        elapsed = (datetime.now() - updated_at).total_seconds()
        if elapsed >= threshold_seconds:
            print(f"[Alert] unchanged 到期触发: {rule.name} elapsed={int(elapsed)}s >= threshold={threshold_seconds}s")
            _trigger(rule, {
                "key": key,
                "elapsed_seconds": int(elapsed),
                "updated_at": kv.updated_at,
                "condition": "unchanged"
            })
            db.commit()
    except Exception as e:
        print(f"[Alert] unchanged 预约触发失败: {e}")
        db.rollback()
    finally:
        db.close()


# ============================================================
# 设备离线告警 — 由心跳路径实时预约
# ============================================================

def schedule_offline_check(device_name: str, timeout_seconds: int):
    """心跳到达时预约离线检查：now + timeout 秒后验证"""
    if timeout_seconds <= 0:
        return

    trigger_at = datetime.now() + timedelta(seconds=timeout_seconds)
    job_id = f"offline_{device_name}"

    sched = get_scheduler()
    if sched.get_job(job_id):
        sched.remove_job(job_id)

    print(f"[Alert] offline 预约: {device_name} 将在 {timeout_seconds}s 后检查是否离线")
    sched.add_job(
        _execute_scheduled_offline,
        'date',
        run_date=trigger_at,
        args=[device_name, timeout_seconds],
        id=job_id,
        replace_existing=True
    )


def _execute_scheduled_offline(device_name: str, timeout_seconds: int):
    """离线预约到期：检查 last_heartbeat 是否超时，若超时则标记离线并触发告警"""
    db = SessionLocal()
    try:
        device = db.query(Device).filter(Device.name == device_name, Device.online == True).first()
        if not device:
            return

        try:
            last_hb = datetime.strptime(device.last_heartbeat, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return

        elapsed = (datetime.now() - last_hb).total_seconds()
        if elapsed >= timeout_seconds:
            device.online = False
            db.commit()
            print(f"[Alert] offline 到期触发: {device_name} 离线 (last_hb={device.last_heartbeat}, elapsed={int(elapsed)}s)")

            # 触发离线告警规则
            trigger_key = f"__device__:{device_name}"
            rules = db.query(AlertRule).filter(
                AlertRule.enabled == True,
                AlertRule.trigger_key == trigger_key,
                AlertRule.condition == "offline"
            ).all()
            for rule in rules:
                _trigger(rule, {
                    "device": device_name,
                    "status": "offline",
                    "last_heartbeat": device.last_heartbeat,
                    "ip": device.ip or "",
                    "elapsed_seconds": int(elapsed),
                    "condition": "offline"
                })
                db.commit()
    except Exception as e:
        print(f"[Alert] offline 预约触发失败: {e}")
        db.rollback()
    finally:
        db.close()
