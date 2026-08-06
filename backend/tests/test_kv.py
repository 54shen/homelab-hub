# ============================================================
# KV 变量模块测试:读写/批量/历史/导入导出/心跳超时同步
# ============================================================
import json


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
