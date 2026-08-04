# ============================================================
# 字段映射模块测试:CRUD / 未映射扫描 / 模板导出 / CSV 导入
# ============================================================


def test_mapping_crud(client, admin_headers):
    r = client.post("/api/field-mappings", json={"field_key": "cpu", "display_name": "CPU使用率"}, headers=admin_headers)
    assert r.status_code == 200

    # 重复 key → 更新而非新建
    r = client.post("/api/field-mappings", json={"field_key": "cpu", "display_name": "CPU"}, headers=admin_headers)
    assert r.json()["display_name"] == "CPU"

    mappings = client.get("/api/field-mappings", headers=admin_headers).json()
    assert len(mappings) == 1
    mid = mappings[0]["id"]

    # 修改
    r = client.put(f"/api/field-mappings/{mid}", json={"display_name": "CPU占用"}, headers=admin_headers)
    assert r.json()["display_name"] == "CPU占用"

    # 删除
    assert client.delete(f"/api/field-mappings/{mid}", headers=admin_headers).status_code == 200
    assert client.get("/api/field-mappings", headers=admin_headers).json() == []


def test_update_mapping_404(client, admin_headers):
    assert client.put("/api/field-mappings/999", json={"display_name": "x"}, headers=admin_headers).status_code == 404


def test_unmapped_keys_scan(client, admin_headers):
    client.post("/api/kv", json={"key": "HA.temperature", "value": "1"}, headers=admin_headers)
    client.post("/api/kv", json={"key": "HA.humidity", "value": "2"}, headers=admin_headers)
    client.post("/api/field-mappings", json={"field_key": "temperature", "display_name": "温度"}, headers=admin_headers)

    r = client.get("/api/field-mappings/unmapped", headers=admin_headers)
    assert r.json() == ["humidity"]


def test_export_template(client, admin_headers):
    r = client.get("/api/field-mappings/export/template", headers=admin_headers)
    assert r.status_code == 200
    assert "field_key" in r.text
    assert "display_name" in r.text


def test_import_csv_insert_then_update(client, admin_headers):
    csv_content = "field_key,display_name\nvoltage,电压\ncurrent,电流\n"
    r = client.post("/api/field-mappings/import",
                    files={"file": ("m.csv", csv_content.encode("utf-8"), "text/csv")},
                    headers=admin_headers)
    assert r.status_code == 200
    assert "新增 2" in r.json()["message"]

    # 再次导入同一份 → 更新而非新增
    r = client.post("/api/field-mappings/import",
                    files={"file": ("m.csv", csv_content.encode("utf-8"), "text/csv")},
                    headers=admin_headers)
    assert "更新 2" in r.json()["message"]
    assert len(client.get("/api/field-mappings", headers=admin_headers).json()) == 2


def test_import_bad_csv_rejected(client, admin_headers):
    r = client.post("/api/field-mappings/import",
                    files={"file": ("bad.csv", b"no,columns\n1,2", "text/csv")},
                    headers=admin_headers)
    assert r.json()["success"] is False
