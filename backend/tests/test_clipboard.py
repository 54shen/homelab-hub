# ============================================================
# 剪切板功能测试:启动幂等创建 / 删除保护 / 设备隐藏 / 统计排除 / 正常写路径
# ============================================================
from constants import CLIPBOARD_DEVICE_ID, CLIPBOARD_DEVICE_NAME, CLIPBOARD_KEY
from models import Device, KvEntry, KvHistory
from services.clipboard import ensure_clipboard


def test_startup_creates_clipboard(client, db):
    """lifespan 启动后:剪切板设备 + key 各 1 条,且不产生历史"""
    devs = db.query(Device).filter(Device.name == CLIPBOARD_DEVICE_NAME).all()
    assert len(devs) == 1
    assert devs[0].type == "clipboard"

    entries = db.query(KvEntry).filter(KvEntry.key == CLIPBOARD_KEY).all()
    assert len(entries) == 1
    assert entries[0].retention_days == 3650

    # 初始化不得写历史(空值不应出现在历史里)
    assert db.query(KvHistory).filter(KvHistory.key == CLIPBOARD_KEY).count() == 0


def test_ensure_clipboard_idempotent(client, db):
    """重复调用幂等:行数不增"""
    ensure_clipboard(db)
    ensure_clipboard(db)
    assert db.query(Device).filter(Device.name == CLIPBOARD_DEVICE_NAME).count() == 1
    assert db.query(KvEntry).filter(KvEntry.key == CLIPBOARD_KEY).count() == 1


def test_devices_list_and_get_hide_clipboard(client, admin_headers):
    """设备列表不含剪切板;直接按 id 访问详情/变量 → 404"""
    names = [d["name"] for d in client.get("/api/devices", headers=admin_headers).json()]
    assert CLIPBOARD_DEVICE_NAME not in names

    assert client.get(f"/api/devices/{CLIPBOARD_DEVICE_ID}", headers=admin_headers).status_code == 404
    assert client.get(f"/api/devices/{CLIPBOARD_DEVICE_ID}/variables", headers=admin_headers).status_code == 404


def test_delete_clipboard_key_forbidden(client, admin_headers):
    """删除内置 key → 403,key 仍存在"""
    r = client.delete(f"/api/kv/{CLIPBOARD_KEY}", headers=admin_headers)
    assert r.status_code == 403
    assert "内置" in r.json()["detail"]
    assert client.get(f"/api/kv/{CLIPBOARD_KEY}", headers=admin_headers).status_code == 200


def test_batch_delete_skips_clipboard(client, admin_headers):
    """批量删除:内置 key 被跳过,普通 key 正常删除,消息有提示"""
    client.post("/api/kv", json={"key": "x.y", "value": "1"}, headers=admin_headers)
    r = client.post("/api/kv/batch-delete",
                    json={"keys": [CLIPBOARD_KEY, "x.y"]}, headers=admin_headers)
    assert r.status_code == 200
    assert "已跳过 1 个内置变量" in r.json()["message"]
    assert client.get("/api/kv/x.y", headers=admin_headers).status_code == 404
    assert client.get(f"/api/kv/{CLIPBOARD_KEY}", headers=admin_headers).status_code == 200


def test_delete_clipboard_device_forbidden(client, admin_headers):
    """删除内置设备 → 403,设备仍在"""
    r = client.delete(f"/api/devices/{CLIPBOARD_DEVICE_ID}", headers=admin_headers)
    assert r.status_code == 403
    assert "内置" in r.json()["detail"]


def test_stats_exclude_clipboard(client, admin_headers, db):
    """统计排除内置实体:设备/变量/健康度不受剪切板影响"""
    # 注册 2 台普通设备(1 在线)
    from routers.devices import _gen_device_id
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for name, online in [("pc1", True), ("pc2", False)]:
        db.add(Device(id=_gen_device_id(name, "pc"), name=name, type="pc",
                      online=online, last_heartbeat=now))
    # 3 个普通 key
    for i in range(3):
        client.post("/api/kv", json={"key": f"s.k{i}", "value": str(i)}, headers=admin_headers)
    db.commit()

    body = client.get("/api/dashboard/stats", headers=admin_headers).json()
    assert body["total_devices"] == 2
    assert body["online_devices"] == 1
    assert body["total_keys"] == 3
    assert body["system_health"] == 50


def test_clipboard_write_via_normal_path(client, admin_headers, db):
    """写剪切板走普通 /api/kv 路径:写历史、重复值静默、recent 不含"""
    # 首次写入 → 历史 1 条
    r = client.post("/api/kv", json={
        "key": CLIPBOARD_KEY, "value": '{"t":"x","c":"y"}', "type": "string",
        "source": "admin(Web)", "retention_days": 3650,
    }, headers=admin_headers)
    assert r.status_code == 200
    assert db.query(KvHistory).filter(KvHistory.key == CLIPBOARD_KEY).count() == 1
    assert client.get(f"/api/kv/{CLIPBOARD_KEY}", headers=admin_headers).json()["value"] == '{"t":"x","c":"y"}'

    # 重复同值写入 → 静默(值未变不写历史,与普通 key 一致)
    client.post("/api/kv", json={
        "key": CLIPBOARD_KEY, "value": '{"t":"x","c":"y"}', "type": "string",
        "source": "admin(Web)", "retention_days": 3650,
    }, headers=admin_headers)
    assert db.query(KvHistory).filter(KvHistory.key == CLIPBOARD_KEY).count() == 1

    # 变更动态(recent)不包含剪切板 key
    recents = client.get("/api/dashboard/recent", params={"limit": 20}, headers=admin_headers).json()
    assert all(r["key"] != CLIPBOARD_KEY for r in recents)

    # 但历史记录接口仍可查(本质是普通 key)
    h = client.get("/api/history", params={"key": CLIPBOARD_KEY}, headers=admin_headers).json()
    assert h["total"] == 1


def test_import_can_update_clipboard(client, admin_headers):
    """导入含剪切板 key → 走普通写路径正常更新(无特判)"""
    import json
    r = client.post("/api/kv/import",
                    files={"file": ("import.json", json.dumps(
                        [{"key": CLIPBOARD_KEY, "value": '{"t":"i","c":"z"}'}]
                    ).encode(), "application/json")},
                    headers=admin_headers)
    assert r.status_code == 200
    assert client.get(f"/api/kv/{CLIPBOARD_KEY}", headers=admin_headers).json()["value"] == '{"t":"i","c":"z"}'
