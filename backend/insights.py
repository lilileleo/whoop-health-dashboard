"""Longitudinal comparisons, explicit training plans and contextual events."""
from datetime import date, datetime, timedelta
from . import store
from .analysis import TZ, prepare, parsed, avg, day_of, score
from .activity import sport_info


def monday(day):
    return day-timedelta(days=day.weekday())


def load_events():
    with store.connection() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM events ORDER BY day,time,id")]


def long_term(end=None, weeks=8):
    data=store.records()
    daily,_,_,_=prepare(data)
    last=date.fromisoformat(end or (daily[-1]["date"] if daily else datetime.now(TZ).date().isoformat()))
    first=monday(last)-timedelta(weeks=weeks-1)
    with store.connection() as conn:
        weights=[dict(r) for r in conn.execute("SELECT * FROM weights WHERE day BETWEEN ? AND ? ORDER BY day",(first.isoformat(),last.isoformat()))]
        completions={r[0]:r[1] for r in conn.execute("SELECT week,COUNT(*) FROM training_checks WHERE state='complete' GROUP BY week")}
    events=[e for e in load_events() if first.isoformat()<=e["day"]<=last.isoformat()]
    notes=store.annotations()
    rows=[]
    for n in range(weeks):
        start=first+timedelta(weeks=n)
        stop=min(start+timedelta(days=6),last)
        ds=[r for r in daily if start.isoformat()<=r["date"]<=stop.isoformat()]
        ws=[r for r in weights if start.isoformat()<=r["day"]<=stop.isoformat()]
        zones=[0.0]*6
        zone_samples=0
        for workout in data["workout"]:
            day=day_of(workout.get("start"))
            z=score(workout).get("zone_durations")
            if day and start.isoformat()<=day<=stop.isoformat() and z:
                zone_samples+=1
                for i,name in enumerate(("zero","one","two","three","four","five")):
                    zones[i]+=(z.get(f"zone_{name}_milli") or 0)/60000
        low,high=zones[1]+zones[2],zones[4]+zones[5]
        denominator=low+high
        rows.append({"week":start.isoformat(),"end":stop.isoformat(),"partial":stop<start+timedelta(days=6),
          "hrv":avg([r["hrv"] for r in ds]),"rhr":avg([r["rhr"] for r in ds]),
          "strain":avg([r["strain"] for r in ds]),"weight":avg([r["kg"] for r in ws]),
          "samples":{k:sum(r[k] is not None for r in ds) for k in ("hrv","rhr","strain")}|{"weight":len(ws)},
          "zones":[round(v,2) for v in zones],"low_minutes":round(low,2),"high_minutes":round(high,2),
          "low_percent":round(low/denominator*100,1) if denominator else None,
          "high_percent":round(high/denominator*100,1) if denominator else None,
          "zone_samples":zone_samples,"coverage":len(ds),
          "training_complete":completions.get(start.isoformat(),0),
          "events":[e for e in events if start.isoformat()<=e["day"]<=stop.isoformat()],
          "notes":[{"day":d,"text":text} for d,text in notes.items() if start.isoformat()<=d<=stop.isoformat()]})
    for key in ("hrv","rhr","strain","weight"):
        base=next((r[key] for r in rows if r[key] is not None and r[key]!=0),None)
        for r in rows:r[key+"_index"]=round(r[key]/base*100,2) if r[key] is not None and base else None
    for row in rows:
        plans=training_week(row["week"])["plans"]
        row["plan_statuses"]=[{"id":p["id"],"name":p["name"],"configured":p["weekday"] is not None,
          "state":p["state"],"candidates":len(p["candidates"])} for p in plans]
    return {"start":first.isoformat(),"end":last.isoformat(),"weeks":rows,"weights":weights,"events":events,
      "notes":[{"day":d,"text":t} for d,t in notes.items() if first.isoformat()<=d<=last.isoformat()]}


def training_week(day=None):
    start=monday(date.fromisoformat(day or datetime.now(TZ).date().isoformat()))
    end=start+timedelta(days=6)
    data=store.records()
    with store.connection() as conn:
        templates=[dict(r) for r in conn.execute("SELECT * FROM training_templates ORDER BY id")]
        checks={r["template_id"]:dict(r) for r in conn.execute("SELECT * FROM training_checks WHERE week=?",(start.isoformat(),))}
    actual=[]
    for w in data["workout"]:
        d=day_of(w.get("start"))
        if not d or not start.isoformat()<=d<=end.isoformat():continue
        s=score(w)
        z=s.get("zone_durations") or {}
        actual.append({"id":str(w.get("id","")),"date":d,"start":w.get("start"),"sport":w.get("sport_name") or "activity",
          "label":sport_info(w.get("sport_name") or "activity")["label"],"strain":s.get("strain"),
          "high_minutes":((z.get("zone_four_milli") or 0)+(z.get("zone_five_milli") or 0))/60000})
    rows=[]
    for t in templates:
        c=checks.get(t["id"],{})
        scheduled=c.get("scheduled_day") or ((start+timedelta(days=t["weekday"])).isoformat() if t["weekday"] is not None else None)
        candidates=[]
        if scheduled:
            for w in actual:
                match=t["kind"]=="any" or (t["kind"]=="strength" and w["sport"] in ("functional-fitness","weightlifting","strength-trainer")) or (t["kind"]=="interval" and w["sport"] in ("spin","cycling","running","rowing","stairmaster","elliptical") and w["high_minutes"]>=10) or (t["kind"]=="easy" and w["sport"] in ("walking","cycling","running","spin","hiking-rucking"))
                if w["date"]==scheduled and match:candidates.append(w["id"])
        rows.append(t|{"scheduled_day":scheduled,"state":c.get("state","pending"),"workout_id":c.get("workout_id"),"note":c.get("note",""),"candidates":candidates})
    return {"start":start.isoformat(),"end":end.isoformat(),"plans":rows,"workouts":actual,
      "complete":sum(r["state"]=="complete" for r in rows),"configured":sum(r["weekday"] is not None for r in rows)}
