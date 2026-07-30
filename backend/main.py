# ============================================================
# Shared Center — FastAPI 主入口
# ============================================================
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from database import init_db, SessionLocal
from models import Token as TokenModel
from services.cleanup import cleanup_history, check_device_offline
from websocket_manager import connect, disconnect, broadcast
from config import CLEANUP_INTERVAL_HOURS, HEARTBEAT_TIMEOUT_SECONDS
import time
import asyncio

# ---- 调度器 ----
scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _ensure_admin_token()
    scheduler.add_job(cleanup_history, "interval", hours=CLEANUP_INTERVAL_HOURS, id="cleanup")
    scheduler.add_job(check_device_offline, "interval", seconds=HEARTBEAT_TIMEOUT_SECONDS, id="heartbeat_check")
    scheduler.start()
    print("[Shared Center] 服务已启动")
    yield
    scheduler.shutdown(wait=False)


def _ensure_admin_token():
    db = SessionLocal()
    try:
        existing = db.query(TokenModel).filter(TokenModel.permission == "admin").first()
        if not existing:
            import uuid
            token_str = "sk-" + uuid.uuid4().hex
            db.add(TokenModel(name="default-admin", token=token_str, permission="admin"))
            db.commit()
            print(f"\n{'='*50}")
            print(f"  默认 Admin Token: {token_str}")
            print(f"  请妥善保存！")
            print(f"{'='*50}\n")
    finally:
        db.close()


# ---- App ----
app = FastAPI(
    title="Shared Center",
    description="家庭实验室统一数据中心",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- 注册路由 ----
from routers import kv, history, devices, dashboard, alerts, webhooks, logs, settings

app.include_router(kv.router)
app.include_router(history.router)
app.include_router(devices.router)
app.include_router(dashboard.router)
app.include_router(alerts.router)
app.include_router(webhooks.router)
app.include_router(logs.router)
app.include_router(settings.router)


@app.get("/")
def root():
    return {"name": "Shared Center", "version": "1.0.0", "status": "running"}


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---- WebSocket ----
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    await connect(ws)
    try:
        await ws.send_json({"event": "connected", "data": {"time": int(time.time())}})
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_json({"event": "pong", "data": {"time": int(time.time())}})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await disconnect(ws)


# 后台 WebSocket 心跳
async def _ws_heartbeat_loop():
    while True:
        await asyncio.sleep(30)
        await broadcast("heartbeat", {"time": int(time.time())})


@app.on_event("startup")
async def _start_ws_heartbeat():
    asyncio.create_task(_ws_heartbeat_loop())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
