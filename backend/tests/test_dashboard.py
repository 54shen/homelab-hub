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


# ---- TOTP 展示器 ----

def test_totp_code_not_configured(client, admin_headers):
    """未配置密钥 → configured=False"""
    r = client.get("/api/dashboard/totp-code", headers=admin_headers)
    assert r.json() == {"configured": False}


def test_totp_secret_admin_only(client, admin_headers):
    """录入密钥仅 admin 可操作:write 用户 → 403"""
    import pyotp
    secret = pyotp.random_base32()
    # 创建 write 用户并登录
    assert client.post("/api/users", json={"username": "tw", "password": "pass1234", "permission": "write"},
                       headers=admin_headers).status_code == 200
    r = client.post("/api/auth/login", json={"username": "tw", "password": "pass1234"})
    write_headers = {"Authorization": f"Bearer {r.json()['token']}"}

    assert client.put("/api/dashboard/totp-secret", json={"secret": secret},
                      headers=write_headers).status_code == 403
    # admin 可以
    assert client.put("/api/dashboard/totp-secret", json={"secret": secret},
                      headers=admin_headers).status_code == 200


def test_totp_code_matches_pyotp(client, admin_headers):
    """配置密钥后:验证码与 pyotp 一致,剩余秒数在 0-30 内"""
    import pyotp
    secret = pyotp.random_base32()
    assert client.put("/api/dashboard/totp-secret", json={"secret": secret},
                      headers=admin_headers).status_code == 200

    body = client.get("/api/dashboard/totp-code", headers=admin_headers).json()
    assert body["configured"] is True
    assert body["code"] == pyotp.TOTP(secret).now()
    assert len(body["code"]) == 6
    assert 0 <= body["period_remaining"] < 30


def test_totp_secret_invalid(client, admin_headers):
    """非法 Base32 密钥 → 400"""
    r = client.put("/api/dashboard/totp-secret", json={"secret": "!!!not-base32!!!"},
                   headers=admin_headers)
    assert r.status_code == 400
    assert "密钥格式无效" in r.json()["detail"]
