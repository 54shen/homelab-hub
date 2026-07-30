# ============================================================
# Shared Center — FastAPI 主入口
# ============================================================
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
            db.add(TokenModel(username="admin", name="默认管理员", token=token_str, permission="admin"))
            db.commit()
            print(f"\n{'='*50}")
            print(f"  登录账号: admin")
            print(f"  Admin Token: {token_str}")
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


# ---- Auth 中间件：强制 Token 认证（含读操作） ----
PUBLIC_PATHS = ("/api/health", "/docs", "/openapi.json", "/redoc", "/api/auth/login", "/", "/ws")

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # 公开路径跳过
    if any(request.url.path == p or request.url.path.startswith(p + "/") for p in PUBLIC_PATHS if p != "/"):
        return await call_next(request)
    if request.url.path == "/":
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "需要认证 Token: Authorization: Bearer <token>"})

    token_str = auth_header[7:]
    db = SessionLocal()
    try:
        token_record = db.query(TokenModel).filter(TokenModel.token == token_str).first()
        if not token_record:
            return JSONResponse(status_code=401, content={"detail": "Token 不存在"})

        # 写操作需要 write/admin
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            if token_record.permission not in ("write", "admin"):
                return JSONResponse(status_code=403, content={"detail": "权限不足（需要 write 或 admin）"})

        # 更新会话活跃时间
        from models import Session
        session = db.query(Session).filter(
            Session.token_id == token_record.id,
            Session.ip == (request.client.host if request.client else "")
        ).order_by(Session.id.desc()).first()
        if session:
            from datetime import datetime
            session.last_active = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db.commit()
    finally:
        db.close()

    return await call_next(request)


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


# ---- 前端登录 ----
from pydantic import BaseModel as PydanticBase

class LoginRequest(PydanticBase):
    username: str
    token: str

@app.post("/api/auth/login")
def login(req: LoginRequest):
    """前端登录：验证 username + token"""
    db = SessionLocal()
    try:
        token_record = db.query(TokenModel).filter(
            TokenModel.username == req.username,
            TokenModel.token == req.token
        ).first()
        if not token_record:
            return JSONResponse(status_code=401, content={"detail": "用户名或 Token 错误"})

        # 创建/更新会话记录
        from models import Session
        import uuid
        session = Session(
            token_id=token_record.id,
            username=req.username,
            token_name=token_record.name,
            permission=token_record.permission,
            ip="",
            user_agent=""
        )
        db.add(session)
        db.commit()

        return {
            "success": True,
            "username": token_record.username,
            "name": token_record.name,
            "permission": token_record.permission,
            "token": token_record.token
        }
    finally:
        db.close()


# ---- 会话管理（设置页用） ----
@app.get("/api/sessions")
def list_sessions():
    from models import Session
    db = SessionLocal()
    try:
        sessions = db.query(Session).order_by(Session.last_active.desc()).all()
        return [{
            "id": s.id, "token_id": s.token_id, "username": s.username,
            "token_name": s.token_name, "permission": s.permission,
            "ip": s.ip, "user_agent": s.user_agent,
            "created_at": s.created_at, "last_active": s.last_active
        } for s in sessions]
    finally:
        db.close()


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: int):
    from models import Session
    db = SessionLocal()
    try:
        s = db.query(Session).filter(Session.id == session_id).first()
        if s:
            db.delete(s)
            db.commit()
            return {"success": True, "message": "已踢掉该会话"}
        return JSONResponse(status_code=404, content={"detail": "会话不存在"})
    finally:
        db.close()


# ---- Token 管理 API ----
@app.get("/api/tokens")
def list_tokens():
    db = SessionLocal()
    try:
        tokens = db.query(TokenModel).order_by(TokenModel.id).all()
        return [{
            "id": t.id, "username": t.username, "name": t.name,
            "token": t.token[:8] + "••••" + t.token[-4:],  # 脱敏显示
            "token_full": t.token,
            "permission": t.permission, "created_at": t.created_at
        } for t in tokens]
    finally:
        db.close()


class TokenCreate(PydanticBase):
    username: str = ""
    name: str = ""
    permission: str = "read"

@app.post("/api/tokens")
def create_token(req: TokenCreate):
    db = SessionLocal()
    try:
        import uuid
        token_str = "sk-" + uuid.uuid4().hex
        t = TokenModel(
            username=req.username or req.name,
            name=req.name or req.username or "unnamed",
            token=token_str,
            permission=req.permission
        )
        db.add(t)
        db.commit()
        return {"success": True, "token": token_str, "id": t.id}
    finally:
        db.close()


class TokenUpdate(PydanticBase):
    username: str | None = None
    name: str | None = None
    permission: str | None = None

@app.put("/api/tokens/{token_id}")
def update_token(token_id: int, req: TokenUpdate):
    db = SessionLocal()
    try:
        t = db.query(TokenModel).filter(TokenModel.id == token_id).first()
        if not t:
            return JSONResponse(status_code=404, content={"detail": "Token 不存在"})
        if req.username is not None: t.username = req.username
        if req.name is not None: t.name = req.name
        if req.permission is not None: t.permission = req.permission
        db.commit()
        return {"success": True, "message": "已更新"}
    finally:
        db.close()


@app.delete("/api/tokens/{token_id}")
def delete_token(token_id: int):
    db = SessionLocal()
    try:
        t = db.query(TokenModel).filter(TokenModel.id == token_id).first()
        if t:
            # 同时删除关联会话
            from models import Session
            db.query(Session).filter(Session.token_id == token_id).delete()
            db.delete(t)
            db.commit()
        return {"success": True, "message": "已删除"}
    finally:
        db.close()


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
