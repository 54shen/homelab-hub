# ============================================================
# 认证模块测试:密码哈希 / 登录 / TOTP 二次验证 / 会话 / Token / 用户
# ============================================================
import pyotp

from main import hash_password, verify_password


# ---- 纯函数:密码哈希 ----

def test_hash_password_roundtrip():
    hashed = hash_password("mypass")
    assert hashed != "mypass"              # 绝不存明文
    assert ":" in hashed                   # 盐:哈希 格式
    assert verify_password("mypass", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("mypass")
    assert verify_password("wrong", hashed) is False


def test_verify_password_malformed_hash():
    """格式非法的哈希 → False 而不是崩溃"""
    assert verify_password("x", "not-a-valid-hash") is False


def test_hash_password_salt_is_random():
    """两次哈希同一密码,结果必须不同(随机盐)"""
    assert hash_password("same") != hash_password("same")


# ---- 登录 ----

def test_login_success(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["permission"] == "admin"
    assert body["token"].startswith("ws-")   # Web 会话专用前缀


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
    assert r.status_code == 401


# ---- TOTP 二次验证完整流程(用独立用户,不动 admin) ----

def test_2fa_full_flow(client, admin_headers):
    # 新建独立用户(自动生成一个 API Token)。
    # 注意:2FA 管理接口 (2fa/setup 等) 是写操作,该用户必须是 admin/write 权限
    r = client.post("/api/users", json={"username": "2fa_user", "password": "pass1234", "permission": "admin"},
                    headers=admin_headers)
    assert r.status_code == 200

    # 首次登录 → 未启用 2FA,直接发会话
    r = client.post("/api/auth/login", json={"username": "2fa_user", "password": "pass1234"})
    assert r.json()["success"] is True
    ua_headers = {"Authorization": f"Bearer {r.json()['token']}"}

    # 启用 2FA → 拿到 secret
    r = client.post("/api/auth/2fa/setup", headers=ua_headers)
    assert r.status_code == 200
    secret = r.json()["secret"]

    # 错误验证码确认 → 400
    r = client.post("/api/auth/2fa/confirm", json={"code": "000000"}, headers=ua_headers)
    assert r.status_code == 400

    # 正确验证码确认 → 启用成功
    r = client.post("/api/auth/2fa/confirm", json={"code": pyotp.TOTP(secret).now()},
                    headers=ua_headers)
    assert r.status_code == 200

    # 状态查询 → 已启用
    r = client.get("/api/auth/2fa/status", headers=ua_headers)
    assert r.json()["enabled"] is True

    # 再次登录 → 要求二次验证
    r = client.post("/api/auth/login", json={"username": "2fa_user", "password": "pass1234"})
    body = r.json()
    assert body["success"] is False and body["need_2fa"] is True

    # 第二步:错误验证码 → 401
    r = client.post("/api/auth/verify-2fa", json={"username": "2fa_user", "code": "000000"})
    assert r.status_code == 401

    # 第二步:正确验证码 → 发会话
    r = client.post("/api/auth/verify-2fa", json={"username": "2fa_user", "code": pyotp.TOTP(secret).now()})
    assert r.status_code == 200
    assert r.json()["success"] is True
    new_headers = {"Authorization": f"Bearer {r.json()['token']}"}

    # 关闭 2FA(验证码正确)
    r = client.post("/api/auth/2fa/disable", json={"code": pyotp.TOTP(secret).now()}, headers=new_headers)
    assert r.status_code == 200

    # 关闭后登录 → 直接发会话
    r = client.post("/api/auth/login", json={"username": "2fa_user", "password": "pass1234"})
    assert r.json()["success"] is True


def test_2fa_confirm_without_setup(client, admin_headers):
    """未生成密钥就 confirm → 400"""
    r = client.post("/api/auth/2fa/confirm", json={"code": "123456"}, headers=admin_headers)
    assert r.status_code == 400


def test_2fa_verify_for_unenabled_user(client):
    """未启用 2FA 的账号走 verify-2fa → 401"""
    r = client.post("/api/auth/verify-2fa", json={"username": "admin", "code": "000000"})
    assert r.status_code == 401


# ---- 修改密码 ----

def test_change_password_flow(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    h = {"Authorization": f"Bearer {r.json()['token']}"}

    r = client.put("/api/auth/password",
                   json={"username": "admin", "old_password": "admin123", "new_password": "newpass9"},
                   headers=h)
    assert r.status_code == 200

    # 旧密码立即失效
    assert client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).status_code == 401
    # 新密码可登录
    assert client.post("/api/auth/login", json={"username": "admin", "password": "newpass9"}).status_code == 200


def test_change_password_wrong_old(client, admin_headers):
    r = client.put("/api/auth/password",
                   json={"username": "admin", "old_password": "bad", "new_password": "whatever"},
                   headers=admin_headers)
    assert r.status_code == 400


def test_change_password_too_short(client, admin_headers):
    r = client.put("/api/auth/password",
                   json={"username": "admin", "old_password": "admin123", "new_password": "123"},
                   headers=admin_headers)
    assert r.status_code == 400


# ---- 会话管理 ----

def test_sessions_flow(client, admin_headers, db):
    # 再登录一次,产生第二个会话
    other_token = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).json()["token"]
    sessions = client.get("/api/sessions", headers=admin_headers).json()
    assert len(sessions) >= 2

    # 列表接口不返回 session_token,直接从库中查
    from models import Session as SessionModel
    other_id = db.query(SessionModel).filter(SessionModel.session_token == other_token).first().id
    # 删除别人的会话
    r = client.delete(f"/api/sessions/{other_id}", headers=admin_headers)
    assert r.status_code == 200
    # 被删除的会话立即失效
    assert client.get("/api/sessions", headers={"Authorization": f"Bearer {other_token}"}).status_code == 401


def test_kick_all_sessions(client, admin_headers):
    other_token = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).json()["token"]
    r = client.post("/api/sessions/kick-all", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["deleted"] >= 1
    # 被踢的会话失效,当前会话仍有效
    assert client.get("/api/sessions", headers={"Authorization": f"Bearer {other_token}"}).status_code == 401
    assert client.get("/api/sessions", headers=admin_headers).status_code == 200


def test_kick_all_without_token(client):
    assert client.post("/api/sessions/kick-all").status_code == 401


# ---- Token 管理 + 权限 ----

def test_token_crud_and_permissions(client, admin_headers):
    # 创建 read Token
    r = client.post("/api/tokens", json={"name": "测试读Token", "permission": "read"}, headers=admin_headers)
    assert r.status_code == 200
    read_token = r.json()["token"]
    assert read_token.startswith("sk-")
    read_headers = {"Authorization": f"Bearer {read_token}"}

    # read 权限:可以读(KV 列表实际路由是 /api/list)
    assert client.get("/api/list", headers=read_headers).status_code == 200
    # read 权限:不能写 → 403
    assert client.post("/api/kv", json={"key": "t", "value": "1"}, headers=read_headers).status_code == 403

    # 列表展示(名称 + 脱敏 token)
    tokens = client.get("/api/tokens", headers=admin_headers).json()
    tid = next(t["id"] for t in tokens if t["name"] == "测试读Token")
    masked = next(t["token"] for t in tokens if t["name"] == "测试读Token")
    assert "••••" in masked                      # 中间部分被脱敏
    assert masked != read_token                  # 且不等于完整 Token

    # 升级为 write → 可以写
    r = client.put(f"/api/tokens/{tid}", json={"permission": "write"}, headers=admin_headers)
    assert r.status_code == 200
    assert client.post("/api/kv", json={"key": "t", "value": "1"}, headers=read_headers).status_code == 200

    # 删除 → 立即失效
    r = client.delete(f"/api/tokens/{tid}", headers=admin_headers)
    assert r.status_code == 200
    assert client.get("/api/list", headers=read_headers).status_code == 401


# ---- 用户管理 ----

def test_users_crud(client, admin_headers):
    r = client.post("/api/users", json={"username": "u1", "password": "pass1234"}, headers=admin_headers)
    assert r.status_code == 200
    uid = r.json()["id"]

    # 重名 → 400
    assert client.post("/api/users", json={"username": "u1", "password": "pass1234"}, headers=admin_headers).status_code == 400
    # 密码过短 → 400
    assert client.post("/api/users", json={"username": "u2", "password": "1"}, headers=admin_headers).status_code == 400

    # 列表
    users = client.get("/api/users", headers=admin_headers).json()
    assert any(u["username"] == "u1" for u in users)

    # 更新密码
    assert client.put(f"/api/users/{uid}", json={"password": "newpass9"}, headers=admin_headers).status_code == 200
    # 删除
    assert client.delete(f"/api/users/{uid}", headers=admin_headers).status_code == 200
    users = client.get("/api/users", headers=admin_headers).json()
    assert not any(u["username"] == "u1" for u in users)


# ---- 认证中间件 ----

def test_middleware_requires_token(client):
    assert client.get("/api/kv/list").status_code == 401


def test_middleware_invalid_token(client):
    r = client.get("/api/kv/list", headers={"Authorization": "Bearer sk-invalid"})
    assert r.status_code == 401


def test_public_paths_need_no_token(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/").status_code == 200
