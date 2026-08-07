# ============================================================
# KV 变量模块测试:读写/批量/历史/导入导出/心跳超时同步
# ============================================================
import json
from datetime import datetime


def test_set_and_get(client, admin_headers):
    r = client.post("/api/kv", json={"key": "room.temp", "value": "25.5", "type": "float", "source": "test"},
                    headers=admin_headers)
    assert r.status_code == 200

    r = client.get("/api/kv/room.temp", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["value"] == "25.5"
    assert body["type"] == "float"
    assert body["source"] == "test"


def test_get_missing_key_404(client, admin_headers):
    assert client.get("/api/kv/not_exist", headers=admin_headers).status_code == 404


def test_set_same_value_is_silent(client, admin_headers):
    """值不变 → 不产生新历史记录(静默)"""
    for _ in range(2):
        client.post("/api/kv", json={"key": "k.same", "value": "1"}, headers=admin_headers)
    r = client.get("/api/history", params={"key": "k.same"}, headers=admin_headers)
    assert r.json()["total"] == 1


def test_set_changed_value_records_history(client, admin_headers):
    client.post("/api/kv", json={"key": "k.hist", "value": "1"}, headers=admin_headers)
    client.post("/api/kv", json={"key": "k.hist", "value": "2"}, headers=admin_headers)
    r = client.get("/api/history", params={"key": "k.hist"}, headers=admin_headers)
    body = r.json()
    assert body["total"] == 2
    # 两条历史:新建(old=None) + 变更(old=1→new=2)。同一秒内写入时顺序不保证,用集合断言
    records = {(item["old_value"], item["new_value"]) for item in body["items"]}
    assert (None, "1") in records
    assert ("1", "2") in records


def test_list_and_prefix_filter(client, admin_headers):
    # 注意:KV 列表的实际路由是 GET /api/list
    for k, v in [("a.one", "1"), ("a.two", "2"), ("b.one", "3")]:
        client.post("/api/kv", json={"key": k, "value": v}, headers=admin_headers)

    all_keys = {e["key"] for e in client.get("/api/list", headers=admin_headers).json()}
    # 列表包含写入的 key；启动时 lifespan 会创建内置剪切板 key（"剪切板.内容"），
    # 因此不能做精确集合断言,只验证子集 + 内置 key 存在
    assert {"a.one", "a.two", "b.one"} <= all_keys
    assert "剪切板.内容" in all_keys

    prefixed = {e["key"] for e in client.get("/api/list", params={"prefix": "a."}, headers=admin_headers).json()}
    assert prefixed == {"a.one", "a.two"}


def test_delete_and_batch(client, admin_headers):
    # 批量写入
    r = client.post("/api/kv/batch", json={"items": [
        {"key": "b1", "value": "1"}, {"key": "b2", "value": "2"}
    ]}, headers=admin_headers)
    assert r.status_code == 200
    assert "已写入 2" in r.json()["message"]

    # 批量删除
    r = client.post("/api/kv/batch-delete", json={"keys": ["b1"]}, headers=admin_headers)
    assert r.status_code == 200
    assert client.get("/api/kv/b1", headers=admin_headers).status_code == 404
    assert client.get("/api/kv/b2", headers=admin_headers).status_code == 200

    # 单个删除
    assert client.delete("/api/kv/b2", headers=admin_headers).status_code == 200
    assert client.get("/api/kv/b2", headers=admin_headers).status_code == 404


def test_export_kv(client, admin_headers):
    client.post("/api/kv", json={"key": "exp.one", "value": "1"}, headers=admin_headers)
    r = client.get("/api/kv/export", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert any(item["key"] == "exp.one" and item["value"] == "1" for item in data)


def test_import_kv(client, admin_headers):
    """导入功能本身正常(不受导出 bug 影响)"""
    r = client.post("/api/kv/import",
                    files={"file": ("import.json", json.dumps([{"key": "imp.one", "value": "9"}]).encode(), "application/json")},
                    headers=admin_headers)
    assert r.status_code == 200
    assert client.get("/api/kv/imp.one", headers=admin_headers).json()["value"] == "9"


def test_heartbeat_timeout_kv_syncs_to_device(client, admin_headers):
    """写 设备.心跳超时 KV → 自动同步到 Device 表"""
    client.post("/api/device/register", json={"name": "测试机", "type": "pc"}, headers=admin_headers)
    r = client.post("/api/kv", json={"key": "测试机.心跳超时", "value": "500"}, headers=admin_headers)
    assert r.status_code == 200
    devs = client.get("/api/devices", headers=admin_headers).json()
    dev = next(d for d in devs if d["name"] == "测试机")
    assert dev["heartbeat_timeout"] == 500


def test_heartbeat_timeout_sync_via_transformed_prefix(client, admin_headers):
    """转换前缀(连字符→点)写 心跳超时 → 也能同步回正确设备(旧 rsplit 反推的 bug)"""
    client.post("/api/device/register", json={"name": "监控-1", "type": "camera"}, headers=admin_headers)
    r = client.post("/api/kv", json={"key": "监控.1.心跳超时", "value": "500"}, headers=admin_headers)
    assert r.status_code == 200
    devs = client.get("/api/devices", headers=admin_headers).json()
    dev = next(d for d in devs if d["name"] == "监控-1")
    assert dev["heartbeat_timeout"] == 500


# ============================================================
# 设备活跃度：变量上报刷新在线状态 + 服务器专用"server_received_at" key
# ============================================================

def _register(client, admin_headers, name, typ="pc"):
    client.post("/api/device/register", json={"name": name, "type": typ}, headers=admin_headers)


def test_kv_report_refreshes_device_heartbeat(client, admin_headers):
    """设备变量上报(无心跳)→ 设备被标记在线"""
    _register(client, admin_headers, "测试机")
    r = client.post("/api/kv", json={"key": "测试机.温度", "value": "25"}, headers=admin_headers)
    assert r.status_code == 200
    dev = next(d for d in client.get("/api/devices", headers=admin_headers).json() if d["name"] == "测试机")
    assert dev["online"] is True
    assert dev["last_heartbeat"]


def test_kv_report_unchanged_value_still_refreshes_report_time(client, admin_headers):
    """值无变化(静默)也要记录server_received_at"""
    _register(client, admin_headers, "测试机")
    for _ in range(2):
        client.post("/api/kv", json={"key": "测试机.温度", "value": "25"}, headers=admin_headers)

    # 值没变 → 变量本身无新历史(静默语义保留)
    r = client.get("/api/history", params={"key": "测试机.温度"}, headers=admin_headers)
    assert r.json()["total"] == 1

    # 但上报时间 key 存在且由服务器写
    kv = client.get("/api/kv/测试机.server_received_at", headers=admin_headers).json()
    assert kv["source"] == "system"
    assert kv["type"] == "string"


def test_report_time_key_is_server_overridden(client, admin_headers):
    """设备伪造上传 server_received_at → 服务器强制覆盖为当前时间"""
    _register(client, admin_headers, "测试机")
    r = client.post("/api/kv", json={"key": "测试机.server_received_at", "value": "evil", "source": "hacker", "type": "int"},
                    headers=admin_headers)
    assert r.status_code == 200
    kv = client.get("/api/kv/测试机.server_received_at", headers=admin_headers).json()
    datetime.strptime(kv["value"], "%Y-%m-%d %H:%M:%S")   # 值被覆盖为合法时间戳
    assert kv["source"] == "system"
    assert kv["type"] == "string"


def test_report_time_key_no_history_noise(client, admin_headers):
    """上报时间 key 静默更新：不写历史记录"""
    _register(client, admin_headers, "测试机")
    for v in ("1", "2", "3"):
        client.post("/api/kv", json={"key": "测试机.温度", "value": v}, headers=admin_headers)
    r = client.get("/api/history", params={"key": "测试机.server_received_at"}, headers=admin_headers)
    assert r.json()["total"] == 0


def test_report_time_key_unknown_device_dropped(client, admin_headers):
    """未知设备的上报时间 key → 整个丢弃,不建幽灵 key"""
    r = client.post("/api/kv", json={"key": "幽灵.server_received_at", "value": "1"}, headers=admin_headers)
    assert r.status_code == 200
    assert client.get("/api/kv/幽灵.server_received_at", headers=admin_headers).status_code == 404


def test_batch_kv_multi_device_mixed(client, admin_headers):
    """批量混传多设备 key + 恶意上报时间 key → 各刷新各的,独占 key 被覆盖"""
    _register(client, admin_headers, "设备A")
    _register(client, admin_headers, "设备B")
    r = client.post("/api/kv/batch", json={"items": [
        {"key": "设备A.温度", "value": "1"},
        {"key": "设备B.温度", "value": "2"},
        {"key": "设备B.server_received_at", "value": "fake"},
    ]}, headers=admin_headers)
    assert r.status_code == 200
    devs = {d["name"]: d for d in client.get("/api/devices", headers=admin_headers).json()}
    assert devs["设备A"]["online"] is True
    assert devs["设备B"]["online"] is True
    kv = client.get("/api/kv/设备B.server_received_at", headers=admin_headers).json()
    assert kv["source"] == "system"
    assert kv["value"] != "fake"


def test_hyphen_name_resolve_from_transformed_prefix(client, admin_headers):
    """连字符设备名走转换前缀上报 → 仍刷新原设备"""
    _register(client, admin_headers, "监控-1")
    client.post("/api/kv", json={"key": "监控.1.cpu", "value": "5"}, headers=admin_headers)
    dev = next(d for d in client.get("/api/devices", headers=admin_headers).json() if d["name"] == "监控-1")
    assert dev["online"] is True
    assert client.get("/api/kv/监控-1.server_received_at", headers=admin_headers).status_code == 200


def test_dot_in_device_name_longest_prefix(client, admin_headers):
    """设备名含点 → 最长前缀匹配,key 归最具体的设备"""
    _register(client, admin_headers, "A")
    _register(client, admin_headers, "A.1")
    client.post("/api/kv", json={"key": "A.1.x", "value": "1"}, headers=admin_headers)
    client.post("/api/kv", json={"key": "A.y", "value": "2"}, headers=admin_headers)
    devs = {d["name"]: d for d in client.get("/api/devices", headers=admin_headers).json()}
    assert devs["A"]["online"] is True
    assert devs["A.1"]["online"] is True


def test_report_time_key_delete_forbidden(client, admin_headers):
    """删除服务器独占 key → 403"""
    _register(client, admin_headers, "测试机")
    r = client.delete("/api/kv/测试机.server_received_at", headers=admin_headers)
    assert r.status_code == 403
    # 批量删除也会被过滤
    r = client.post("/api/kv/batch-delete", json={"keys": ["测试机.server_received_at"]}, headers=admin_headers)
    assert r.status_code == 200
    assert client.get("/api/kv/测试机.server_received_at", headers=admin_headers).status_code == 200
