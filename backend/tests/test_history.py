# ============================================================
# 历史记录模块测试:数值解析 / 列表 / keys / 趋势 / 聚合 / 导出
# ============================================================
from datetime import datetime

from models import KvHistory
from routers.history import _chart_kind, _parse_value, _to_float


# ---- 纯函数:数值解析 ----

def test_to_float():
    assert _to_float("32.5") == 32.5
    assert _to_float("17h 57m") is None      # 时长文本必须拒绝
    assert _to_float("") is None
    assert _to_float(None) is None
    assert _to_float("nan") is None
    assert _to_float("inf") is None


def test_parse_value_number():
    assert _parse_value("32.5") == ("number", 32.5)
    assert _parse_value("-3") == ("number", -3.0)


def test_parse_value_duration():
    assert _parse_value("1d 5h 53m") == ("duration", 107580.0)
    assert _parse_value("5h 53m") == ("duration", 21180.0)
    assert _parse_value("30s") == ("duration", 30.0)
    assert _parse_value("1h") == ("duration", 3600.0)


def test_parse_value_timestamp():
    kind, _ = _parse_value("2026-08-03T02:58:31")
    assert kind == "timestamp"
    kind, _ = _parse_value("2026-08-03 02:58:31.123")
    assert kind == "timestamp"


def test_parse_value_rejects_garbage():
    assert _parse_value("垃圾文本") is None
    assert _parse_value("") is None
    assert _parse_value(None) is None
    assert _parse_value("nan") is None


def test_chart_kind_consistency():
    assert _chart_kind(["1", "2.5", "3"]) == "number"
    assert _chart_kind(["1h", "2m"]) == "duration"
    assert _chart_kind(["1", "1h"]) == ""      # 格式混用 → 不可绘图
    assert _chart_kind(["1", "x"]) == ""
    assert _chart_kind([]) == ""


# ---- API 端点 ----

def _seed(client, admin_headers, rows):
    from database import SessionLocal
    db = SessionLocal()
    try:
        for r in rows:
            db.add(KvHistory(**r))
        db.commit()
    finally:
        db.close()


def test_history_list_filters(client, admin_headers):
    _seed(client, admin_headers, [
        dict(key="HA.temp", old_value="1", new_value="2", source="homeassistant", changed_at="2026-08-01 10:00:00"),
        dict(key="HA.hum", old_value=None, new_value="50", source="homeassistant", changed_at="2026-08-02 10:00:00"),
        dict(key="PC.cpu", old_value="10", new_value="20", source="agent", changed_at="2026-08-03 10:00:00"),
    ])
    H = admin_headers
    assert client.get("/api/history", params={"key": "HA.temp"}, headers=H).json()["total"] == 1
    assert client.get("/api/history", params={"search": "cpu"}, headers=H).json()["total"] == 1
    assert client.get("/api/history", params={"prefix": "HA"}, headers=H).json()["total"] == 2
    assert client.get("/api/history", params={"suffix": "temp"}, headers=H).json()["total"] == 1
    assert client.get("/api/history", params={"source": "agent"}, headers=H).json()["total"] == 1
    assert client.get("/api/history", params={"start": "2026-08-02 00:00:00"}, headers=H).json()["total"] == 2
    assert client.get("/api/history", params={"end": "2026-08-01 23:59:59"}, headers=H).json()["total"] == 1

    # 升序排列
    r = client.get("/api/history", params={"order": "asc"}, headers=H)
    keys = [i["key"] for i in r.json()["items"]]
    assert keys == ["HA.temp", "HA.hum", "PC.cpu"]


def test_history_keys_endpoint(client, admin_headers):
    _seed(client, admin_headers, [
        dict(key="n.v", old_value=None, new_value="1", source="a", changed_at="2026-08-01 10:00:00"),
        dict(key="n.v", old_value="1", new_value="2", source="a", changed_at="2026-08-01 10:01:00"),
        dict(key="t.d", old_value=None, new_value="1h", source="b", changed_at="2026-08-01 10:00:00"),
    ])
    r = client.get("/api/history/keys", headers=admin_headers)
    keys = {k["key"]: k for k in r.json()}
    assert keys["n.v"]["count"] == 2
    assert keys["n.v"]["is_numeric"] is True
    assert keys["n.v"]["latest_value"] == "2"
    assert keys["n.v"]["sources"] == ["a"]
    assert keys["t.d"]["plot_kind"] == "duration"
    assert keys["t.d"]["is_numeric"] is False


def test_history_sources_endpoint(client, admin_headers):
    _seed(client, admin_headers, [
        dict(key="s.1", old_value=None, new_value="1", source="homeassistant", changed_at="2026-08-01 10:00:00"),
        dict(key="s.2", old_value=None, new_value="1", source="homeassistant", changed_at="2026-08-01 10:00:00"),
        dict(key="s.3", old_value=None, new_value="1", source="agent", changed_at="2026-08-01 10:00:00"),
    ])
    r = client.get("/api/history/sources", headers=admin_headers).json()
    assert r == [{"source": "homeassistant", "count": 2}, {"source": "agent", "count": 1}]


def test_history_trend(client, admin_headers):
    _seed(client, admin_headers, [
        dict(key="t.v", old_value=None, new_value="1", changed_at="2026-08-01 10:00:00"),
        dict(key="t.v", old_value="1", new_value="2.5", changed_at="2026-08-01 10:01:00"),
        dict(key="t.v", old_value="2.5", new_value="5h 30m", changed_at="2026-08-01 10:02:00"),
    ])
    r = client.get("/api/history/trend", params={"key": "t.v"}, headers=admin_headers)
    body = r.json()
    assert body["kind"] == "number"          # kind = 首行解析出的类型
    # 格式不一致的时长行被过滤,避免数字和时长混画
    assert [p["value"] for p in body["points"]] == [1.0, 2.5]
    assert body["count"] == 2


def test_history_trend_requires_key(client, admin_headers):
    assert client.get("/api/history/trend", headers=admin_headers).status_code == 422


def test_history_hourly_and_frequency(client, admin_headers):
    _seed(client, admin_headers, [
        dict(key="f.v", old_value=None, new_value="1", changed_at="2026-08-01 10:00:00"),
        dict(key="f.v", old_value="1", new_value="2", changed_at="2026-08-01 10:05:00"),
        dict(key="f.v", old_value="2", new_value="3", changed_at="2026-08-01 11:00:00"),
    ])
    hours = {row["hour"]: row["count"] for row in client.get("/api/history/hourly", headers=admin_headers).json()}
    assert hours["2026-08-01 10"] == 2
    assert hours["2026-08-01 11"] == 1

    mins = {row["minute"]: row["count"] for row in client.get("/api/history/frequency", params={"key": "f.v"}, headers=admin_headers).json()}
    assert mins["2026-08-01 10:00"] == 1
    assert mins["2026-08-01 10:05"] == 1
    assert mins["2026-08-01 11:00"] == 1


def test_history_stats(client, admin_headers):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _seed(client, admin_headers, [
        dict(key="s.v", old_value=None, new_value="1", source="agent", changed_at=now),
    ])
    body = client.get("/api/history/stats", headers=admin_headers).json()
    assert body["total_records"] == 1
    assert body["per_source"][0]["source"] == "agent"
    assert body["per_hour"]  # 至少一个小时的桶


def test_history_export_csv(client, admin_headers):
    _seed(client, admin_headers, [
        dict(key="e.v", old_value="1", new_value="2", source="agent", changed_at="2026-08-01 10:00:00"),
    ])
    r = client.get("/api/history/export", headers=admin_headers)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert r.text.startswith("﻿")       # UTF-8 BOM,Excel 友好
    assert "e.v" in r.text

    # 带 source 过滤导出 → 应仍包含该行
    r = client.get("/api/history/export", params={"source": "agent"}, headers=admin_headers)
    assert r.status_code == 200
    assert "e.v" in r.text
