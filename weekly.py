"""Weekly WHOOP snapshot archival and comparison helpers."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


COLLECTIONS = ("recovery", "sleep", "cycle", "workout")
TIME_FIELDS = {
    "recovery": "created_at",
    "sleep": "start",
    "cycle": "start",
    "workout": "start",
}


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def week_key(value: datetime) -> str:
    iso = value.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def week_bounds(key: str) -> tuple[datetime, datetime]:
    year, week = key.split("-W")
    start = datetime.fromisocalendar(int(year), int(week), 1).replace(tzinfo=timezone.utc)
    return start, start + timedelta(days=7)


def record_time(record: dict[str, Any], collection: str) -> datetime | None:
    return parse_time(record.get(TIME_FIELDS[collection]))


def record_identity(record: dict[str, Any]) -> str:
    if record.get("id"):
        return str(record["id"])
    return "|".join(str(record.get(key, "")) for key in ("created_at", "start", "end"))


def merge_records(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = {record_identity(record): record for record in existing}
    merged.update({record_identity(record): record for record in incoming})
    return sorted(merged.values(), key=lambda row: str(row.get("start") or row.get("created_at") or ""))


def archive_snapshot(snapshot: dict[str, Any], week_dir: Path) -> list[Path]:
    """Partition a fetched snapshot into ISO weeks and merge it into weekly files."""
    buckets: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for collection in COLLECTIONS:
        for record in snapshot.get(collection, []):
            timestamp = record_time(record, collection)
            if not timestamp:
                continue
            bucket = buckets.setdefault(week_key(timestamp), {name: [] for name in COLLECTIONS})
            bucket[collection].append(record)

    week_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for key, records in sorted(buckets.items()):
        path = week_dir / f"{key}.json"
        existing: dict[str, Any] = {}
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
        start, end = week_bounds(key)
        archived: dict[str, Any] = {
            "week": key,
            "week_start": start.isoformat(),
            "week_end": end.isoformat(),
            "updated_at": snapshot.get("fetched_at") or datetime.now(timezone.utc).isoformat(),
        }
        for collection in COLLECTIONS:
            archived[collection] = merge_records(existing.get(collection, []), records[collection])
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=week_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(archived, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        written.append(path)
    return written


def load_weekly_snapshots(week_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    snapshots: list[tuple[Path, dict[str, Any]]] = []
    if not week_dir.exists():
        return snapshots
    for path in sorted(week_dir.glob("????-W??.json")):
        snapshots.append((path, json.loads(path.read_text(encoding="utf-8"))))
    return snapshots


def has_health_data(snapshot: dict[str, Any]) -> bool:
    return any(snapshot.get(name) for name in ("recovery", "sleep", "cycle"))


def coverage_days(snapshot: dict[str, Any]) -> int:
    dates: set[str] = set()
    for collection in COLLECTIONS:
        for record in snapshot.get(collection, []):
            timestamp = record_time(record, collection)
            if timestamp:
                dates.add(timestamp.date().isoformat())
    return len(dates)


def average(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def score_of(record: dict[str, Any]) -> dict[str, Any]:
    score = record.get("score")
    return score if isinstance(score, dict) else {}


def sleep_milliseconds(record: dict[str, Any]) -> float:
    stages = score_of(record).get("stage_summary") or {}
    return sum(float(stages.get(key) or 0) for key in (
        "total_light_sleep_time_milli",
        "total_slow_wave_sleep_time_milli",
        "total_rem_sleep_time_milli",
    ))


def summarize_week(snapshot: dict[str, Any]) -> dict[str, float | int | str | None]:
    recovery_scores = [
        float(score_of(row).get("recovery_score"))
        for row in snapshot.get("recovery", [])
        if row.get("score_state") == "SCORED" and score_of(row).get("recovery_score") is not None
    ]
    main_sleeps = [
        row for row in snapshot.get("sleep", [])
        if row.get("score_state") == "SCORED" and not row.get("nap")
    ]
    sleep_hours = [sleep_milliseconds(row) / 3_600_000 for row in main_sleeps]
    performance = [
        float(score_of(row).get("sleep_performance_percentage"))
        for row in main_sleeps if score_of(row).get("sleep_performance_percentage") is not None
    ]
    consistency = [
        float(score_of(row).get("sleep_consistency_percentage"))
        for row in main_sleeps if score_of(row).get("sleep_consistency_percentage") is not None
    ]
    cycle_strain = [
        float(score_of(row).get("strain"))
        for row in snapshot.get("cycle", [])
        if row.get("score_state") == "SCORED" and score_of(row).get("strain") is not None
    ]
    workout_strain = [
        float(score_of(row).get("strain"))
        for row in snapshot.get("workout", []) if score_of(row).get("strain") is not None
    ]
    return {
        "week": snapshot.get("week", "—"),
        "coverage_days": coverage_days(snapshot),
        "recovery_avg": average(recovery_scores),
        "sleep_hours_avg": average(sleep_hours),
        "sleep_performance_avg": average(performance),
        "sleep_consistency_avg": average(consistency),
        "cycle_strain_avg": average(cycle_strain),
        "workout_count": len(snapshot.get("workout", [])),
        "workout_strain_total": sum(workout_strain),
    }


def compare_weeks(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    current_summary = summarize_week(current)
    previous_summary = summarize_week(previous) if previous else None
    deltas: dict[str, float | None] = {}
    for key in (
        "recovery_avg", "sleep_hours_avg", "sleep_performance_avg",
        "sleep_consistency_avg", "cycle_strain_avg", "workout_count", "workout_strain_total",
    ):
        before = previous_summary.get(key) if previous_summary else None
        after = current_summary.get(key)
        deltas[key] = float(after) - float(before) if after is not None and before is not None else None

    suggestions: list[str] = []
    previous_core_available = bool(previous_summary and (
        previous_summary.get("recovery_avg") is not None
        or previous_summary.get("sleep_performance_avg") is not None
    ))
    if not previous_summary:
        suggestions.append("这是首个可比较周；再积累一周后会自动生成环比建议。")
    elif not previous_core_available:
        suggestions.append("上一周缺少恢复或睡眠数据，目前只能比较训练负荷；再积累一周后复核完整环比。")
    else:
        recovery_delta = deltas["recovery_avg"]
        sleep_delta = deltas["sleep_hours_avg"]
        performance_delta = deltas["sleep_performance_avg"]
        load_delta = deltas["workout_strain_total"]
        if recovery_delta is not None and recovery_delta <= -8:
            suggestions.append("平均恢复明显下降，下一周优先安排低强度训练或额外恢复日。")
        elif recovery_delta is not None and recovery_delta >= 8:
            suggestions.append("平均恢复明显改善，可在主观状态良好时逐步增加训练负荷。")
        if sleep_delta is not None and sleep_delta <= -0.5:
            suggestions.append("平均睡眠减少超过 30 分钟，建议固定就寝时间并补足睡眠机会。")
        if performance_delta is not None and performance_delta <= -8:
            suggestions.append("睡眠表现下降，建议检查晚间训练、酒精、咖啡因或作息变化。")
        if load_delta is not None and load_delta >= 15 and recovery_delta is not None and recovery_delta < 0:
            suggestions.append("训练负荷上升但恢复下降，建议下周控制总 Strain，避免连续高负荷。")
        if not suggestions:
            suggestions.append("本周关键指标整体稳定，继续保持当前睡眠与训练节奏。")
    if int(current_summary["coverage_days"] or 0) < 5:
        suggestions.append("本周数据覆盖不足 5 天，环比仅作趋势参考，周末后再复核。")
    if previous_summary and int(previous_summary["coverage_days"] or 0) < 5:
        suggestions.append("上一周数据覆盖不足 5 天，变化值可能偏差较大。")
    return {"current": current_summary, "previous": previous_summary, "deltas": deltas, "suggestions": suggestions}
