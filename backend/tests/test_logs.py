# ============================================================
# 系统日志模块测试:列表筛选/分页/导出/清空
# ============================================================
from models import SystemLog


def _seed_logs(db, n_info=5, n_error=2):
    for i in range(n_info):
        db.add(SystemLog(level="info", module="test", message=f"msg{i}",
                         created_at=f"2026-08-01 10:0{i}:00"))
    for i in range(n_error):
        db.add(SystemLog(level="error", module="test", message=f"err{i}",
                         created_at=f"2026-08-01 10:0{i}:00"))
    db.commit()


def test_logs_list_filter_and_page(client, admin_headers, db):
    _seed_logs(db)
    body = client.get("/api/logs", headers=admin_headers).json()
    assert body["total"] == 7

    body = client.get("/api/logs", params={"level": "error"}, headers=admin_headers).json()
    assert body["total"] == 2

    # 分页:page 2 每页 5 条 → 还剩 2 条
    body = client.get("/api/logs", params={"page": 2, "page_size": 5}, headers=admin_headers).json()
    assert body["total"] == 7
    assert len(body["items"]) == 2

    # 模块筛选
    body = client.get("/api/logs", params={"module": "不存在"}, headers=admin_headers).json()
    assert body["total"] == 0


def test_logs_export_csv(client, admin_headers, db):
    db.add(SystemLog(level="warn", module="m", message="导出测试", created_at="2026-08-01 10:00:00"))
    db.commit()
    r = client.get("/api/logs/export", headers=admin_headers)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "导出测试" in r.text
    assert "Level" in r.text    # 表头


def test_logs_clear(client, admin_headers, db):
    _seed_logs(db)
    r = client.post("/api/logs/clear", headers=admin_headers)
    assert r.status_code == 200
    assert "已清空" in r.json()["message"]
    assert client.get("/api/logs", headers=admin_headers).json()["total"] == 0
