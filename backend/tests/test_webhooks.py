# ============================================================
# Webhook 模块测试:CRUD / 模板变量解析 / 请求体构建 / 测试发送
# ============================================================
from models import WebhookConfig
from routers.webhooks import _build_payload, resolve_url


def test_webhook_crud(client, admin_headers):
    r = client.post("/api/webhooks", json={
        "name": "通知服务", "url": "http://localhost:9999/hook", "event_types": ["kv.changed"]
    }, headers=admin_headers)
    assert r.status_code == 200

    whs = client.get("/api/webhooks", headers=admin_headers).json()
    assert len(whs) == 1
    assert whs[0]["event_types"] == ["kv.changed"]
    wid = whs[0]["id"]

    # 更新
    assert client.put(f"/api/webhooks/{wid}", json={"enabled": False}, headers=admin_headers).status_code == 200
    assert client.get("/api/webhooks", headers=admin_headers).json()[0]["enabled"] is False

    # 删除
    assert client.delete(f"/api/webhooks/{wid}", headers=admin_headers).status_code == 200
    assert client.get("/api/webhooks", headers=admin_headers).json() == []

    # 不存在 → 404
    assert client.put("/api/webhooks/999", json={"enabled": True}, headers=admin_headers).status_code == 404


def test_preview_url_replaces_placeholders(client, admin_headers):
    """设备不存在 → {{ip:设备名}} 解析为空串"""
    r = client.post("/api/webhooks/preview-url",
                    json={"url": "http://{{ip:不存在的设备}}/api?e={{event}}"},
                    headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["url"] == "http:///api?e=preview"


def test_resolve_url_with_device_attr(client, admin_headers):
    """{{ip:设备名}} 从数据库解析设备 IP"""
    client.post("/api/device/register", json={"name": "测试机", "type": "pc"}, headers=admin_headers)
    client.post("/api/device/heartbeat", json={"name": "测试机", "online": True, "ip": "192.168.1.10"}, headers=admin_headers)
    url = resolve_url("http://{{ip:测试机}}/hook?e={{event}}", "测试wh", "kv.changed")
    assert url == "http://192.168.1.10/hook?e=kv.changed"


def test_build_payload_merges_and_replaces(client, admin_headers, db):
    """Body 信封 + Body+ 合并,{{event}}/{{key}}/{{alert}}/{{data}} 全部替换"""
    client.post("/api/kv", json={"key": "w.v", "value": "42"}, headers=admin_headers)

    wh = WebhookConfig(
        id=1, name="测试wh", url="x", method="POST", headers={},
        body='{"to_user": "{{event}}", "value": "{{w.v}}"}',
        body_extra='{"extra": "{{alert}}"}',
        event_types=["kv.changed"], enabled=True,
    )
    db.add(wh)
    db.commit()

    payload = _build_payload(wh, "kv.changed", event_data={"alert": "测试告警", "key": "w.v"})
    assert payload["to_user"] == "kv.changed"
    assert payload["value"] == "42"          # {{w.v}} 从 KV 表兜底解析
    assert payload["extra"] == "测试告警"      # {{alert}} 来自事件数据
    assert "event" in payload and "timestamp" in payload
    assert "{{" not in str(payload)          # 不应残留未替换的占位符


def test_build_payload_rule_body_overrides_extra(client, admin_headers, db):
    wh = WebhookConfig(
        id=1, name="测试wh2", url="x", method="POST", headers={},
        body='{"to_user": "a"}', body_extra='{"extra": "默认"}',
        event_types=[], enabled=True,
    )
    db.add(wh)
    db.commit()
    payload = _build_payload(wh, "evt", rule_body_template='{"extra": "规则覆盖"}')
    assert payload["extra"] == "规则覆盖"


def test_build_payload_non_json_extra_becomes_text(client, admin_headers, db):
    wh = WebhookConfig(
        id=1, name="测试wh3", url="x", method="POST", headers={},
        body="", body_extra="这是一段纯文本", event_types=[], enabled=True,
    )
    db.add(wh)
    db.commit()
    payload = _build_payload(wh, "evt")
    assert payload["text"] == "这是一段纯文本"


def test_test_webhook_connection_failed(client, admin_headers):
    """指向不可达地址 → 返回失败并累加 fail_count"""
    client.post("/api/webhooks", json={"name": "坏Hook", "url": "http://127.0.0.1:1/nope"}, headers=admin_headers)
    wid = client.get("/api/webhooks", headers=admin_headers).json()[0]["id"]

    r = client.post(f"/api/webhooks/{wid}/test", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["success"] is False
    wh = client.get("/api/webhooks", headers=admin_headers).json()[0]
    assert wh["fail_count"] == 1


def test_webhook_error_logged(client, admin_headers):
    """Webhook 测试失败 → 错误日志应写入 system_logs"""
    client.post("/api/webhooks", json={"name": "坏Hook", "url": "http://127.0.0.1:1/nope"}, headers=admin_headers)
    wid = client.get("/api/webhooks", headers=admin_headers).json()[0]["id"]
    client.post(f"/api/webhooks/{wid}/test", headers=admin_headers)
    logs = client.get("/api/logs", params={"module": "webhook"}, headers=admin_headers).json()
    assert logs["total"] >= 1
