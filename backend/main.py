# ============================================================
# Shared Center — FastAPI 主入口
# ============================================================
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from database import init_db, SessionLocal
from models import Token as TokenModel, User, Session as SessionModel
import hashlib
import secrets

def hash_password(password: str) -> str:
    """SHA-256 + 随机盐"""
    salt = secrets.token_hex(16)
    return salt + ":" + hashlib.sha256((salt + password).encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """验证密码"""
    try:
        salt, hash_val = hashed.split(":", 1)
        return hashlib.sha256((salt + password).encode()).hexdigest() == hash_val
    except ValueError:
        return False
from services.cleanup import cleanup_history, check_device_offline
from services.scheduler import init_scheduler
from websocket_manager import connect, disconnect, broadcast
from config import CLEANUP_INTERVAL_HOURS, HEARTBEAT_TIMEOUT_SECONDS
import time
import asyncio


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _ensure_admin_user()
    scheduler = init_scheduler()
    scheduler.add_job(cleanup_history, "interval", hours=CLEANUP_INTERVAL_HOURS, id="cleanup")
    # check_device_offline 只负责标记设备离线（UI 状态），告警触发改由心跳路径实时预约
    scheduler.add_job(check_device_offline, "interval", seconds=HEARTBEAT_TIMEOUT_SECONDS, id="heartbeat_check")
    scheduler.start()
    print("[Shared Center] 服务已启动")
    yield
    scheduler.shutdown(wait=False)


def _ensure_admin_user():
    """确保至少有一个 admin 用户可用"""
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.permission == "admin").first()
        if not existing:
            # 创建默认管理员用户 密码: admin123
            import uuid
            user = User(username="admin", password_hash=hash_password("admin123"), permission="admin")
            db.add(user)
            db.flush()  # 获取 user.id
            # 同时创建关联的 admin token
            token_str = "sk-" + uuid.uuid4().hex
            db.add(TokenModel(user_id=user.id, name="默认管理员", token=token_str, permission="admin"))
            db.commit()
            print(f"\n{'='*50}")
            print(f"  Web 登录: admin / admin123")
            print(f"  API Token: {token_str}")
            print(f"  请尽快修改默认密码！")
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
        # 先查 API Token 表
        token_record = db.query(TokenModel).filter(TokenModel.token == token_str).first()
        # 再查 Web 会话表
        session_record = db.query(SessionModel).filter(SessionModel.session_token == token_str).first() if not token_record else None

        if not token_record and not session_record:
            return JSONResponse(status_code=401, content={"detail": "Token 无效"})

        # 确定权限：API Token 或 Session
        if token_record:
            permission = token_record.permission
        else:
            permission = session_record.permission

        # 写操作需要 write/admin
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            if permission not in ("write", "admin"):
                return JSONResponse(status_code=403, content={"detail": "权限不足（需要 write 或 admin）"})

        # 更新 Web 会话活跃时间
        if session_record:
            from datetime import datetime
            session_record.last_active = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db.commit()
    finally:
        db.close()

    return await call_next(request)


# ---- 注册路由 ----
from routers import kv, devices, dashboard, alerts, webhooks, logs, settings, ha_incoming, history, field_mappings

app.include_router(kv.router)
app.include_router(devices.router)
app.include_router(dashboard.router)
app.include_router(alerts.router)
app.include_router(webhooks.router)
app.include_router(logs.router)
app.include_router(settings.router)
app.include_router(ha_incoming.router)
app.include_router(history.router)
app.include_router(field_mappings.router)


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
    password: str

@app.post("/api/auth/login")
def login(req: LoginRequest, request: Request):
    """Web 登录：账号 + 密码 → 返回会话 Token（仅 Web 有效）"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == req.username).first()
        if not user or not verify_password(req.password, user.password_hash):
            return JSONResponse(status_code=401, content={"detail": "账号或密码错误"})

        # 获取客户端 IP
        forwarded = request.headers.get("X-Forwarded-For", "")
        client_ip = forwarded.split(",")[0].strip() if forwarded else (
            request.client.host if request.client else ""
        )

        # 生成会话专用 Token（不污染 API Token 表）
        import uuid
        session_token = "ws-" + uuid.uuid4().hex

        session = SessionModel(
            user_id=user.id,
            username=user.username,
            permission=user.permission,
            session_token=session_token,
            ip=client_ip,
            user_agent=request.headers.get("User-Agent", "")[:256]
        )
        db.add(session)
        db.commit()

        return {
            "success": True,
            "username": user.username,
            "permission": user.permission,
            "token": session_token
        }
    finally:
        db.close()


class PasswordChangeRequestV2(PydanticBase):
    username: str
    old_password: str
    new_password: str

@app.put("/api/auth/password")
def change_password(req: PasswordChangeRequestV2):
    """修改密码：验证旧密码后更新"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == req.username).first()
        if not user or not verify_password(req.old_password, user.password_hash):
            return JSONResponse(status_code=400, content={"detail": "旧密码错误"})

        if len(req.new_password) < 4:
            return JSONResponse(status_code=400, content={"detail": "新密码至少 4 位"})

        user.password_hash = hash_password(req.new_password)
        db.commit()
        return {"success": True, "message": "密码已修改"}
    finally:
        db.close()


# ---- 会话管理（设置页用） ----
@app.get("/api/sessions")
def list_sessions():
    db = SessionLocal()
    try:
        sessions = db.query(SessionModel).order_by(SessionModel.last_active.desc()).all()
        return [{
            "id": s.id, "user_id": s.user_id, "username": s.username,
            "permission": s.permission, "ip": s.ip, "user_agent": s.user_agent,
            "created_at": s.created_at, "last_active": s.last_active
        } for s in sessions]
    finally:
        db.close()


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: int):
    db = SessionLocal()
    try:
        s = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if s:
            db.delete(s)
            db.commit()
            return {"success": True, "message": "已踢掉该会话"}
        return JSONResponse(status_code=404, content={"detail": "会话不存在"})
    finally:
        db.close()


@app.post("/api/sessions/kick-all")
def kick_all_sessions(request: Request):
    """踢掉当前 Token 之外的所有 Web 会话"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "缺少 Token"})
    current_token = auth_header[7:]

    db = SessionLocal()
    try:
        deleted = db.query(SessionModel).filter(
            SessionModel.session_token != current_token
        ).delete()
        db.commit()
        return {"success": True, "message": f"已踢掉 {deleted} 个会话", "deleted": deleted}
    finally:
        db.close()


# ---- Token 管理 API ----
@app.get("/api/tokens")
def list_tokens():
    db = SessionLocal()
    try:
        tokens = db.query(TokenModel).order_by(TokenModel.id).all()
        return [{
            "id": t.id, "user_id": t.user_id, "name": t.name,
            "token": t.token[:8] + "••••" + t.token[-4:],
            "token_full": t.token,
            "permission": t.permission, "created_at": t.created_at
        } for t in tokens]
    finally:
        db.close()


class TokenCreate(PydanticBase):
    name: str = ""
    permission: str = "read"
    user_id: int | None = None  # 关联用户ID

@app.post("/api/tokens")
def create_token(req: TokenCreate):
    db = SessionLocal()
    try:
        import uuid
        token_str = "sk-" + uuid.uuid4().hex
        t = TokenModel(name=req.name or "unnamed", token=token_str, permission=req.permission, user_id=req.user_id)
        db.add(t)
        db.commit()
        return {"success": True, "token": token_str, "id": t.id}
    finally:
        db.close()


class TokenUpdate(PydanticBase):
    name: str | None = None
    permission: str | None = None

@app.put("/api/tokens/{token_id}")
def update_token(token_id: int, req: TokenUpdate):
    db = SessionLocal()
    try:
        t = db.query(TokenModel).filter(TokenModel.id == token_id).first()
        if not t:
            return JSONResponse(status_code=404, content={"detail": "Token 不存在"})
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
            db.query(SessionModel).filter(SessionModel.user_id == t.id).delete()
            db.delete(t)
            db.commit()
        return {"success": True, "message": "已删除"}
    finally:
        db.close()


# ---- 用户管理 API ----
@app.get("/api/users")
def list_users():
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.id).all()
        return [{
            "id": u.id, "username": u.username,
            "permission": u.permission, "created_at": u.created_at
        } for u in users]
    finally:
        db.close()


class UserCreate(PydanticBase):
    username: str
    password: str
    permission: str = "read"

@app.post("/api/users")
def create_user(req: UserCreate):
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == req.username).first():
            return JSONResponse(status_code=400, content={"detail": "用户名已存在"})
        if len(req.password) < 4:
            return JSONResponse(status_code=400, content={"detail": "密码至少 4 位"})

        user = User(username=req.username, password_hash=hash_password(req.password), permission=req.permission)
        db.add(user)
        db.flush()
        # 为新用户自动创建一个 API Token
        import uuid
        token_str = "sk-" + uuid.uuid4().hex
        db.add(TokenModel(user_id=user.id, name=f"{req.username}的Token", token=token_str, permission=req.permission))
        db.commit()
        return {"success": True, "id": user.id, "token": token_str}
    finally:
        db.close()


class UserUpdate(PydanticBase):
    password: str | None = None
    permission: str | None = None

@app.put("/api/users/{user_id}")
def update_user(user_id: int, req: UserUpdate):
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == user_id).first()
        if not u:
            return JSONResponse(status_code=404, content={"detail": "用户不存在"})
        if req.password:
            if len(req.password) < 4:
                return JSONResponse(status_code=400, content={"detail": "密码至少 4 位"})
            u.password_hash = hash_password(req.password)
        if req.permission is not None:
            u.permission = req.permission
        db.commit()
        return {"success": True, "message": "已更新"}
    finally:
        db.close()


@app.delete("/api/users/{user_id}")
def delete_user(user_id: int):
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == user_id).first()
        if u:
            # 删除关联的 Token 和会话
            db.query(TokenModel).filter(TokenModel.user_id == user_id).delete()
            db.query(SessionModel).filter(SessionModel.user_id == user_id).delete()
            db.delete(u)
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
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
