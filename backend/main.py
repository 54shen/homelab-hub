# ============================================================
# Shared Center — FastAPI 主入口
# ============================================================
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from database import init_db, SessionLocal
from models import Token as TokenModel, User, Session as SessionModel, UISetting
from constants import AUTH_CODE_ONLY_KEY
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
import pyotp


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _ensure_admin_user()
    _ensure_clipboard()
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


def _ensure_clipboard():
    """确保剪切板内置设备 + key 存在（幂等）"""
    from services.clipboard import ensure_clipboard
    db = SessionLocal()
    try:
        ensure_clipboard(db)
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
PUBLIC_PATHS = ("/api/health", "/docs", "/openapi.json", "/redoc",
                "/api/auth/login", "/api/auth/verify-2fa", "/api/auth/login-mode", "/api/auth/totp-login",
                "/", "/ws")

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

# ---- 仅验证码登录：全局 A 锁 / B 锁 / 一次性 ticket（内存存储，重启清零） ----
# 全局 A 锁：纯验证码(totp-login)连续错 A_FAIL_LIMIT 次 → 纯验证码渠道全局锁 30 分钟。
#   B(用户名+密码+验证码)与未绑定用户的密码登录不受影响；管理员 B 登录成功立即重置。
# B 锁：按用户名，B 路径连续失败 B_FAIL_LIMIT 次 → 该用户名锁 1 分钟。
# ticket：login 验密码成功后发一次性票据(5 分钟有效)，verify-2fa 携带以证明"密码已验证"。
A_FAIL_LIMIT = 5
A_LOCK_SECONDS = 1800      # 30 分钟
B_FAIL_LIMIT = 5
B_LOCK_SECONDS = 60        # 1 分钟
TICKET_TTL = 300           # 5 分钟
_code_lock = {"fail": 0, "until": 0.0}       # 全局 A 锁
_b_locks: dict[str, list] = {}               # username -> [fail_count, locked_until]
_login_tickets: dict[str, list] = {}         # ticket -> [username, expire_ts]


def _is_code_only(db) -> bool:
    row = db.query(UISetting).filter(UISetting.key == AUTH_CODE_ONLY_KEY).first()
    return bool(row and row.value == "1")


def _code_locked() -> bool:
    return time.time() < _code_lock["until"]


def _clear_code_lock():
    _code_lock["fail"] = 0
    _code_lock["until"] = 0.0


def _b_locked(username: str) -> bool:
    entry = _b_locks.get(username)
    return bool(entry and time.time() < entry[1])


def _b_fail(username: str):
    """B 路径失败计数；已锁定期间不叠加，避免延长锁定期"""
    now = time.time()
    entry = _b_locks.setdefault(username, [0, 0.0])
    if entry[1] > now:
        return
    entry[0] += 1
    if entry[0] >= B_FAIL_LIMIT:
        entry[1] = now + B_LOCK_SECONDS
        entry[0] = 0


def _consume_ticket(ticket: str, username: str) -> bool:
    """校验并消费一次性 ticket（存在 + 用户匹配 + 未过期 → 用后即焚）"""
    entry = _login_tickets.get(ticket)
    if not entry:
        return False
    if entry[0] != username or time.time() > entry[1]:
        _login_tickets.pop(ticket, None)
        return False
    del _login_tickets[ticket]
    return True

def _issue_web_session(db, user, request) -> str:
    """创建 Web 会话并返回会话 Token（login / verify-2fa 共用）"""
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
    return session_token


@app.post("/api/auth/login")
def login(req: LoginRequest, request: Request):
    """Web 登录第一步：账号 + 密码（B 路径）。
    未启用二次验证 → 直接返回会话 Token；已启用 → 返回 need_2fa + 一次性 ticket，等第二步验证码。
    """
    db = SessionLocal()
    try:
        code_only = _is_code_only(db)
        user = db.query(User).filter(User.username == req.username).first()
        if not user or not verify_password(req.password, user.password_hash):
            # 仅验证码模式下:已绑定用户的密码错误计入该用户名 B 锁
            # (未绑定用户为纯密码登录不参与锁;开关关闭时保持现状零行为变化)
            if code_only and user and user.totp_enabled:
                _b_fail(user.username)
            return JSONResponse(status_code=401, content={"detail": "账号或密码错误"})

        # 已启用二次验证 → 第一步不发会话，返回 need_2fa + 一次性 ticket（证明密码已验证）
        if user.totp_enabled and user.totp_secret:
            if code_only and _b_locked(user.username):
                return JSONResponse(status_code=429,
                                    content={"detail": "该账号登录失败次数过多，已锁定 1 分钟，请稍后再试"})
            ticket = secrets.token_hex(16)
            _login_tickets[ticket] = [user.username, time.time() + TICKET_TTL]
            return {"success": False, "need_2fa": True, "username": user.username, "ticket": ticket}

        session_token = _issue_web_session(db, user, request)
        return {
            "success": True,
            "username": user.username,
            "permission": user.permission,
            "token": session_token
        }
    finally:
        db.close()


class Verify2FARequest(PydanticBase):
    username: str
    code: str
    ticket: str | None = None   # B 路径凭证(login 验密码后签发);仅验证码模式开关开启时必填

@app.post("/api/auth/verify-2fa")
def verify_2fa(req: Verify2FARequest, request: Request):
    """登录第二步（B 路径）：6 位 TOTP 验证码 → 校验通过发放会话 Token。

    仅验证码模式开启时要求携带 login 签发的一次性 ticket（证明密码已验证），
    纯验证码登录请走 /api/auth/totp-login。
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == req.username).first()
        if not user or not user.totp_enabled or not user.totp_secret:
            return JSONResponse(status_code=401, content={"detail": "该账号未启用二次验证"})

        code_only = _is_code_only(db)
        if code_only:
            # 仅验证码模式：B 路径必须持 ticket（否则任何人都能绕过密码直接试验证码）
            if not req.ticket or not _consume_ticket(req.ticket, user.username):
                return JSONResponse(status_code=401,
                                    content={"detail": "请先通过账号密码验证（或改用纯验证码登录）"})
            if _b_locked(user.username):
                return JSONResponse(status_code=429,
                                    content={"detail": "该账号登录失败次数过多，已锁定 1 分钟，请稍后再试"})

        if not pyotp.TOTP(user.totp_secret).verify(req.code.strip(), valid_window=1):
            if code_only:
                _b_fail(user.username)
            return JSONResponse(status_code=401, content={"detail": "验证码错误或已过期"})

        session_token = _issue_web_session(db, user, request)
        # B 路径成功：该用户名 B 锁清零；管理员登录成功 → 重置全局 A 锁
        if code_only:
            _b_locks.pop(user.username, None)
            if user.permission == "admin":
                _clear_code_lock()
        return {
            "success": True,
            "username": user.username,
            "permission": user.permission,
            "token": session_token
        }
    finally:
        db.close()


class TotpLoginRequest(PydanticBase):
    code: str

@app.post("/api/auth/totp-login")
def totp_login(req: TotpLoginRequest, request: Request):
    """纯验证码登录（A 路径）：只有 6 位验证码，无用户名/密码。
    遍历所有已绑定 TOTP 的用户匹配验证码，匹配到谁就登录谁。
    连续 A_FAIL_LIMIT 次错误 → 触发全局 A 锁（纯验证码渠道锁 30 分钟）。
    """
    db = SessionLocal()
    try:
        if not _is_code_only(db):
            return JSONResponse(status_code=403, content={"detail": "仅验证码登录未开启"})
        if _code_locked():
            return JSONResponse(status_code=429,
                                content={"detail": "纯验证码登录已锁定 30 分钟，请使用 用户名+密码+验证码 登录"})

        code = req.code.strip()
        users = db.query(User).filter(
            User.totp_enabled == 1, User.totp_secret != ""
        ).all()
        for u in users:
            if pyotp.TOTP(u.totp_secret).verify(code, valid_window=1):
                _code_lock["fail"] = 0  # 成功 → 失败计数清零
                session_token = _issue_web_session(db, u, request)
                return {
                    "success": True,
                    "username": u.username,
                    "permission": u.permission,
                    "token": session_token
                }

        # 无匹配 → 全局失败计数
        _code_lock["fail"] += 1
        if _code_lock["fail"] >= A_FAIL_LIMIT:
            _code_lock["until"] = time.time() + A_LOCK_SECONDS
            _code_lock["fail"] = 0
            return JSONResponse(status_code=429,
                                content={"detail": "验证码错误次数过多，纯验证码登录已锁定 30 分钟，请使用 用户名+密码+验证码 登录"})
        return JSONResponse(status_code=401, content={"detail": "验证码错误或已过期"})
    finally:
        db.close()


@app.get("/api/auth/login-mode")
def login_mode():
    """登录页查询：是否启用仅验证码登录（决定默认表单）"""
    db = SessionLocal()
    try:
        return {"code_only": _is_code_only(db)}
    finally:
        db.close()


# ---- 二次验证(TOTP)管理：设置页使用，需已登录(Web 会话) ----
def _current_user(request: Request, db):
    """从 Authorization header 解析当前 Web 会话用户。"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token_str = auth[7:]
    session_record = db.query(SessionModel).filter(SessionModel.session_token == token_str).first()
    if session_record:
        return db.query(User).filter(User.id == session_record.user_id).first()
    return None


class TwoFACodeRequest(PydanticBase):
    code: str

@app.get("/api/auth/2fa/status")
def twofa_status(request: Request):
    db = SessionLocal()
    try:
        user = _current_user(request, db)
        if not user:
            return JSONResponse(status_code=401, content={"detail": "未登录"})
        return {"username": user.username, "enabled": bool(user.totp_enabled)}
    finally:
        db.close()


@app.post("/api/auth/2fa/setup")
def twofa_setup(request: Request):
    """生成新 TOTP 密钥并返回 otpauth URI(未启用,等待 confirm 确认)"""
    db = SessionLocal()
    try:
        user = _current_user(request, db)
        if not user:
            return JSONResponse(status_code=401, content={"detail": "未登录"})
        secret = pyotp.random_base32()
        user.totp_secret = secret
        user.totp_enabled = 0  # 等待 confirm
        db.commit()
        uri = pyotp.TOTP(secret).provisioning_uri(name=user.username, issuer_name="Shared Center")
        return {"secret": secret, "uri": uri}
    finally:
        db.close()


@app.post("/api/auth/2fa/confirm")
def twofa_confirm(req: TwoFACodeRequest, request: Request):
    """输入 App 当前显示的 6 位码确认 → 正式启用"""
    db = SessionLocal()
    try:
        user = _current_user(request, db)
        if not user or not user.totp_secret:
            return JSONResponse(status_code=400, content={"detail": "请先点击「启用」生成密钥"})
        if not pyotp.TOTP(user.totp_secret).verify(req.code.strip(), valid_window=1):
            return JSONResponse(status_code=400, content={"detail": "验证码错误,请确认 App 与手机时间准确"})
        user.totp_enabled = 1
        db.commit()
        return {"success": True, "message": "二次验证已启用"}
    finally:
        db.close()


@app.post("/api/auth/2fa/disable")
def twofa_disable(req: TwoFACodeRequest, request: Request):
    """输入 6 位码验证后关闭二次验证"""
    db = SessionLocal()
    try:
        user = _current_user(request, db)
        if not user or not user.totp_enabled:
            return JSONResponse(status_code=400, content={"detail": "未启用二次验证"})
        if not pyotp.TOTP(user.totp_secret).verify(req.code.strip(), valid_window=1):
            return JSONResponse(status_code=400, content={"detail": "验证码错误"})
        user.totp_enabled = 0
        user.totp_secret = ""
        db.commit()
        return {"success": True, "message": "二次验证已关闭"}
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
def _current_operator(request: Request, db):
    """解析 Authorization → 当前操作者 User(Web 会话或 API Token)"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token_str = auth[7:]
    session_record = db.query(SessionModel).filter(SessionModel.session_token == token_str).first()
    if session_record:
        return db.query(User).filter(User.id == session_record.user_id).first()
    token_record = db.query(TokenModel).filter(TokenModel.token == token_str).first()
    if token_record and token_record.user_id:
        return db.query(User).filter(User.id == token_record.user_id).first()
    return None


def _require_admin_operator(request: Request, db) -> User | None:
    """用户管理操作:操作者必须是 admin,否则返回 None(调用方返回 403)"""
    op = _current_operator(request, db)
    return op if op and op.permission == "admin" else None


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
def create_user(req: UserCreate, request: Request):
    db = SessionLocal()
    try:
        if not _require_admin_operator(request, db):
            return JSONResponse(status_code=403, content={"detail": "仅管理员可管理用户"})
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
def update_user(user_id: int, req: UserUpdate, request: Request):
    db = SessionLocal()
    try:
        op = _require_admin_operator(request, db)
        if not op:
            return JSONResponse(status_code=403, content={"detail": "仅管理员可管理用户"})
        u = db.query(User).filter(User.id == user_id).first()
        if not u:
            return JSONResponse(status_code=404, content={"detail": "用户不存在"})
        if req.password:
            # 修改自己的密码请走「修改密码」模块(需验证旧密码),用户管理只改其他账户
            if u.id == op.id:
                return JSONResponse(status_code=403,
                                    content={"detail": "请使用「修改密码」模块修改自己的密码（需验证旧密码）"})
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
def delete_user(user_id: int, request: Request):
    db = SessionLocal()
    try:
        if not _require_admin_operator(request, db):
            return JSONResponse(status_code=403, content={"detail": "仅管理员可管理用户"})
        u = db.query(User).filter(User.id == user_id).first()
        if not u:
            return {"success": True, "message": "已删除"}
        # 管理员账号完全禁止删除(防止系统失去管理员;应急恢复用 reset_admin.py)
        if u.permission == "admin":
            return JSONResponse(status_code=403, content={"detail": "管理员账号不允许删除"})
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
