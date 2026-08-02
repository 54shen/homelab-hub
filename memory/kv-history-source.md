---
name: kv-history-source
description: KvHistory 记录的 source 字段应反映数据真实来源
metadata:
  type: project
---

KvHistory 表的 `source` 字段表示变更的真实来源。当前有三个写入点：

1. `kv.py:_set_kv_sync` — source 来自 `req.source`（Agent 传 "agent"，Web 传 "xxx(Web)"）
2. `ha_incoming.py:_write_kv` — source 来自 `req.source`（"homeassistant"）
3. `devices.py:device_heartbeat` — `_sync_kv` 同步 volume/muted 到 KV 系统，source 应设为 `"agent"`（数据真实来自 Agent），不要用 `"heartbeat"`（那是内部实现细节）

**原则**：source 应反映数据原始来源，不是后端转发机制。
