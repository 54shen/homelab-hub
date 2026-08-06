# ============================================================
# 管理员密码 / TOTP 重置脚本 — 服务器终端应急工具
#
# 场景:忘记密码 / 手机验证器丢失 / 仅验证码登录被锁且无逃生通道
# 用法(在 backend/ 目录,venv 环境):
#   python reset_admin.py
# 交互式输入:用户名(默认 admin)、新密码(回车跳过)、是否清除 TOTP
#
# 原理:直接操作 SQLite 数据库(与服务器同一份),无需登录、无需重启。
# 执行后该用户的所有 Web 会话被踢下线。
# ============================================================
import sys

from database import SessionLocal
from models import Session as SessionModel, User
from main import hash_password  # 与登录同款 salt:hash 格式


def run(username: str = "admin", new_password: str | None = None,
        clear_totp: bool = False) -> str:
    """核心逻辑(函数化便于测试)。返回结果描述。"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise SystemExit(f"✗ 用户「{username}」不存在")

        messages = []
        if new_password:
            if len(new_password) < 6:
                raise SystemExit("✗ 新密码至少 6 位")
            user.password_hash = hash_password(new_password)
            messages.append("密码已重置")

        if clear_totp:
            user.totp_secret = ""
            user.totp_enabled = 0
            messages.append("TOTP 二次验证已清除")

        # 踢掉该用户所有 Web 会话(密码/TOTP 已变,旧会话不应继续有效)
        kicked = db.query(SessionModel).filter(SessionModel.user_id == user.id).delete()
        if kicked:
            messages.append(f"已踢出 {kicked} 个会话")
        db.commit()
        return "；".join(messages) if messages else "未做任何修改"
    finally:
        db.close()


def main():
    print("=" * 52)
    print(" 管理员密码 / TOTP 重置工具(直接操作数据库)")
    print("=" * 52)
    try:
        username = input("用户名(回车默认 admin): ").strip() or "admin"
        pw = input("新密码(至少 6 位,回车跳过): ").strip()
        totp = input("清除 TOTP 二次验证? [y/N]: ").strip().lower() in ("y", "yes")
        if not pw and not totp:
            print("✗ 未做任何修改:密码与 TOTP 都未选择")
            sys.exit(1)
        msg = run(username, pw or None, totp)
        print(f"✓ 完成: {msg}")
        print(f"  现在可用新密码登录(如需登录后重新绑定验证码,到 设置 → 二次验证)")
    except KeyboardInterrupt:
        print("\n已取消")
        sys.exit(1)
    except SystemExit as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
