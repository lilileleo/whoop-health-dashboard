"""Auditable descriptive metrics; no diagnosis or causal claims."""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from statistics import mean
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")


def parsed(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def day_of(value):
    dt = parsed(value)
    return dt.astimezone(TZ).date().isoformat() if dt else None


def score(row):
    return row.get("score") or {}


def sleep_hours(row):
    stages = score(row).get("stage_summary") or {}
    return sum(stages.get(k) or 0 for k in ("total_light_sleep_time_milli", "total_slow_wave_sleep_time_milli", "total_rem_sleep_time_milli")) / 3_600_000


def avg(values):
    v = [x for x in values if x is not None and isinstance(x, (float, int)) and math.isfinite(x)]
    return round(mean(v), 3) if v else None


def correlation(pairs):
    pairs = [(x,y) for x,y in pairs if x is not None and y is not None]
    if len(pairs) < 10:
        return {"n":len(pairs), "r":None}
    xs, ys = zip(*pairs)
    mx, my = mean(xs), mean(ys)
    den = math.sqrt(sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))
    return {"n":len(pairs), "r":round(sum((x-mx)*(y-my) for x,y in pairs)/den, 3) if den else None}


def prepare(data):
    days, flags = {}, []
    sleep_map = {str(s["id"]):s for s in data["sleep"] if s.get("id")}
    cycle_dates = {}
    def get(day):
        return days.setdefault(day, {"date":day, "recovery":None, "hrv":None, "rhr":None,
          "spo2":None, "sleep":None, "naps":None, "total_sleep":None,
          "performance":None,"efficiency":None,"consistency":None,"respiratory":None,
          "strain":None,"workouts":0,"calibrating":False})
    for row in data["recovery"]:
        if row.get("score_state") != "SCORED":
            continue
        linked = sleep_map.get(str(row.get("sleep_id")))
        day = day_of(linked.get("end")) if linked else day_of(row.get("created_at"))
        if not day: continue
        cycle_dates[str(row.get("cycle_id"))] = day
        s, d = score(row), get(day)
        d.update(recovery=s.get("recovery_score"),hrv=s.get("hrv_rmssd_milli"),
          rhr=s.get("resting_heart_rate"),spo2=s.get("spo2_percentage"),
          calibrating=bool(s.get("user_calibrating")))
        if not linked:
            flags.append({"date":day,"type":"关联缺失","text":"恢复记录对应的睡眠未收录，日期按恢复创建时间显示。"})
    sleeps=[]
    for row in data["sleep"]:
        if row.get("score_state") != "SCORED": continue
        day = day_of(row.get("end") or row.get("start"))
        if not day: continue
        d,s,h = get(day), score(row), sleep_hours(row)
        stages = s.get("stage_summary") or {}
        nap = bool(row.get("nap"))
        if nap: d["naps"] = (d["naps"] or 0) + h
        else:
            if d["naps"] is None: d["naps"] = 0
            d["sleep"] = (d["sleep"] or 0) + h
            # Score fields belong to latest main sleep ending on that date.
            d.update(performance=s.get("sleep_performance_percentage"),efficiency=s.get("sleep_efficiency_percentage"),
              consistency=s.get("sleep_consistency_percentage"),respiratory=s.get("respiratory_rate"))
        d["total_sleep"] = (d["total_sleep"] or 0) + h
        sleeps.append({"id":str(row.get("id","")),"date":day,"start":row.get("start"),"end":row.get("end"),
          "nap":nap,"hours":round(h,3),"performance":s.get("sleep_performance_percentage"),
          "efficiency":s.get("sleep_efficiency_percentage"),"consistency":s.get("sleep_consistency_percentage"),
          "respiratory":s.get("respiratory_rate"),"stages":{k:round((stages.get(v) or 0)/3_600_000,3) for k,v in
            {"light":"total_light_sleep_time_milli","deep":"total_slow_wave_sleep_time_milli","rem":"total_rem_sleep_time_milli","awake":"total_awake_time_milli"}.items()}})
        if nap and h >= 4:
            flags.append({"date":day,"type":"睡眠分类待核对","text":f"{h:.1f} 小时睡眠被标记为 Nap；可能为长补觉或识别偏差，请结合实际作息核对。"})
        in_bed = stages.get("total_in_bed_time_milli")
        if in_bed and s.get("sleep_efficiency_percentage") is not None and abs(h*3_600_000/in_bed*100-s["sleep_efficiency_percentage"])>3:
            flags.append({"date":day,"type":"指标口径差异","text":"API 睡眠效率与阶段时长推算值相差超过 3 个百分点，保留原始读数。"})
    for row in data["cycle"]:
        if row.get("score_state") != "SCORED":continue
        day = cycle_dates.get(str(row.get("id"))) or day_of(row.get("start"))
        if not day:continue
        strain = score(row).get("strain")
        d=get(day)
        d["strain"] = max(d["strain"],strain) if d["strain"] is not None and strain is not None else strain
        start,end=parsed(row.get("start")),parsed(row.get("end"))
        if start and end and (end-start).total_seconds()>36*3600:
            flags.append({"date":day,"type":"周期偏长","text":"WHOOP 生理周期超过 36 小时，不能按自然日负荷或消耗解读。"})
    workouts=[]
    for row in data["workout"]:
        day=day_of(row.get("start"))
        if not day:continue
        get(day)["workouts"]+=1
        s=score(row)
        start,end=parsed(row.get("start")),parsed(row.get("end"))
        workouts.append({"id":str(row.get("id","")),"date":day,"start":row.get("start"),
          "name":row.get("sport_name") or "活动", "scored":row.get("score_state")=="SCORED",
          "minutes":round((end-start).total_seconds()/60,1) if start and end else None,
          "strain":s.get("strain"),"average_hr":s.get("average_heart_rate"),"max_hr":s.get("max_heart_rate"),
          "kcal":round(s["kilojoule"]/4.184) if s.get("kilojoule") is not None else None,
          "zones":[round((s.get("zone_durations") or {}).get(f"zone_{z}_milli",0)/60000,2) for z in ("zero","one","two","three","four","five")]})
    return sorted(days.values(),key=lambda x:x["date"]), sleeps, workouts,flags


METRICS=("recovery","hrv","rhr","sleep","total_sleep","performance","consistency","efficiency","strain","spo2","respiratory")


def summarize(rows):
    return {k:{"value":avg([r[k] for r in rows]),"n":sum(r[k] is not None for r in rows)} for k in METRICS}


def dashboard(data, start=None, end=None, days=30, notes=None):
    all_days,sleeps,workouts,flags=prepare(data)
    end = date.fromisoformat(end) if end else date.fromisoformat(all_days[-1]["date"]) if all_days else datetime.now(TZ).date()
    start = date.fromisoformat(start) if start else end-timedelta(days=days-1)
    if start>end or (end-start).days>730: raise ValueError("日期范围需为 1–731 天，开始日期不能晚于结束日期")
    length=(end-start).days+1
    selected=[r for r in all_days if start.isoformat()<=r["date"]<=end.isoformat()]
    prev=[r for r in all_days if (start-timedelta(days=length)).isoformat()<=r["date"]<start.isoformat()]
    summary,previous=summarize(selected),summarize(prev)
    for k in METRICS:
        a,b=summary[k]["value"],previous[k]["value"]
        summary[k].update(previous=b,previous_n=previous[k]["n"],delta=round(a-b,3) if a is not None and b is not None else None)
    calendar=[]
    by_day={r["date"]:r for r in selected}
    for n in range(length):
        day=(start+timedelta(days=n)).isoformat()
        row=dict(by_day.get(day) or {"date":day,**{k:None for k in METRICS},"naps":None,"workouts":0,"calibrating":False})
        history=[r for r in all_days if (date.fromisoformat(day)-timedelta(days=28)).isoformat()<=r["date"]<day and not r["calibrating"]]
        for key in ("hrv","rhr","sleep","respiratory"):
            vals=[r[key] for r in history if r[key] is not None]
            row[key+"_baseline"]=avg(vals) if len(vals)>=7 else None
        row["note"]=(notes or {}).get(day,"")
        calendar.append(row)
    subset=lambda rows:[r for r in rows if start.isoformat()<=r["date"]<=end.isoformat()]
    issues=subset(flags)
    insight=[]
    if summary["sleep"]["value"] is not None:
        insight.append({"title":"睡眠与补觉分开看","text":f"主睡眠平均 {summary['sleep']['value']:.1f} 小时；按结束日期统计的全天睡眠平均 {(summary['total_sleep']['value'] or 0):.1f} 小时。主睡眠样本 {summary['sleep']['n']} 天。","tone":"mint"})
    h=summary["hrv"]
    if h["delta"] is not None:
        insight.append({"title":"关注个人恢复趋势","text":f"HRV 比上一等长时段{'上升' if h['delta']>=0 else '下降'} {abs(h['delta']):.1f} ms（{h['n']} / {h['previous_n']} 个样本）。变化是描述性比较，结合睡眠、负荷和主观感受观察。","tone":"purple"})
    if issues:
        insight.append({"title":"有记录值得核对","text":f"本时段有 {len(issues)} 条数据提示。长补觉会降低一致性，也可能被误识别；请按实际情况核对，而非自动改为主睡眠。","tone":"amber"})
    if len(selected)<length:
        insight.append({"title":"缺失日期没有当成零","text":f"{length} 天中 {len(selected)} 天有记录。各指标使用自己的有效样本数；不完整时段的均值不宜直接代表整体。","tone":"amber"})
    for row in calendar:
        row["naps"]=round(row["naps"],3) if row["naps"] is not None else None
    return {"range":{"start":start.isoformat(),"end":end.isoformat(),"days":length,"previous_start":(start-timedelta(days=length)).isoformat(),"previous_end":(start-timedelta(days=1)).isoformat()},
      "available":{"start":all_days[0]["date"] if all_days else None,"end":all_days[-1]["date"] if all_days else None},
      "summary":summary,"daily":calendar,"coverage":len(selected),"sleeps":list(reversed(subset(sleeps))),
      "workouts":list(reversed(subset(workouts))),"flags":list(reversed(issues)),"insights":insight,
      "latest":selected[-1] if selected else None,
      "correlation":correlation([(r["sleep"],r["recovery"]) for r in selected if not r["calibrating"]]),
      "definitions":["时区：Asia/Shanghai；睡眠按结束日期归日，主睡眠和 Nap 分开统计。",
        "恢复优先关联 sleep_id，周期通过 cycle_id 对齐恢复日期；无关联时使用原始创建/开始时间。",
        "每日 Strain 展示该日关联生理周期的最大读数，不累加活动 Strain；周期不等于自然日。",
        "基线取该日期之前 28 天的非校准样本，至少需要 7 个有效样本；图表留白表示缺失。",
        "环比使用前一等长时段；每项均值排除空值并显示样本数。",
        "相关性至少需要 10 对有效样本，不能证明因果；睡眠本身也是恢复评分的输入之一。"]}


def report_text(result):
    p=result["range"]
    lines=["# WHOOP 健康分析", "",f"统计范围：{p['start']} 至 {p['end']}（Asia/Shanghai）", "",
      f"有记录 {result['coverage']} / {p['days']} 天。", "", "| 指标 | 均值 | 样本数 | 前期均值 | 变化 |", "|---|---:|---:|---:|---:|"]
    for k,label,unit in [("recovery","恢复","分"),("hrv","HRV","ms"),("rhr","静息心率","bpm"),("sleep","主睡眠","小时"),("consistency","睡眠一致性","%"),("strain","周期 Strain","")]:
        s=result["summary"][k]
        fmt=lambda v:"—" if v is None else f"{v:.1f}"
        lines.append(f"| {label} ({unit}) | {fmt(s['value'])} | {s['n']} | {fmt(s['previous'])} | {fmt(s['delta'])} |")
    lines += ["", "## 观察", ""]+[f"- {i['title']}：{i['text']}" for i in result["insights"]]
    lines += ["", "## 数据提示", ""]+[f"- {f['date']} {f['type']}：{f['text']}" for f in result["flags"]]
    lines += ["", "## 个人备注", ""]+[f"- {r['date']}：{r['note']}" for r in result["daily"] if r.get("note")]
    lines += ["", "## 时间线事件", ""]+[f"- {r['day']} {r['time']} [{r['category']}] {r['text']}" for r in result.get("events",[])]
    lines += ["", "## 统计口径", ""]+[f"- {s}" for s in result["definitions"]]
    lines += ["", "设备数据用于个人趋势观察，不用于诊断。"]
    return "\n".join(lines)
