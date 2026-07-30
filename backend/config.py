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

# 清理
DEFAULT_RETENTION_DAYS = int(os.getenv("DEFAULT_RETENTION_DAYS", "180"))
CLEANUP_INTERVAL_HOURS = int(os.getenv("CLEANUP_INTERVAL_HOURS", "24"))
HEARTBEAT_TIMEOUT_SECONDS = int(os.getenv("HEARTBEAT_TIMEOUT_SECONDS", "60"))
DEFAULT_HEARTBEAT_TIMEOUT = int(os.getenv("DEFAULT_HEARTBEAT_TIMEOUT", "180"))

# 服务
API_PREFIX = "/api"
