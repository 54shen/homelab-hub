# ============================================================
# 仅验证码登录 + 全局A锁/B锁 测试
# 覆盖:login-mode / totp-login 匹配 / A锁(5错→30分钟,管理员B成功重置) /
#      B锁(按用户名 5错→1分钟,独立) / ticket 一次性与过期 / 开关关闭回归
# ============================================================
import time

import pytest
import pyotp

import main as main_module
from constants import AUTH_CODE_ONLY_KEY
from models import User, UISetting

SECRET_A = pyotp.random_base32()
SECRET_B = pyotp.random_base32()
WRONG_CODE = "000000"  # 与有效码碰撞概率 1/100 万,测试可忽略


@pytest.fixture(autouse=True)
def _reset_locks():
    """内存锁/ticket 状态每个测试前清空(重启清零语义)"""
    main_module._code_lock["fail"] = 0
    main_module._code_lock["until"] = 0.0
    main_module._b_locks.clear()
    main_module._login_tickets.clear()
    yield


def _enable_code_only(db):
    db.add(UISetting(key=AUTH_CODE_ONLY_KEY, value="1"))
    db.commit()


def _bind_totp(db, username: str, secret: str):
    u = db.query(User).filter(User.username == username).first()
    u.totp_secret = secret
    u.totp_enabled = 1
    db.commit()


def _create_user(client, admin_headers, username: str):
    r = client.post("/api/users", json={"username": username, "password": "pass1234", "permission": "read"},
                    headers=admin_headers)
    assert r.status_code == 200


def _trigger_a_lock(client, db):
    """纯验证码连错 5 次 → 触发全局 A 锁,返回锁定时错误码"""
    for _ in range(4):
        assert client.post("/api/auth/totp-login", json={"code": WRONG_CODE}).status_code == 401
    return client.post("/api/auth/totp-login", json={"code": WRONG_CODE})


# ---- login-mode ----

def test_login_mode_default_off(client):
    assert client.get("/api/auth/login-mode").json() == {"code_only": False}


def test_login_mode_on_after_switch(client, db):
    _enable_code_only(db)
    assert client.get("/api/auth/login-mode").json() == {"code_only": True}


# ---- totp-login（A 路径） ----

def test_totp_login_requires_switch(client):
    r = client.post("/api/auth/totp-login", json={"code": "123456"})
    assert r.status_code == 403
    assert "未开启" in r.json()["detail"]


def test_totp_login_matches_user(client, admin_headers, db):
    """开关开启 + 绑定用户 → 纯验证码免密码登录成功"""
    _enable_code_only(db)
    _bind_totp(db, "admin", SECRET_A)
    r = client.post("/api/auth/totp-login", json={"code": pyotp.TOTP(SECRET_A).now()})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["username"] == "admin"
    assert body["permission"] == "admin"
    assert body["token"].startswith("ws-")

    # 错误码 → 401
    assert client.post("/api/auth/totp-login", json={"code": WRONG_CODE}).status_code == 401


def test_totp_login_two_users_each_matches_own(client, admin_headers, db):
    """多个绑定用户:各自的验证码登录各自账号"""
    _enable_code_only(db)
    _create_user(client, admin_headers, "u_a")
    _create_user(client, admin_headers, "u_b")
    _bind_totp(db, "u_a", SECRET_A)
    _bind_totp(db, "u_b", SECRET_B)

    r = client.post("/api/auth/totp-login", json={"code": pyotp.TOTP(SECRET_A).now()})
    assert r.json()["username"] == "u_a"
    r = client.post("/api/auth/totp-login", json={"code": pyotp.TOTP(SECRET_B).now()})
    assert r.json()["username"] == "u_b"


def test_totp_login_ignores_unbound_user(client, admin_headers, db):
    """未绑定用户不在匹配列表(输验证码永远匹配不到)"""
    _enable_code_only(db)
    _bind_totp(db, "admin", SECRET_A)
    _create_user(client, admin_headers, "u_unbound")
    assert client.post("/api/auth/totp-login", json={"code": WRONG_CODE}).status_code == 401


# ---- 全局 A 锁 ----

def test_a_lock_after_5_failures(client, admin_headers, db):
    """纯验证码连错 5 次 → 全局锁 30 分钟;锁定期内纯验证码 429(码对也不行)"""
    _enable_code_only(db)
    _bind_totp(db, "admin", SECRET_A)

    r = _trigger_a_lock(client, db)
    assert r.status_code == 429
    assert "锁定 30 分钟" in r.json()["detail"]

    # 锁定期内:正确验证码也 429
    r = client.post("/api/auth/totp-login", json={"code": pyotp.TOTP(SECRET_A).now()})
    assert r.status_code == 429


def test_a_lock_keeps_b_path_available(client, admin_headers, db):
    """A 锁期间:B(用户名+密码+验证码)仍可用"""
    _enable_code_only(db)
    _bind_totp(db, "admin", SECRET_A)
    _trigger_a_lock(client, db)

    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    body = r.json()
    assert body["need_2fa"] is True and body["ticket"]
    r = client.post("/api/auth/verify-2fa",
                    json={"username": "admin", "code": pyotp.TOTP(SECRET_A).now(), "ticket": body["ticket"]})
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_a_lock_reset_by_admin_b_login(client, admin_headers, db):
    """管理员 B 登录成功 → 重置全局 A 锁(纯验证码立即恢复)"""
    _enable_code_only(db)
    _bind_totp(db, "admin", SECRET_A)
    _trigger_a_lock(client, db)

    # 管理员 B 完整登录
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    r = client.post("/api/auth/verify-2fa",
                    json={"username": "admin", "code": pyotp.TOTP(SECRET_A).now(), "ticket": r.json()["ticket"]})
    assert r.status_code == 200

    # 锁已重置:错误码恢复 401(而非 429),正确码可登录
    assert client.post("/api/auth/totp-login", json={"code": WRONG_CODE}).status_code == 401
    assert client.post("/api/auth/totp-login",
                       json={"code": pyotp.TOTP(SECRET_A).now()}).status_code == 200


def test_a_lock_not_reset_by_normal_user(client, admin_headers, db):
    """非管理员 B 登录成功 → 不重置全局 A 锁"""
    _enable_code_only(db)
    _bind_totp(db, "admin", SECRET_A)
    _create_user(client, admin_headers, "u_norm")
    _bind_totp(db, "u_norm", SECRET_B)
    _trigger_a_lock(client, db)

    r = client.post("/api/auth/login", json={"username": "u_norm", "password": "pass1234"})
    r = client.post("/api/auth/verify-2fa",
                    json={"username": "u_norm", "code": pyotp.TOTP(SECRET_B).now(), "ticket": r.json()["ticket"]})
    assert r.status_code == 200

    # 全局锁仍生效
    assert client.post("/api/auth/totp-login",
                       json={"code": pyotp.TOTP(SECRET_A).now()}).status_code == 429


def test_a_lock_expires_after_timeout(client, admin_headers, db):
    """30 分钟到期自动恢复(直接拨快内存时间)"""
    _enable_code_only(db)
    _bind_totp(db, "admin", SECRET_A)
    _trigger_a_lock(client, db)

    main_module._code_lock["until"] = time.time() - 1  # 模拟 30 分钟到期
    assert client.post("/api/auth/totp-login",
                       json={"code": pyotp.TOTP(SECRET_A).now()}).status_code == 200


# ---- B 锁(按用户名,1 分钟) ----

def test_b_lock_by_username(client, admin_headers, db):
    """B 路径连错 5 次(密码错)→ 该用户名锁 1 分钟;到期恢复"""
    _enable_code_only(db)
    _bind_totp(db, "admin", SECRET_A)

    for _ in range(5):
        assert client.post("/api/auth/login",
                           json={"username": "admin", "password": "wrong"}).status_code == 401

    # 密码正确也被锁 → 429
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 429
    assert "锁定 1 分钟" in r.json()["detail"]

    # 到期(拨快时间)→ 恢复
    main_module._b_locks["admin"][1] = time.time() - 1
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    assert r.json()["need_2fa"] is True


def test_b_lock_independent_per_user(client, admin_headers, db):
    """B 锁按用户名独立:锁 admin 不影响其他用户"""
    _enable_code_only(db)
    _bind_totp(db, "admin", SECRET_A)
    _create_user(client, admin_headers, "u_ok")
    _bind_totp(db, "u_ok", SECRET_B)

    for _ in range(5):
        client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert client.post("/api/auth/login",
                       json={"username": "admin", "password": "admin123"}).status_code == 429

    # 其他用户 B 正常
    r = client.post("/api/auth/login", json={"username": "u_ok", "password": "pass1234"})
    assert r.status_code == 200
    assert r.json()["need_2fa"] is True


def test_b_lock_cleared_on_success(client, admin_headers, db):
    """B 登录成功 → 该用户名 B 锁计数清零(再错 4 次不触发)"""
    _enable_code_only(db)
    _bind_totp(db, "admin", SECRET_A)

    for _ in range(4):
        client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    # 第 5 次:密码对 → 成功进入 need_2fa(第 5 次密码错才触发锁,对则清零)
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    r = client.post("/api/auth/verify-2fa",
                    json={"username": "admin", "code": pyotp.TOTP(SECRET_A).now(), "ticket": r.json()["ticket"]})
    assert r.status_code == 200
    # 成功后清零:再错 4 次不锁
    for _ in range(4):
        client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200


# ---- ticket ----

def test_verify_2fa_requires_ticket_when_code_only(client, admin_headers, db):
    """开关开启:verify-2fa 不带 ticket → 401(纯验证码走 totp-login,防止绕过密码暴破)"""
    _enable_code_only(db)
    _bind_totp(db, "admin", SECRET_A)
    r = client.post("/api/auth/verify-2fa",
                    json={"username": "admin", "code": pyotp.TOTP(SECRET_A).now()})
    assert r.status_code == 401
    assert "账号密码验证" in r.json()["detail"]


def test_ticket_single_use(client, admin_headers, db):
    """ticket 一次性:用后即焚,同 ticket 再试 → 401"""
    _enable_code_only(db)
    _bind_totp(db, "admin", SECRET_A)
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    ticket = r.json()["ticket"]

    r = client.post("/api/auth/verify-2fa",
                    json={"username": "admin", "code": pyotp.TOTP(SECRET_A).now(), "ticket": ticket})
    assert r.status_code == 200
    r = client.post("/api/auth/verify-2fa",
                    json={"username": "admin", "code": pyotp.TOTP(SECRET_A).now(), "ticket": ticket})
    assert r.status_code == 401


def test_ticket_expired(client, admin_headers, db):
    """ticket 过期(5 分钟)→ 401"""
    _enable_code_only(db)
    _bind_totp(db, "admin", SECRET_A)
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    ticket = r.json()["ticket"]
    main_module._login_tickets[ticket][1] = time.time() - 1  # 改为已过期

    r = client.post("/api/auth/verify-2fa",
                    json={"username": "admin", "code": pyotp.TOTP(SECRET_A).now(), "ticket": ticket})
    assert r.status_code == 401


def test_ticket_wrong_username(client, admin_headers, db):
    """ticket 与用户名不匹配 → 401"""
    _enable_code_only(db)
    _bind_totp(db, "admin", SECRET_A)
    _create_user(client, admin_headers, "u_other")
    _bind_totp(db, "u_other", SECRET_B)

    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    ticket = r.json()["ticket"]
    # 用 u_other 的验证码 + admin 的 ticket → 401
    r = client.post("/api/auth/verify-2fa",
                    json={"username": "u_other", "code": pyotp.TOTP(SECRET_B).now(), "ticket": ticket})
    assert r.status_code == 401


# ---- 开关关闭回归 ----

def test_switch_off_existing_flow_unchanged(client, admin_headers, db):
    """开关关闭:现有两步登录流程照旧(login need_2fa + verify-2fa 不带 ticket 也可用)"""
    _bind_totp(db, "admin", SECRET_A)
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.json()["need_2fa"] is True
    r = client.post("/api/auth/verify-2fa",
                    json={"username": "admin", "code": pyotp.TOTP(SECRET_A).now()})
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_switch_off_no_b_lock(client, admin_headers, db):
    """开关关闭:密码错不触发 B 锁(行为与现状一致)"""
    _bind_totp(db, "admin", SECRET_A)
    for _ in range(8):
        assert client.post("/api/auth/login",
                           json={"username": "admin", "password": "wrong"}).status_code == 401
    # 密码对 → 正常 need_2fa(无 429)
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
