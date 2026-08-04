# ============================================================
# Dashboard 模块测试:统计/最近变更/数据库状态/时间线
# ============================================================


def test_stats_empty(client, admin_headers):
    r = client.get("/api/dashboard/stats", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_devices"] == 0
    assert body["total_keys"] == 0
    assert body["system_health"] == 100
    assert body["network_status"] == "offline"


def test_stats_with_data(client, admin_headers):
    # 1 台在线 + 1 台离线设备
    client.post("/api/device/register", json={"name": "A", "type": "pc"}, headers=admin_headers)
    client.post("/api/device/heartbeat", json={"name": "A", "online": True}, headers=admin_headers)
    client.post("/api/device/register", json={"name": "B", "type": "pc"}, headers=admin_headers)
    # 服务 + 公网 IP
    client.post("/api/kv", json={"key": "service.web", "value": "running"}, headers=admin_headers)
    client.post("/api/kv", json={"key": "service.db", "value": "stopped"}, headers=admin_headers)
    client.post("/api/kv", json={"key": "network.public_ip", "value": "1.2.3.4"}, headers=admin_headers)

    body = client.get("/api/dashboard/stats", headers=admin_headers).json()
    assert body["total_devices"] == 2
    assert body["online_devices"] == 1
    assert body["total_services"] == 2
    assert body["running_services"] == 1
    # 注册设备会各自动创建一个 心跳超时 KV,所以总共 3+2=5 个 key
    assert body["total_keys"] == 5
    assert body["network_status"] == "online"
    assert body["public_ip"] == "1.2.3.4"
    assert body["system_health"] == 50


def test_recent_changes(client, admin_headers):
    client.post("/api/kv", json={"key": "dash.k", "value": "1"}, headers=admin_headers)
    r = client.get("/api/dashboard/recent", params={"limit": 5}, headers=admin_headers)
    assert r.status_code == 200
    assert any(item["key"] == "dash.k" for item in r.json())


def test_db_status(client, admin_headers):
    r = client.get("/api/dashboard/db-status", headers=admin_headers)
    body = r.json()
    assert body["total_keys"] == 0
    assert body["history_count"] == 0
    assert isinstance(body["file_size"], str)


def test_timeline_contains_device_heartbeat(client, admin_headers):
    client.post("/api/device/register", json={"name": "TL", "type": "pc"}, headers=admin_headers)
    r = client.get("/api/dashboard/timeline", headers=admin_headers)
    assert r.status_code == 200
    events = r.json()["events"]
    assert any(e["title"] == "TL 心跳" and e["description"] == "离线" for e in events)
