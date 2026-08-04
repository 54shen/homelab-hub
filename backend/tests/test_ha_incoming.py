# ============================================================
# Home Assistant 接入模块测试:命名/类型推断/状态上报/批量
# ============================================================
from routers.ha_incoming import _guess_type, _resolve_name


# ---- 纯函数 ----

def test_resolve_name():
    assert _resolve_name("switch.xianshiqi", "显示器开关") == "显示器开关"   # 优先用 friendly_name
    assert _resolve_name("sensor.co2_sensor", "") == "co2.sensor"        # 回退:下划线转点
    assert _resolve_name("light.living_room", "客厅灯") == "客厅灯"


def test_guess_type():
    assert _guess_type("on") == "string"
    assert _guess_type("OFF") == "string"
    assert _guess_type("42") == "int"
    assert _guess_type("23.5") == "float"
    assert _guess_type("未知") == "string"


# ---- 状态上报 ----

def test_state_report_new_and_update(client, admin_headers):
    r = client.post("/api/ha/state", json={"entity_id": "switch.xianshiqi", "state": "on", "friendly_name": "显示器开关"},
                    headers=admin_headers)
    assert r.status_code == 200
    assert "HA.显示器开关 = on" in r.json()["message"]

    # KV 已写入
    assert client.get("/api/kv/HA.显示器开关", headers=admin_headers).json()["value"] == "on"

    # 状态更新
    client.post("/api/ha/state", json={"entity_id": "switch.xianshiqi", "state": "off", "friendly_name": "显示器开关"},
                headers=admin_headers)
    assert client.get("/api/kv/HA.显示器开关", headers=admin_headers).json()["value"] == "off"

    # 同值重复上报 → 静默,历史不增加
    client.post("/api/ha/state", json={"entity_id": "switch.xianshiqi", "state": "off", "friendly_name": "显示器开关"},
                headers=admin_headers)
    r = client.get("/api/history", params={"key": "HA.显示器开关"}, headers=admin_headers)
    assert r.json()["total"] == 2   # 新建1 + 变更1,重复不算


def test_state_report_creates_ha_device(client, admin_headers):
    r = client.post("/api/ha/state", json={"entity_id": "sensor.t1", "state": "23.5", "friendly_name": "温度", "unit": "°C"},
                    headers=admin_headers)
    assert r.status_code == 200

    devs = client.get("/api/devices", headers=admin_headers).json()
    ha = next(d for d in devs if d["name"] == "HA")
    assert ha["type"] == "ha"
    assert ha["group"] == "智能家居"
    assert ha["online"] is True

    entry = client.get("/api/kv/HA.温度", headers=admin_headers).json()
    assert entry["type"] == "float"    # 23.5 → float


def test_state_report_requires_valid_entity_id(client, admin_headers):
    r = client.post("/api/ha/state", json={"entity_id": "bad", "state": "on"}, headers=admin_headers)
    assert r.status_code == 422


def test_batch_states_with_duplicate_entity(client, admin_headers):
    r = client.post("/api/ha/states", json={"states": [
        {"entity_id": "switch.a", "state": "on", "friendly_name": "开关A"},
        {"entity_id": "switch.b", "state": "off", "friendly_name": "开关B"},
        {"entity_id": "switch.a", "state": "on", "friendly_name": "开关A"},   # 重复 → 不计数
    ]}, headers=admin_headers)
    assert r.status_code == 200
    assert "2 个变更" in r.json()["message"]


def test_batch_invalid_entity_rejected(client, admin_headers):
    """批量里有一个非法 entity_id → 整体 422(不受 bug E 影响)"""
    r = client.post("/api/ha/states", json={"states": [
        {"entity_id": "ok.one", "state": "on"},
        {"entity_id": "bad", "state": "on"},
    ]}, headers=admin_headers)
    assert r.status_code == 422
