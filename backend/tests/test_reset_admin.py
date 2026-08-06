# ============================================================
# reset_admin.py 应急脚本测试:重置密码 / 清除 TOTP / 踢会话
# ============================================================
import pyotp

from models import Session as SessionModel, User


def test_reset_password_and_totp(client, admin_headers, db):
    """脚本:重置密码 + 清除 TOTP + 踢掉会话"""
    from reset_admin import run

    # 给 admin 绑定 TOTP + 建一个会话
    secret = pyotp.random_base32()
    u = db.query(User).filter(User.username == "admin").first()
    u.totp_secret = secret
    u.totp_enabled = 1
    db.commit()

    login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.json()["need_2fa"] is True
    session_token = client.post("/api/auth/verify-2fa",
                                json={"username": "admin", "code": pyotp.TOTP(secret).now()}).json()["token"]
    assert db.query(SessionModel).count() >= 1

    # 执行脚本:重置密码 + 清 TOTP
    msg = run("admin", "newpass99", clear_totp=True)
    assert "密码已重置" in msg
    assert "TOTP 二次验证已清除" in msg

    # TOTP 已清、会话已踢
    db.refresh(u)
    assert u.totp_enabled == 0
    assert u.totp_secret == ""
    assert db.query(SessionModel).filter(SessionModel.user_id == u.id).count() == 0

    # 旧密码失效,新密码直接登录(无需验证码)
    assert client.post("/api/auth/login",
                       json={"username": "admin", "password": "admin123"}).status_code == 401
    r = client.post("/api/auth/login", json={"username": "admin", "password": "newpass99"})
    assert r.json()["success"] is True

    # 被踢的旧会话 Token 已失效
    assert client.get("/api/dashboard/stats",
                      headers={"Authorization": f"Bearer {session_token}"}).status_code == 401


def test_reset_unknown_user(client, db):
    from reset_admin import run
    try:
        run("nobody_user", None, True)
        raise AssertionError("应抛出 SystemExit")
    except SystemExit as e:
        assert "不存在" in str(e)


def test_reset_short_password(client, db):
    from reset_admin import run
    try:
        run("admin", "123", True)
        raise AssertionError("应抛出 SystemExit")
    except SystemExit as e:
        assert "6 位" in str(e)


def test_reset_noop(client, db):
    """不传密码也不清 TOTP → 无操作提示"""
    from reset_admin import run
    assert run("admin", None, False) == "未做任何修改"
