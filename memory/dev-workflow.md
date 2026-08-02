---
name: dev-workflow
description: 开发工作流 — 修改代码后需重启前后端并打开网页
metadata:
  type: feedback
---

# 开发工作流

## 每次修改代码后必须执行

1. **重启后端**：`cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000`
2. **重启前端**：`cd frontend && npx vite --host 0.0.0.0 --port 5173`
3. **打开网页**：`start https://sc.54shen.cn`

**Why:** 用户通过 `https://sc.54shen.cn` 访问，宝塔 Nginx 反代到本地 Vite/后端。前端 `.env` 变更需要重启 Vite 生效，后端 Python 文件变更需要重启 uvicorn 生效。

**How to apply:** 每次改完代码，先杀旧进程 (`taskkill //F //IM node.exe` + 杀掉 8000 端口的 python)，再启动后端和前端，最后 `start https://sc.54shen.cn` 打开浏览器。

## 相关
- [[deployment]] — 部署配置详情
- [[ws-realtime-architecture]] — WS 实时推送架构
