# ============================================================
# 设备管理模块测试:注册/心跳/变量/注销
# ============================================================


def test_register_new_device(client, admin_headers):
    r = client.post("/api/device/register", json={"name": "书房电脑", "type": "pc"}, headers=admin_headers)
    assert r.status_code == 200
    assert len(r.json()["data"]["device_id"]) == 12   # md5 前 12 位

    devs = client.get("/api/devices", headers=admin_headers).json()
    dev = next(d for d in devs if d["name"] == "书房电脑")
    assert dev["online"] is False
    # 注册时自动创建 心跳超时 KV(默认 180s)
    kv = client.get("/api/kv/书房电脑.心跳超时", headers=admin_headers).json()
    assert kv["value"] == "180"

    # 重复注册 → 更新而非新建
    r = client.post("/api/device/register",
                    json={"name": "书房电脑", "type": "pc", "heartbeat_timeout": 300}, headers=admin_headers)
    assert r.status_code == 200
    devs = client.get("/api/devices", headers=admin_headers).json()
    matches = [d for d in devs if d["name"] == "书房电脑"]
    assert len(matches) == 1
    assert matches[0]["heartbeat_timeout"] == 300


def test_get_device_404(client, admin_headers):
    assert client.get("/api/devices/nope", headers=admin_headers).status_code == 404


def test_heartbeat_auto_registers_device(client, admin_headers):
    """心跳时设备不存在 → 自动注册"""
    r = client.post("/api/device/heartbeat", json={"name": "新设备", "online": True, "cpu": 10}, headers=admin_headers)
    assert r.status_code == 200
    dev = next(d for d in client.get("/api/devices", headers=admin_headers).json() if d["name"] == "新设备")
    assert dev["online"] is True
    assert dev["cpu"] == 10


def test_heartbeat_updates_metrics_and_volume_kv(client, admin_headers):
    client.post("/api/device/register", json={"name": "音箱", "type": "speaker"}, headers=admin_headers)
    r = client.post("/api/device/heartbeat",
                    json={"name": "音箱", "online": True, "volume": 70, "cpu": 42, "memory": 50},
                    headers=admin_headers)
    assert r.status_code == 200

    dev = next(d for d in client.get("/api/devices", headers=admin_headers).json() if d["name"] == "音箱")
    assert dev["volume"] == 70 and dev["muted"] is False
    assert dev["cpu"] == 42 and dev["memory"] == 50

    # volume 同步到 KV + 历史记录
    assert client.get("/api/kv/音箱.volume", headers=admin_headers).json()["value"] == "70"
    r = client.get("/api/history", params={"key": "音箱.volume"}, headers=admin_headers)
    assert r.json()["total"] >= 1

    # 负数音量 → 静音
    client.post("/api/device/heartbeat", json={"name": "音箱", "online": True, "volume": -1}, headers=admin_headers)
    dev = next(d for d in client.get("/api/devices", headers=admin_headers).json() if d["name"] == "音箱")
    assert dev["muted"] is True


def test_device_variables_prefix_match(client, admin_headers):
    client.post("/api/device/register", json={"name": "监控器", "type": "camera"}, headers=admin_headers)
    client.post("/api/kv", json={"key": "监控器.cpu", "value": "5"}, headers=admin_headers)
    dev = next(d for d in client.get("/api/devices", headers=admin_headers).json() if d["name"] == "监控器")

    r = client.get(f"/api/devices/{dev['id']}/variables", headers=admin_headers)
    keys = [e["key"] for e in r.json()]
    assert "监控器.心跳超时" in keys
    assert "监控器.cpu" in keys


def test_device_variables_hyphen_name(client, admin_headers):
    """名字带连字符的设备,变量查询不能漏(注册用原始名,查询兼容转换名)"""
    client.post("/api/device/register", json={"name": "监控-1", "type": "camera"}, headers=admin_headers)
    # 注册自动写入的 心跳超时 KV 用的是原始名称
    dev = next(d for d in client.get("/api/devices", headers=admin_headers).json() if d["name"] == "监控-1")
    r = client.get(f"/api/devices/{dev['id']}/variables", headers=admin_headers)
    keys = [e["key"] for e in r.json()]
    assert "监控-1.心跳超时" in keys


def test_heartbeat_updates_report_time_key(client, admin_headers):
    """心跳 → 更新服务器专用 设备上报时间 key,值 == last_heartbeat"""
    client.post("/api/device/register", json={"name": "测试机", "type": "pc"}, headers=admin_headers)
    client.post("/api/device/heartbeat", json={"name": "测试机", "online": True}, headers=admin_headers)
    dev = next(d for d in client.get("/api/devices", headers=admin_headers).json() if d["name"] == "测试机")
    kv = client.get("/api/kv/测试机.设备上报时间", headers=admin_headers).json()
    assert kv["value"] == dev["last_heartbeat"]
    assert kv["source"] == "system"


def test_heartbeat_auto_register_creates_report_time_key(client, admin_headers):
    """心跳自动注册的设备 → 也建 设备上报时间 key"""
    client.post("/api/device/heartbeat", json={"name": "新设备", "online": True}, headers=admin_headers)
    kv = client.get("/api/kv/新设备.设备上报时间", headers=admin_headers).json()
    assert kv["source"] == "system"
    assert kv["value"]


def test_unregister_device(client, admin_headers):
    client.post("/api/device/register", json={"name": "待删除", "type": "pc"}, headers=admin_headers)
    dev = next(d for d in client.get("/api/devices", headers=admin_headers).json() if d["name"] == "待删除")
    r = client.delete(f"/api/devices/{dev['id']}", headers=admin_headers)
    assert r.status_code == 200
    assert not any(d["name"] == "待删除" for d in client.get("/api/devices", headers=admin_headers).json())
