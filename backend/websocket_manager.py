# ============================================================
# Shared Center — WebSocket 连接管理器
# ============================================================
import asyncio
import json
from typing import Any

_connections: set[Any] = set()
_lock = asyncio.Lock()


async def connect(websocket) -> None:
    async with _lock:
        _connections.add(websocket)


async def disconnect(websocket) -> None:
    async with _lock:
        _connections.discard(websocket)


async def broadcast(event: str, data: dict) -> None:
    """向所有已连接的客户端广播事件"""
    if not _connections:
        return
    message = json.dumps({"event": event, "data": data}, ensure_ascii=False)
    stale: set[Any] = set()
    async with _lock:
        for ws in _connections.copy():
            try:
                await ws.send_text(message)
            except Exception:
                stale.add(ws)
        _connections.difference_update(stale)
