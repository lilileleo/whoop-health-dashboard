"""Activity calendar and per-day timeline, using WHOOP's actual activity labels."""
from datetime import date, datetime, time, timedelta

from .analysis import TZ, day_of, parsed, score

SPORTS = {
    "walking": ("步行", "🚶", "#55a2ad"),
    "functional-fitness": ("功能性训练", "🏋️", "#8d6ac4"),
    "activity": ("未分类活动", "⚡", "#8b91d4"),
    "stairmaster": ("登阶机", "🪜", "#c68c55"),
    "hiking-rucking": ("徒步 / 负重行走", "🥾", "#a58a5c"),
    "cycling": ("骑行", "🚴", "#6aab85"),
    "spin": ("动感单车", "🚲", "#b3a343"),
    "stretching": ("拉伸", "🧘", "#aa85b6"),
    "running": ("跑步", "🏃", "#638cc0"),
    "swimming": ("游泳", "🏊", "#3999b0"),
    "dance": ("舞蹈", "💃", "#9571c4"),
    "weightlifting": ("举重", "🏋️", "#d28d49"),
    "tennis": ("网球", "🎾", "#a5b63e"),
    "rock-climbing": ("攀岩", "🧗", "#b8845e"),
}


def sport_info(name):
    label, emoji, color = SPORTS.get(name, (name.replace("-", " "), "●", "#819c93"))
    return {"id": name, "label": label, "emoji": emoji, "color": color}


def activity_calendar(data, days=182, end=None, notes=None):
    records = data.get("workout", [])
    all_dates = [day_of(r.get("end") or r.get("start") or r.get("created_at"))
                 for rows in data.values() for r in rows]
    all_dates = [d for d in all_dates if d]
    last = date.fromisoformat(end) if end else date.fromisoformat(max(all_dates)) if all_dates else datetime.now(TZ).date()
    first = last - timedelta(days=days-1)
    calendar = {}
    for n in range(days):
        day = (first+timedelta(days=n)).isoformat()
        calendar[day] = {"date": day, "sessions": [], "minutes": 0, "recorded": day in all_dates,
                         "note": (notes or {}).get(day, "")}
    counts = {}
    for i, row in enumerate(records):
        start, end_at = parsed(row.get("start")), parsed(row.get("end"))
        if not start or not end_at or end_at <= start:
            continue
        start, end_at = start.astimezone(TZ), end_at.astimezone(TZ)
        name = row.get("sport_name") or "activity"
        cursor = max(start.date(), first)
        limit = min(end_at.date(), last)
        included = False
        while cursor <= limit:
            lower = datetime.combine(cursor, time.min, TZ)
            upper = lower+timedelta(days=1)
            a, b = max(start, lower), min(end_at, upper)
            if b > a:
                s = score(row)
                session = {"id": str(row.get("id") or i), "sport": name,
                  "start_minute": (a-lower).total_seconds()/60,
                  "end_minute": (b-lower).total_seconds()/60,
                  "minutes": round((b-a).total_seconds()/60, 2),
                  "start": a.isoformat(), "end": b.isoformat(),
                  "continues_before": start < lower, "continues_after": end_at > upper,
                  "strain": s.get("strain"), "average_hr": s.get("average_heart_rate")}
                calendar[cursor.isoformat()]["sessions"].append(session)
                calendar[cursor.isoformat()]["recorded"] = True
                included = True
            cursor += timedelta(days=1)
        if included:
            counts[name] = counts.get(name, 0)+1
    for day in calendar.values():
        day["sessions"].sort(key=lambda s: s["start_minute"])
        # Union intervals: overlapping activities must not inflate daily time.
        intervals = []
        for s in day["sessions"]:
            if intervals and s["start_minute"] <= intervals[-1][1]:
                intervals[-1][1] = max(intervals[-1][1], s["end_minute"])
            else:
                intervals.append([s["start_minute"], s["end_minute"]])
        day["minutes"] = round(sum(b-a for a,b in intervals), 2)
        day["percentage"] = round(day["minutes"]/1440*100, 1)
        totals = {}
        for s in day["sessions"]:
            totals[s["sport"]] = totals.get(s["sport"], 0)+s["minutes"]
        day["dominant_sport"] = max(totals, key=totals.get) if totals else None
    result = list(calendar.values())
    return {"start": first.isoformat(), "end": last.isoformat(), "days": result,
      "sports": [sport_info(k)|{"count":v} for k,v in sorted(counts.items(), key=lambda x:-x[1])],
      "summary": {"activities": sum(counts.values()), "active_days": sum(bool(d["sessions"]) for d in result),
                  "minutes": round(sum(d["minutes"] for d in result)), "recorded_days": sum(d["recorded"] for d in result)}}
