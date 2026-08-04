# ============================================================
# 告警模块测试:规则 CRUD + 条件触发逻辑
# (动作统一用 "log" — 只写系统日志,不触发真实网络请求)
# ============================================================
from models import SystemLog
from services.alerts import check_kv_change


def test_alert_rule_crud(client, admin_headers):
    r = client.post("/api/alerts", json={
        "name": "温度过高", "trigger_key": "room.temp",
        "condition": "gt", "threshold": "30", "action": "log"
    }, headers=admin_headers)
    assert r.status_code == 200

    rules = client.get("/api/alerts", headers=admin_headers).json()
    assert len(rules) == 1
    rid = rules[0]["id"]

    # 更新
    r = client.put(f"/api/alerts/{rid}", json={"threshold": "35"}, headers=admin_headers)
    assert r.status_code == 200

    # 开关
    r = client.post(f"/api/alerts/{rid}/toggle", json={"enabled": False}, headers=admin_headers)
    assert r.status_code == 200
    assert client.get("/api/alerts", headers=admin_headers).json()[0]["enabled"] is False

    # 删除
    assert client.delete(f"/api/alerts/{rid}", headers=admin_headers).status_code == 200
    assert client.get("/api/alerts", headers=admin_headers).json() == []

    # 不存在的规则 → 404
    assert client.put("/api/alerts/999", json={"threshold": "1"}, headers=admin_headers).status_code == 404
    assert client.post("/api/alerts/999/toggle", json={"enabled": True}, headers=admin_headers).status_code == 404


def test_eq_condition_triggers_log(client, admin_headers, db):
    client.post("/api/alerts", json={
        "name": "等于1", "trigger_key": "k.v", "condition": "eq", "threshold": "1", "action": "log"
    }, headers=admin_headers)
    check_kv_change("k.v", "0", "1")     # 触发
    check_kv_change("k.v", "1", "2")     # 不触发(2 != 1)
    logs = db.query(SystemLog).filter(SystemLog.module == "alert").all()
    assert len(logs) == 1
    assert "等于1" in logs[0].message


def test_gt_lt_conditions(client, admin_headers, db):
    client.post("/api/alerts", json={
        "name": "大于10", "trigger_key": "m.v", "condition": "gt", "threshold": "10", "action": "log"
    }, headers=admin_headers)
    client.post("/api/alerts", json={
        "name": "小于5", "trigger_key": "m.v", "condition": "lt", "threshold": "5", "action": "log"
    }, headers=admin_headers)

    check_kv_change("m.v", "0", "20")    # 触发 大于10
    check_kv_change("m.v", "20", "3")    # 触发 小于5
    check_kv_change("m.v", "3", "7")     # 都不触发
    logs = db.query(SystemLog).filter(SystemLog.module == "alert").all()
    assert len(logs) == 2


def test_neq_condition(client, admin_headers, db):
    client.post("/api/alerts", json={
        "name": "不等于off", "trigger_key": "s.v", "condition": "neq", "threshold": "off", "action": "log"
    }, headers=admin_headers)
    check_kv_change("s.v", "on", "off")   # 等于 → 不触发
    check_kv_change("s.v", "off", "on")   # 不等于 → 触发
    assert db.query(SystemLog).filter(SystemLog.module == "alert").count() == 1


def test_changed_condition(client, admin_headers, db):
    client.post("/api/alerts", json={
        "name": "变化即触发", "trigger_key": "c.v", "condition": "changed", "threshold": "", "action": "log"
    }, headers=admin_headers)
    check_kv_change("c.v", "1", "2")
    assert db.query(SystemLog).filter(SystemLog.module == "alert").count() == 1


def test_non_numeric_compare_is_safe(client, admin_headers, db):
    """阈值不是数字时 gt/lt 比较抛 ValueError → 静默跳过,不崩溃"""
    client.post("/api/alerts", json={
        "name": "文本阈值", "trigger_key": "t.v", "condition": "gt", "threshold": "abc", "action": "log"
    }, headers=admin_headers)
    check_kv_change("t.v", "x", "10")
    assert db.query(SystemLog).count() == 0


def test_disabled_rule_not_triggered(client, admin_headers, db):
    r = client.post("/api/alerts", json={
        "name": "已停用", "trigger_key": "d.v", "condition": "changed", "threshold": "", "action": "log"
    }, headers=admin_headers)
    rid = client.get("/api/alerts", headers=admin_headers).json()[0]["id"]
    client.post(f"/api/alerts/{rid}/toggle", json={"enabled": False}, headers=admin_headers)
    check_kv_change("d.v", "1", "2")
    assert db.query(SystemLog).filter(SystemLog.module == "alert").count() == 0
