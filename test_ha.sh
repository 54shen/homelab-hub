#!/bin/bash
# ============================================================
# HA 设备状态手动测试 — 直接上传到 Shared Center
# 用法: bash test_ha.sh
# ============================================================

HUB="http://192.168.5.232:8000/api/ha/state"
TOKEN="Bearer sk-f6ac12cf94f742f8bcea76b609da6786"

echo "=== 上传 HA 设备状态 ==="

# 1. 开关
curl -s -X POST "$HUB" \
  -H "Authorization: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id":"switch.cuco_cn_961948487_v3_on_p_2_1","state":"on","friendly_name":"CoCo开关"}'
echo ""

# 2. 人在传感器
curl -s -X POST "$HUB" \
  -H "Authorization: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id":"sensor.mqtt_presence_status","state":"home","friendly_name":"人在状态"}'
echo ""

# 3. 服务器时间（自动取当前 ISO 8601 时间）
curl -s -X POST "$HUB" \
  -H "Authorization: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id":"sensor.lpy_es6_server_time","state":"'"$(date -Iseconds)"'","friendly_name":"服务器时间"}'
echo ""

echo "=== 完成 ==="
