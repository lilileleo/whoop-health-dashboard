#!/usr/bin/env python3
"""Turn a WHOOP snapshot into a Chinese Markdown report and local HTML dashboard."""

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from weekly import compare_weeks, has_health_data, load_weekly_snapshots


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "data" / "latest.json"
REPORT_DIR = ROOT / "reports"
WEEK_DATA_DIR = ROOT / "data" / "weeks"
WEEK_REPORT_DIR = REPORT_DIR / "weeks"


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def record_time(record: dict[str, Any], field: str = "start") -> datetime:
    return parse_time(record.get(field)) or datetime.min.replace(tzinfo=timezone.utc)


def local_time(value: str | None, offset: str | None = None) -> str:
    parsed = parse_time(value)
    if not parsed:
        return "—"
    if offset and len(offset) == 6:
        sign = 1 if offset[0] == "+" else -1
        hours, minutes = map(int, offset[1:].split(":"))
        parsed = parsed.astimezone(timezone(sign * timedelta(hours=hours, minutes=minutes)))
    return f"{parsed.month:02d}月{parsed.day:02d}日 {parsed.hour:02d}:{parsed.minute:02d}"


def duration(milliseconds: float | int | None) -> str:
    total_minutes = round((milliseconds or 0) / 60_000)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}小时{minutes:02d}分" if hours else f"{minutes}分钟"


def sleep_duration(sleep: dict[str, Any] | None) -> int:
    if not sleep:
        return 0
    stages = record_score(sleep).get("stage_summary") or {}
    return int(sum(stages.get(key) or 0 for key in (
        "total_light_sleep_time_milli",
        "total_slow_wave_sleep_time_milli",
        "total_rem_sleep_time_milli",
    )))


def fmt(value: Any, digits: int = 0, suffix: str = "") -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}{suffix}"


def delta_fmt(value: Any, digits: int = 1, suffix: str = "") -> str:
    if value is None:
        return "—"
    number = float(value)
    return f"{number:+.{digits}f}{suffix}"


def comparison_rows(comparison: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    current = comparison["current"]
    previous = comparison["previous"] or {}
    deltas = comparison["deltas"]
    specs = (
        ("平均恢复", "recovery_avg", 1, " 分"),
        ("平均睡眠", "sleep_hours_avg", 2, " 小时"),
        ("睡眠表现", "sleep_performance_avg", 1, "%"),
        ("睡眠一致性", "sleep_consistency_avg", 1, "%"),
        ("平均周期 Strain", "cycle_strain_avg", 1, ""),
        ("活动次数", "workout_count", 0, " 次"),
        ("活动总 Strain", "workout_strain_total", 1, ""),
    )
    return [
        (
            label,
            fmt(current.get(key), digits, suffix),
            fmt(previous.get(key), digits, suffix),
            delta_fmt(deltas.get(key), digits, suffix),
        )
        for label, key, digits, suffix in specs
    ]


def pct(value: Any) -> float:
    return max(0.0, min(100.0, float(value or 0)))


def record_score(record: dict[str, Any] | None) -> dict[str, Any]:
    score = (record or {}).get("score")
    return score if isinstance(score, dict) else {}


def latest_scored(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    scored = [record for record in records if record.get("score_state") == "SCORED"]
    return max(scored, key=record_time) if scored else None


def build_context(data: dict[str, Any]) -> dict[str, Any]:
    recoveries = sorted(data.get("recovery", []), key=lambda item: item.get("created_at", ""), reverse=True)
    sleeps = sorted(data.get("sleep", []), key=record_time, reverse=True)
    cycles = sorted(data.get("cycle", []), key=record_time, reverse=True)
    workouts = sorted(data.get("workout", []), key=record_time, reverse=True)
    recovery = latest_scored(recoveries)
    recovery_sleep = None
    if recovery:
        recovery_sleep = next((item for item in sleeps if item.get("id") == recovery.get("sleep_id")), None)
    main_sleep = recovery_sleep or next((item for item in sleeps if not item.get("nap") and item.get("score_state") == "SCORED"), None)
    cycle = latest_scored(cycles)
    sleep_score = record_score(main_sleep)
    stages = sleep_score.get("stage_summary", {})
    recovery_score = record_score(recovery)
    cycle_score = record_score(cycle)
    stage_values = {
        "浅睡": int(stages.get("total_light_sleep_time_milli") or 0),
        "深睡": int(stages.get("total_slow_wave_sleep_time_milli") or 0),
        "REM": int(stages.get("total_rem_sleep_time_milli") or 0),
    }
    naps = [item for item in sleeps if item.get("nap") and item.get("score_state") == "SCORED"]
    return {
        "data": data, "recoveries": recoveries, "sleeps": sleeps, "cycles": cycles,
        "workouts": workouts, "recovery": recovery, "main_sleep": main_sleep, "cycle": cycle,
        "recovery_score": recovery_score, "sleep_score": sleep_score, "cycle_score": cycle_score,
        "stages": stages, "stage_values": stage_values, "total_sleep": sleep_duration(main_sleep),
        "naps": naps, "odd_naps": [item for item in naps if sleep_duration(item) >= 6 * 60 * 60 * 1000],
    }


def markdown_report(ctx: dict[str, Any]) -> str:
    recovery, main_sleep, cycle = ctx["recovery"], ctx["main_sleep"], ctx["cycle"]
    rs, ss, cs, stages = ctx["recovery_score"], ctx["sleep_score"], ctx["cycle_score"], ctx["stages"]
    week = ctx["data"].get("week")
    lines = ["# WHOOP 周健康摘要", ""]
    if week:
        lines += [f"统计周：**{week}**", ""]
    fetched = parse_time(ctx["data"].get("updated_at") or ctx["data"].get("fetched_at"))
    if fetched:
        lines += [f"生成时间：{fetched.astimezone().strftime('%Y-%m-%d %H:%M')}", ""]
    lines += ["## 一眼看懂", ""]
    if recovery:
        calibration = "（个人基线仍在校准）" if rs.get("user_calibrating") else ""
        lines.append(f"- 恢复分：**{fmt(rs.get('recovery_score'))}/100**{calibration}；静息心率 {fmt(rs.get('resting_heart_rate'), 0, ' bpm')}，HRV {fmt(rs.get('hrv_rmssd_milli'), 1, ' ms')}。")
    else:
        lines.append("- 当前时间范围内没有已评分的恢复数据。")
    if main_sleep:
        lines.append(f"- 与本次恢复关联的睡眠：**{duration(ctx['total_sleep'])}**；表现 {fmt(ss.get('sleep_performance_percentage'), 0, '%')}，效率 {fmt(ss.get('sleep_efficiency_percentage'), 0, '%')}，一致性 {fmt(ss.get('sleep_consistency_percentage'), 0, '%')}。")
    if cycle:
        lines.append(f"- 当前周期 Strain：**{fmt(cs.get('strain'), 1)}**；平均心率 {fmt(cs.get('average_heart_rate'), 0, ' bpm')}，估算消耗 {fmt((cs.get('kilojoule') or 0) / 4.184, 0, ' kcal')}。")
    comparison = ctx.get("comparison")
    if comparison:
        current = comparison["current"]
        previous = comparison["previous"]
        previous_week = previous.get("week") if previous else "暂无"
        lines += [
            "", "## 本周与上周对比", "",
            f"当前周覆盖 **{current['coverage_days']} 天**；对比周：**{previous_week}**。",
            "", "| 指标 | 本周 | 上周 | 变化 |", "| --- | ---: | ---: | ---: |",
        ]
        lines += [f"| {label} | {current_value} | {previous_value} | {delta} |" for label, current_value, previous_value, delta in comparison_rows(comparison)]
        lines += ["", "### 跟进建议", ""]
        lines += [f"- {suggestion}" for suggestion in comparison["suggestions"]]
    lines += ["", "## 睡眠结构", "",
        f"- 浅睡：{duration(stages.get('total_light_sleep_time_milli'))}",
        f"- 深睡：{duration(stages.get('total_slow_wave_sleep_time_milli'))}",
        f"- REM：{duration(stages.get('total_rem_sleep_time_milli'))}",
        f"- 清醒：{duration(stages.get('total_awake_time_milli'))}",
        f"- 呼吸频率：{fmt(ss.get('respiratory_rate'), 1, ' 次/分钟')}",
        f"- 睡眠干扰：{fmt(stages.get('disturbance_count'))} 次",
        "", "## 活动", ""]
    if not ctx["workouts"]:
        lines.append("- 当前时间范围内没有活动记录。")
    for workout in ctx["workouts"][:10]:
        score = record_score(workout)
        elapsed = (record_time(workout, "end") - record_time(workout, "start")).total_seconds() * 1000
        lines.append(f"- {local_time(workout.get('start'), workout.get('timezone_offset'))}：{workout.get('sport_name') or '活动'}，{duration(elapsed)}，Strain {fmt(score.get('strain'), 1)}，平均/最高心率 {fmt(score.get('average_heart_rate'))}/{fmt(score.get('max_heart_rate'))} bpm。")
    notes: list[str] = []
    if rs.get("user_calibrating"):
        notes.append("WHOOP 仍在建立个人基线，恢复分和趋势暂时只适合观察，不宜下结论。")
    if ctx["odd_naps"]:
        notes.append("存在超过 6 小时但被标记为 nap 的记录，可能是校准期或睡眠分类异常。")
    if notes:
        lines += ["", "## 数据提示", ""] + [f"- {note}" for note in notes]
    lines += ["", "> 本报告用于整理设备数据，不构成医疗建议。", ""]
    return "\n".join(lines)


def trend_svg(recoveries: list[dict[str, Any]]) -> str:
    points = []
    for item in sorted(recoveries, key=lambda row: row.get("created_at", ""))[-14:]:
        value = record_score(item).get("recovery_score")
        if value is not None:
            points.append(float(value))
    if len(points) < 2:
        return '<p class="muted">目前只有 1 个恢复数据点；拉取更多天数后会自动显示趋势。</p>'
    width, height, left, top, right, bottom = 640, 210, 42, 16, 16, 32
    plot_w, plot_h = width - left - right, height - top - bottom
    coords = [(left + i * plot_w / max(1, len(points)-1), top + (100-v)*plot_h/100, v) for i, v in enumerate(points)]
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in coords)
    circles = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4"><title>{v:.0f}/100</title></circle>' for x, y, v in coords)
    grid = "".join(f'<line x1="{left}" y1="{top+(100-v)*plot_h/100:.1f}" x2="{width-right}" y2="{top+(100-v)*plot_h/100:.1f}"/><text x="{left-8}" y="{top+(100-v)*plot_h/100+4:.1f}" text-anchor="end">{v}</text>' for v in (0, 50, 100))
    return f'<svg class="trend" viewBox="0 0 {width} {height}" role="img" aria-label="最近恢复分趋势"><g class="grid">{grid}</g><polyline points="{polyline}"/><g class="points">{circles}</g><text x="{width/2}" y="{height-5}" text-anchor="middle">按时间排序的最近恢复记录</text></svg>'


def html_report(ctx: dict[str, Any]) -> str:
    rs, ss, cs = ctx["recovery_score"], ctx["sleep_score"], ctx["cycle_score"]
    stage_total = max(1, sum(ctx["stage_values"].values()))
    stage_segments = "".join(f'<span class="stage stage-{i}" style="width:{value/stage_total*100:.2f}%" aria-label="{html.escape(name)} {html.escape(duration(value))}"></span>' for i, (name, value) in enumerate(ctx["stage_values"].items(), 1))
    stage_legend = "".join(f'<li><span class="dot stage-{i}"></span>{html.escape(name)} <strong>{html.escape(duration(value))}</strong></li>' for i, (name, value) in enumerate(ctx["stage_values"].items(), 1))
    workout_rows = "".join("<tr>" + f"<td>{html.escape(local_time(item.get('start'), item.get('timezone_offset')))}</td><td>{html.escape(str(item.get('sport_name') or '活动'))}</td><td>{fmt(record_score(item).get('strain'), 1)}</td><td>{fmt(record_score(item).get('average_heart_rate'))} / {fmt(record_score(item).get('max_heart_rate'))}</td></tr>" for item in ctx["workouts"][:10]) or '<tr><td colspan="4" class="muted">当前时间范围内没有活动记录</td></tr>'
    notes = []
    if rs.get("user_calibrating"):
        notes.append("WHOOP 正在建立个人基线，暂时不要过度解读恢复趋势。")
    if ctx["odd_naps"]:
        notes.append("检测到超过 6 小时却被标记为 nap 的睡眠，可能存在分类异常。")
    note_html = "".join(f"<li>{html.escape(note)}</li>" for note in notes) or "<li>暂未发现明显的数据质量提示。</li>"
    fetched = parse_time(ctx["data"].get("updated_at") or ctx["data"].get("fetched_at"))
    generated = fetched.astimezone().strftime("%Y-%m-%d %H:%M") if fetched else "—"
    energy = (cs.get("kilojoule") or 0) / 4.184
    calibration = "校准中" if rs.get("user_calibrating") else "已建立基线"
    comparison = ctx.get("comparison")
    comparison_html = ""
    if comparison:
        current = comparison["current"]
        previous = comparison["previous"] or {}
        rows = "".join(
            f"<tr><td>{html.escape(label)}</td><td>{html.escape(current_value)}</td><td>{html.escape(previous_value)}</td><td>{html.escape(delta)}</td></tr>"
            for label, current_value, previous_value, delta in comparison_rows(comparison)
        )
        suggestions = "".join(f"<li>{html.escape(item)}</li>" for item in comparison["suggestions"])
        comparison_html = f'''<section><h2>本周与上周对比</h2><p class="muted">{html.escape(str(current.get('week')))} 覆盖 {current.get('coverage_days')} 天 · 对比 {html.escape(str(previous.get('week') or '暂无'))}</p><div class="card"><table><thead><tr><th>指标</th><th>本周</th><th>上周</th><th>变化</th></tr></thead><tbody>{rows}</tbody></table></div><div class="card notice followup"><strong>跟进建议</strong><ul>{suggestions}</ul></div></section>'''
    week_label = html.escape(str(ctx["data"].get("week") or "当前快照"))
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WHOOP 健康摘要</title>
<style>
:root{{color-scheme:light dark;--bg:#f5f5f2;--surface:#fff;--text:#171918;--muted:#666c68;--line:#d9ddd9;--green:#18a568;--yellow:#d39b19;--blue:#3978d4;--purple:#855ac7;--orange:#dc7047}}@media(prefers-color-scheme:dark){{:root{{--bg:#111412;--surface:#1a1e1b;--text:#edf2ee;--muted:#a4ada6;--line:#353c37;--green:#43c98b;--yellow:#e4b84e;--blue:#6ea2ec;--purple:#ac87e0;--orange:#ec946f}}}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}main{{width:min(1040px,calc(100% - 32px));margin:32px auto 56px}}h1{{margin:0;font-size:28px}}h2{{margin:0 0 16px;font-size:18px}}.subtitle,.muted{{color:var(--muted)}}.subtitle{{margin:4px 0 24px}}.metrics{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}}.card{{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px}}.label{{color:var(--muted)}}.value{{margin:4px 0;font-size:30px;font-weight:600;letter-spacing:-.03em}}.unit,.context{{font-size:13px;color:var(--muted)}}section{{margin-top:28px}}.two{{display:grid;grid-template-columns:1.25fr .75fr;gap:20px;align-items:start}}.stage-bar{{display:flex;height:22px;overflow:hidden;border-radius:7px;background:var(--line)}}.stage{{display:block}}.stage-1{{background:var(--blue)}}.stage-2{{background:var(--purple)}}.stage-3{{background:var(--orange)}}.legend{{display:flex;flex-wrap:wrap;gap:10px 20px;padding:0;margin:14px 0 0;list-style:none}}.legend li{{color:var(--muted)}}.legend strong{{color:var(--text)}}.dot{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px}}.score-row{{display:grid;grid-template-columns:94px 1fr 48px;gap:10px;align-items:center;margin:12px 0}}.track{{height:8px;border-radius:5px;background:var(--line);overflow:hidden}}.fill{{display:block;height:100%;background:var(--green)}}table{{width:100%;border-collapse:collapse}}th,td{{padding:11px 8px;text-align:left;border-bottom:1px solid var(--line)}}th{{color:var(--muted);font-weight:500}}.notice{{border-left:4px solid var(--yellow)}}.notice ul{{margin:8px 0 0;padding-left:20px}}.followup{{margin-top:12px}}.trend{{width:100%;min-height:210px}}.trend .grid line{{stroke:var(--line)}}.trend text{{fill:var(--muted);font-size:12px}}.trend polyline{{fill:none;stroke:var(--green);stroke-width:3}}.trend .points circle{{fill:var(--surface);stroke:var(--green);stroke-width:3}}footer{{margin-top:28px;color:var(--muted);font-size:13px}}@media(max-width:760px){{.metrics{{grid-template-columns:repeat(2,1fr)}}.two{{grid-template-columns:1fr}}}}@media(max-width:430px){{main{{width:min(100% - 20px,1040px);margin-top:20px}}.metrics{{grid-template-columns:1fr}}.value{{font-size:26px}}th:nth-child(1),td:nth-child(1){{display:none}}}}
</style></head><body><main><header><h1>WHOOP 健康摘要</h1><p class="subtitle">数据更新时间：{html.escape(generated)}</p></header>
<div class="metrics"><article class="card"><div class="label">恢复分</div><div class="value">{fmt(rs.get('recovery_score'))}<span class="unit"> / 100</span></div><div class="context">{calibration} · HRV {fmt(rs.get('hrv_rmssd_milli'),1)} ms</div></article><article class="card"><div class="label">关联睡眠</div><div class="value">{html.escape(duration(ctx['total_sleep']))}</div><div class="context">效率 {fmt(ss.get('sleep_efficiency_percentage'))}%</div></article><article class="card"><div class="label">睡眠表现</div><div class="value">{fmt(ss.get('sleep_performance_percentage'))}<span class="unit">%</span></div><div class="context">一致性 {fmt(ss.get('sleep_consistency_percentage'))}%</div></article><article class="card"><div class="label">当前 Strain</div><div class="value">{fmt(cs.get('strain'),1)}</div><div class="context">约 {fmt(energy)} kcal · 均心 {fmt(cs.get('average_heart_rate'))}</div></article></div>
<section><h2>统计周</h2><div class="card"><strong>{week_label}</strong></div></section>{comparison_html}<section class="two"><div><h2>睡眠结构</h2><div class="stage-bar" role="img" aria-label="睡眠阶段构成">{stage_segments}</div><ul class="legend">{stage_legend}</ul></div><div><h2>睡眠质量</h2><div class="score-row"><span>表现</span><div class="track"><span class="fill" style="width:{pct(ss.get('sleep_performance_percentage')):.1f}%"></span></div><strong>{fmt(ss.get('sleep_performance_percentage'))}%</strong></div><div class="score-row"><span>效率</span><div class="track"><span class="fill" style="width:{pct(ss.get('sleep_efficiency_percentage')):.1f}%"></span></div><strong>{fmt(ss.get('sleep_efficiency_percentage'))}%</strong></div><div class="score-row"><span>一致性</span><div class="track"><span class="fill" style="width:{pct(ss.get('sleep_consistency_percentage')):.1f}%"></span></div><strong>{fmt(ss.get('sleep_consistency_percentage'))}%</strong></div></div></section>
<section><h2>恢复趋势</h2>{trend_svg(ctx['recoveries'])}</section><section><h2>活动记录</h2><div class="card"><table><thead><tr><th>时间</th><th>类型</th><th>Strain</th><th>平均 / 最高心率</th></tr></thead><tbody>{workout_rows}</tbody></table></div></section><section><h2>数据提示</h2><div class="card notice"><ul>{note_html}</ul></div></section><footer>本报告用于整理设备数据，不构成医疗建议。</footer></main></body></html>'''


def generate_report(input_path: Path = DEFAULT_INPUT) -> tuple[Path, Path]:
    if not input_path.exists():
        raise SystemExit(f"找不到数据文件：{input_path}。请先运行 python3 whoop.py fetch --days 14")
    raw_snapshot = json.loads(input_path.read_text(encoding="utf-8"))
    weekly = [(path, snapshot) for path, snapshot in load_weekly_snapshots(WEEK_DATA_DIR) if has_health_data(snapshot)]
    if weekly:
        WEEK_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        for index, (_, weekly_snapshot) in enumerate(weekly):
            previous_snapshot = weekly[index - 1][1] if index else None
            weekly_ctx = build_context(weekly_snapshot)
            weekly_ctx["comparison"] = compare_weeks(weekly_snapshot, previous_snapshot)
            (WEEK_REPORT_DIR / f"{weekly_snapshot['week']}.md").write_text(markdown_report(weekly_ctx), encoding="utf-8")
            (WEEK_REPORT_DIR / f"{weekly_snapshot['week']}.html").write_text(html_report(weekly_ctx), encoding="utf-8")
        current = weekly[-1][1]
        previous = weekly[-2][1] if len(weekly) > 1 else None
        ctx = build_context(current)
        ctx["comparison"] = compare_weeks(current, previous)
    else:
        current = raw_snapshot
        ctx = build_context(current)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    markdown_path, html_path = REPORT_DIR / "latest.md", REPORT_DIR / "latest.html"
    markdown = markdown_report(ctx)
    rendered_html = html_report(ctx)
    markdown_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(rendered_html, encoding="utf-8")
    return markdown_path, html_path


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 WHOOP 中文摘要和可视化报告")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="WHOOP JSON 快照路径")
    args = parser.parse_args()
    markdown_path, html_path = generate_report(args.input)
    print(f"文本摘要：{markdown_path}")
    print(f"可视化报告：{html_path}")


if __name__ == "__main__":
    main()
