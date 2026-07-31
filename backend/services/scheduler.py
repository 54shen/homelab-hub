# ============================================================
# Shared Center — 共享调度器（供多处模块使用）
# ============================================================
from apscheduler.schedulers.background import BackgroundScheduler

_scheduler: BackgroundScheduler | None = None


def init_scheduler() -> BackgroundScheduler:
    """初始化并返回调度器（main.py 在 lifespan 中调用一次）"""
    global _scheduler
    _scheduler = BackgroundScheduler()
    return _scheduler


def get_scheduler() -> BackgroundScheduler:
    """获取共享调度器实例"""
    if _scheduler is None:
        raise RuntimeError("调度器尚未初始化，请先调用 init_scheduler()")
    return _scheduler
