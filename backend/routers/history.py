# ============================================================
# Shared Center — 历史记录 API
# (融合 kv-history-viewer:keys/sources/trend/stats 分析端点)
# ============================================================
import math
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import KvHistory
from schemas import (
    HistoryKeyInfo, HistorySource, HistoryStats, KvHistoryListOut,
    KvHistoryOut, TrendPoint, TrendSeries
)

router = APIRouter(prefix="/api", tags=["历史记录"])


def _to_float(v: str | None):
    """严格数值判断:拒绝 '17h 57m'(parseFloat 会误判为 17)、空串、nan/inf。"""
    if v is None:
        return None
    t = v.strip()
    if not t:
        return None
    try:
        f = float(t)
    except ValueError:
        return None
    return f if math.isfinite(f) else None


# 时长单位 → 秒
_DURATION_UNITS = [("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]


def _parse_value(v):
    """将值解析为可绘图的数值。

    支持三种格式,返回 (kind, number) 或 None:
      - number   纯数值,如 32.5
      - duration 时长,如 '1d 5h 53m' / '5h 53m' / '30s'(→ 秒)
      - timestamp 时间戳,如 '2026-08-03T02:58:31'(→ epoch 秒)
    """
    if v is None:
        return None
    v = str(v).strip()

    # 1) 纯数值
    try:
        f = float(v)
        if math.isfinite(f):
            return ("number", f)
    except ValueError:
        pass

    # 2) 时长:Nd Xh Ym Zs(单位可省略,顺序固定,至少一个单位)
    m = re.fullmatch(
        r"\s*(\d+d\s*)?(\d+h\s*)?(\d+m\s*)?(\d+s\s*)?\s*", v
    )
    if m and any(g for g in m.groups()):
        secs = 0
        for i, unit in enumerate(_DURATION_UNITS):
            g = m.group(i + 1)
            if g:
                secs += int(g.split(unit[0])[0]) * unit[1]
        return ("duration", float(secs))

    # 3) 时间戳:YYYY-MM-DDTHH:MM:SS 或带空格/毫秒
    m2 = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(\.\d+)?", v)
    if m2:
        try:
            from datetime import datetime
            ts = datetime.strptime(f"{m2.group(1)} {m2.group(2)}", "%Y-%m-%d %H:%M:%S")
            return ("timestamp", ts.timestamp())
        except ValueError:
            return None

    return None


def _chart_kind(vals):
    """一组取值是否可绘图:全部可解析且格式一致,返回 kind,否则 ''。"""
    kinds = set()
    for v in vals:
        parsed = _parse_value(v)
        if parsed is None:
            return ""
        kinds.add(parsed[0])
        if len(kinds) > 1:
            return ""
    return kinds.pop() if kinds else ""


def _base_query(q, key, search, prefix, suffix, source, start, end):
    """拼装公共过滤条件。"""
    if key:
        q = q.filter(KvHistory.key == key)
    elif search:
        q = q.filter(KvHistory.key.contains(search))
    if prefix:
        q = q.filter(KvHistory.key.startswith(prefix + "."))
    if suffix:
        q = q.filter(KvHistory.key.endswith(suffix))
    if source:
        q = q.filter(KvHistory.source == source)
    if start:
        q = q.filter(KvHistory.changed_at >= start)
    if end:
        q = q.filter(KvHistory.changed_at <= end)
    return q


@router.get("/history", response_model=KvHistoryListOut)
def list_history(
    key: str | None = Query(None, description="精确匹配某个 key"),
    search: str | None = Query(None, description="模糊搜索 key"),
    prefix: str | None = Query(None, description="key 前缀(设备),如 大爷的ROG"),
    suffix: str | None = Query(None, description="key 后缀(指标),如 cpu"),
    source: str | None = Query(None, description="精确匹配来源"),
    start: str | None = Query(None, description="起始时间 YYYY-MM-DD HH:MM:SS"),
    end: str | None = Query(None, description="结束时间"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=50000),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    """分页查询历史记录。key 精确匹配时用 ?key=，模糊搜索用 ?search=。"""
    q = _base_query(db.query(KvHistory), key, search, prefix, suffix, source, start, end)

    total = q.count()
    ordering = KvHistory.changed_at.asc() if order == "asc" else KvHistory.changed_at.desc()
    items = (
        q.order_by(ordering)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return KvHistoryListOut(
        items=[KvHistoryOut(
            id=r.id, key=r.key, old_value=r.old_value, new_value=r.new_value,
            source=r.source, retention_days=r.retention_days, changed_at=r.changed_at
        ) for r in items],
        total=total
    )


@router.get("/history/keys", response_model=list[HistoryKeyInfo])
def history_keys(db: Session = Depends(get_db)):
    """全部键:计数、最新值、来源列表、是否数值型(所有取值均可严格转 float)。"""
    keys = [
        r[0] for r in
        db.query(KvHistory.key).group_by(KvHistory.key).order_by(KvHistory.key).all()
    ]
    result = []
    for k in keys:
        count = db.query(func.count(KvHistory.id)).filter(KvHistory.key == k).scalar() or 0
        latest = (
            db.query(KvHistory.new_value, KvHistory.changed_at)
            .filter(KvHistory.key == k)
            .order_by(KvHistory.id.desc())
            .first()
        )
        sources = [
            s[0] for s in db.query(KvHistory.source)
            .filter(KvHistory.key == k, KvHistory.source.isnot(None), KvHistory.source != "")
            .distinct().all()
        ]
        vals = [
            v[0] for v in db.query(KvHistory.new_value)
            .filter(KvHistory.key == k).distinct().all()
        ]
        plot_kind = _chart_kind(vals) if vals else ""
        result.append(HistoryKeyInfo(
            key=k,
            count=count,
            is_numeric=plot_kind == "number",
            plot_kind=plot_kind,
            latest_value=latest[0] if latest else None,
            latest_changed_at=latest[1] if latest else None,
            sources=sources,
        ))
    return result


@router.get("/history/sources", response_model=list[HistorySource])
def history_sources(db: Session = Depends(get_db)):
    """全部来源:计数(按 count 降序)。"""
    rows = (
        db.query(KvHistory.source, func.count(KvHistory.id).label("count"))
        .filter(KvHistory.source.isnot(None), KvHistory.source != "")
        .group_by(KvHistory.source)
        .order_by(func.count(KvHistory.id).desc())
        .all()
    )
    return [HistorySource(source=r[0], count=r[1]) for r in rows]


@router.get("/history/trend", response_model=TrendSeries)
def history_trend(
    key: str = Query(..., description="必填，查询哪个 key 的数值趋势"),
    source: str | None = Query(None),
    start: str | None = Query(None, description="起始时间 YYYY-MM-DD HH:MM:SS"),
    end: str | None = Query(None, description="结束时间"),
    limit: int = Query(5000, ge=1, le=50000),
    db: Session = Depends(get_db)
):
    """某 key 的趋势序列(支持数值/时长/时间戳,过滤不可解析行,超限等距抽稀)。"""
    q = db.query(KvHistory.changed_at, KvHistory.new_value).filter(KvHistory.key == key)
    if source:
        q = q.filter(KvHistory.source == source)
    if start:
        q = q.filter(KvHistory.changed_at >= start)
    if end:
        q = q.filter(KvHistory.changed_at <= end)
    rows = q.order_by(KvHistory.changed_at.asc(), KvHistory.id.asc()).all()

    points = []
    for changed_at, new_value in rows:
        parsed = _parse_value(new_value)
        if parsed is not None:
            points.append(TrendPoint(
                changed_at=changed_at,
                value=parsed[1],
                raw=str(new_value),
            ))
    if len(points) > limit:
        step = math.ceil(len(points) / limit)
        points = points[::step]
    return TrendSeries(key=key, points=points, count=len(points))


@router.get("/history/stats", response_model=HistoryStats)
def history_stats(db: Session = Depends(get_db)):
    """总览统计:总数、最近变更、最近 24h 各来源与逐小时计数。"""
    total = db.query(func.count(KvHistory.id)).scalar() or 0
    max_changed_at = db.query(func.max(KvHistory.changed_at)).scalar()
    if not max_changed_at:
        return HistoryStats(
            total_records=0, max_changed_at=None, start_24h="",
            per_source=[], per_hour=[]
        )
    start_24h = (
        datetime.strptime(max_changed_at, "%Y-%m-%d %H:%M:%S") - timedelta(hours=24)
    ).strftime("%Y-%m-%d %H:%M:%S")

    per_source = (
        db.query(KvHistory.source, func.count(KvHistory.id).label("count"))
        .filter(KvHistory.changed_at >= start_24h,
                KvHistory.source.isnot(None), KvHistory.source != "")
        .group_by(KvHistory.source)
        .order_by(func.count(KvHistory.id).desc())
        .all()
    )
    hour_expr = func.substr(KvHistory.changed_at, 1, 13).label("hour")
    per_hour = (
        db.query(hour_expr, func.count(KvHistory.id).label("count"))
        .filter(KvHistory.changed_at >= start_24h)
        .group_by(hour_expr)
        .order_by(hour_expr)
        .all()
    )
    return HistoryStats(
        total_records=total,
        max_changed_at=max_changed_at,
        start_24h=start_24h,
        per_source=[HistorySource(source=r[0], count=r[1]) for r in per_source],
        per_hour=[{"hour": r[0], "count": r[1]} for r in per_hour],
    )


@router.get("/history/export")
def export_history(
    key: str | None = Query(None),
    source: str | None = Query(None),
    search: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
    db: Session = Depends(get_db)
):
    """导出历史记录为 CSV（utf-8 BOM，Excel 友好）"""
    from fastapi.responses import StreamingResponse
    import io, csv

    q = _base_query(db.query(KvHistory), key, search, source, start, end)
    rows = q.order_by(KvHistory.changed_at.desc()).all()

    buf = io.StringIO()
    buf.write("﻿")  # UTF-8 BOM
    writer = csv.writer(buf)
    writer.writerow(["ID", "Key", "Old Value", "New Value", "Source", "Changed At"])
    for r in rows:
        writer.writerow([r.id, r.key, r.old_value or "(新增)", r.new_value, r.source, r.changed_at])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue().encode("utf-8")]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
    )
