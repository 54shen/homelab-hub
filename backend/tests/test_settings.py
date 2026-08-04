# ============================================================
# 设置模块测试:历史清理/备份/恢复/系统配置/UI 设置
# ============================================================
import json

from models import KvEntry, KvHistory


def test_clean_history(client, admin_headers, db):
    db.add(KvHistory(key="k", old_value=None, new_value="1"))
    db.commit()
    r = client.post("/api/settings/clean-history", headers=admin_headers)
    assert r.status_code == 200
    assert "已清理 1" in r.json()["message"]


def test_backup_excludes_password_hash(client, admin_headers, db):
    db.add(KvEntry(key="b.k", value="v"))
    db.commit()
    r = client.get("/api/settings/backup", headers=admin_headers)
    data = r.json()
    assert data["version"] == "2.0"
    assert any(k["key"] == "b.k" for k in data["kv"])
    assert data["users"]                       # 默认 admin 用户存在
    assert all("password_hash" not in u for u in data["users"])   # 不导出密码


def test_restore_incremental_and_dedupe(client, admin_headers):
    backup = {
        "kv": [{"key": "r.k1", "value": "1", "type": "string", "source": "restore", "retention_days": 180}],
        "devices": [{"name": "恢复设备", "online": "True", "heartbeat_timeout": "100"}],
        "webhooks": [{"name": "恢复Webhook", "url": "http://localhost:1/h"}],
        "alert_rules": [{"name": "恢复规则", "trigger_key": "r.k1", "condition": "eq", "threshold": "1"}],
        "tokens": [{"name": "恢复Token", "token": "sk-restore-1", "permission": "read"}],
        "users": [{"username": "恢复用户", "permission": "read"}],
    }
    payload = ("backup.json", json.dumps(backup).encode(), "application/json")

    r = client.post("/api/settings/restore", files={"file": payload}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["success"] is True
    assert "KV×1" in r.json()["message"]

    # 各类数据都恢复了(KV 列表实际路由是 /api/list)
    assert any(e["key"] == "r.k1" for e in client.get("/api/list", headers=admin_headers).json())
    assert any(d["name"] == "恢复设备" for d in client.get("/api/devices", headers=admin_headers).json())
    assert any(w["name"] == "恢复Webhook" for w in client.get("/api/webhooks", headers=admin_headers).json())
    assert any(a["name"] == "恢复规则" for a in client.get("/api/alerts", headers=admin_headers).json())
    assert any(t["name"] == "恢复Token" for t in client.get("/api/tokens", headers=admin_headers).json())
    assert any(u["username"] == "恢复用户" for u in client.get("/api/users", headers=admin_headers).json())

    # 再次恢复同一份 → 去重,不产生重复
    r = client.post("/api/settings/restore", files={"file": payload}, headers=admin_headers)
    assert r.json()["success"] is True
    assert len(client.get("/api/alerts", headers=admin_headers).json()) == 1


def test_restore_invalid_json(client, admin_headers):
    r = client.post("/api/settings/restore",
                    files={"file": ("bad.json", b"not json", "application/json")},
                    headers=admin_headers)
    assert r.status_code == 400


def test_system_config_get_put_restore(client, admin_headers):
    orig = client.get("/api/settings/system", headers=admin_headers).json()
    r = client.put("/api/settings/system",
                   json={"cleanup_interval_hours": 12, "heartbeat_timeout_seconds": 120},
                   headers=admin_headers)
    assert r.status_code == 200
    saved = client.get("/api/settings/system", headers=admin_headers).json()
    assert saved["cleanup_interval_hours"] == 12
    assert saved["heartbeat_timeout_seconds"] == 120
    # 还原,避免影响其他测试(配置是模块级变量)
    client.put("/api/settings/system", json=orig, headers=admin_headers)


def test_ui_settings_roundtrip(client, admin_headers):
    r = client.put("/api/settings/ui", json={"settings": {"theme": "dark", "lang": "zh"}}, headers=admin_headers)
    assert r.status_code == 200
    assert client.get("/api/settings/ui", headers=admin_headers).json() == {"theme": "dark", "lang": "zh"}

    # 部分更新 → 其他键保留
    client.put("/api/settings/ui", json={"settings": {"theme": "light"}}, headers=admin_headers)
    body = client.get("/api/settings/ui", headers=admin_headers).json()
    assert body["theme"] == "light" and body["lang"] == "zh"
