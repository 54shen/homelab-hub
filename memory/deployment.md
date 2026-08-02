---
name: deployment
description: 部署配置 — 域名、Nginx 反代、WS 代理、访问方式
metadata:
  type: project
---

# 部署配置

## 访问地址
- **生产/调试统一入口**：`https://sc.54shen.cn`
- 无论是本地开发还是生产环境，都通过这个域名访问，不做区分

## 架构
```
浏览器 → https://sc.54shen.cn → 宝塔 Nginx → Vite (5173) / 后端 (8000)
```

## Nginx 反代规则
- `location ^~ /ws` → 直连 `http://127.0.0.1:8000/ws`（WebSocket，绕开 Vite）
- `location ^~ /` → 代理到 `http://192.168.5.232:5173`（Vite 前端）
- SSL 由宝塔管理（Let's Encrypt 证书）
- 服务器 IP：`192.168.5.232`

## 前端环境变量

### `.env`（开发/生产共用）
```
VITE_API_BASE=/api
VITE_WS_URL=ws://192.168.5.232:8000/ws
```

### WebSocket 连接路径
- 浏览器访问 `https://sc.54shen.cn` → WS 连接 `ws://192.168.5.232:8000/ws`
- 注意：HTTPS 页面连接 WS（非 WSS），浏览器可能警告混合内容，但局域网环境可接受
- Nginx 已有 `/ws` location 直连后端，不经过 Vite

## 相关文件
- Nginx 配置：宝塔面板 → 网站 → sc.54shen.cn → 配置文件
- 后端主入口：[backend/main.py](backend/main.py)（端口 8000）
- 前端开发服务器：Vite（端口 5173）
- WS 管理器：[backend/websocket_manager.py](backend/websocket_manager.py)

## 关联
- [[ws-realtime-architecture]] — WS 实时推送架构
