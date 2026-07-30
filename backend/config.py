# ============================================================
# Shared Center — 配置
# ============================================================
import os
from dotenv import load_dotenv

# 从项目根目录加载 .env
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT_DIR, ".env"))

# 数据库
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'data', 'shared_center.db')}")

# JWT
SECRET_KEY = os.getenv("SECRET_KEY", "shared-center-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24h

# 清理
DEFAULT_RETENTION_DAYS = int(os.getenv("DEFAULT_RETENTION_DAYS", "180"))
CLEANUP_INTERVAL_HOURS = int(os.getenv("CLEANUP_INTERVAL_HOURS", "24"))
HEARTBEAT_TIMEOUT_SECONDS = int(os.getenv("HEARTBEAT_TIMEOUT_SECONDS", "60"))

# 认证
AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "false").lower() in ("true", "1", "yes")

# 服务
API_PREFIX = "/api"
