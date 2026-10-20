from __future__ import annotations

import csv
import asyncio
import io
import json
import os
import secrets
import threading
import time
import urllib.parse
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

import whoop
from . import store
from .analysis import dashboard, report_text
from .activity import activity_calendar
from .security import Settings, authorized, tailscale_peer_allowed
from .insights import long_term, load_events, training_week, monday

whoop.load_dotenv()
CONFIG = Settings.load()

LOCAL_TOKEN = secrets.token_urlsafe(32)
SYNC_LOCK = threading.Lock()
OAUTH_STATES: dict[str, float] = {}
DIST = store.ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app):
    store.init_db()
    store.import_snapshots()
    async def periodic_sync():
        while True:
            await asyncio.sleep(CONFIG.sync_minutes*60)
            if whoop.TOKEN_FILE.exists() and not SYNC_LOCK.locked():
                try:
                    sync(SyncInput(days=14))
                except HTTPException:
                    pass
    task = asyncio.create_task(periodic_sync()) if CONFIG.sync_minutes else None
    try:
        yield
    finally:
        if task:
            task.cancel()
            try: await task
            except asyncio.CancelledError: pass


app = FastAPI(title="WHOOP 本地健康空间", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"] + ([CONFIG.hostname] if CONFIG.server else []))


@app.middleware("http")
async def local_boundary(request: Request, call_next):
    if CONFIG.auth_mode == "tailscale" and request.url.path != "/healthz":
        if not request.client or not tailscale_peer_allowed(request.client.host):
            return Response("免登录仅允许 Tailscale 网络或服务器本机连接；不接受代理身份头", status_code=403,
                headers={"Cache-Control":"no-store"})
    if request.url.path != "/healthz" and not authorized(request.headers.get("authorization", ""), CONFIG):
        return Response("请使用看板用户名和密码登录", status_code=401,
            headers={"WWW-Authenticate":'Basic realm="WHOOP Health", charset="UTF-8"',"Cache-Control":"no-store"})
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if not secrets.compare_digest(request.headers.get("x-local-token", ""), LOCAL_TOKEN):
            return Response("本地会话校验失败，请刷新页面", status_code=403)
        origin = request.headers.get("origin")
        if origin:
            parsed = urllib.parse.urlparse(origin)
            allowed = origin.rstrip("/") == CONFIG.origin if CONFIG.server else parsed.hostname in ("localhost", "127.0.0.1", "::1")
            if not allowed:
                return Response("请求来源与看板地址不符",status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store" if not request.url.path.startswith("/assets/") else "public,max-age=86400"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    return response


def status():
    meta=store.metadata()
    history=store.sync_history()
    # Inspect presence only. Tokens and configuration values never leave server.
    whoop.load_dotenv()
    return {"local_token":LOCAL_TOKEN, "last_fetch":meta.get("last_fetch"),"counts":store.counts(),
      "configured":bool(os.getenv("WHOOP_CLIENT_ID") and os.getenv("WHOOP_CLIENT_SECRET")),
      "authorized":whoop.TOKEN_FILE.exists(),"running":SYNC_LOCK.locked(),"history":history,
      "import_errors":json.loads(meta.get("import_errors","[]")),"timezone":"Asia/Shanghai",
      "server_mode":CONFIG.server,"auth_mode":CONFIG.auth_mode if CONFIG.server else "local",
      "insecure_http":CONFIG.insecure_http,"sync_interval_minutes":CONFIG.sync_minutes}


@app.get("/healthz")
def health(): return {"status":"ok"}


@app.get("/api/status")
def get_status(): return status()


def get_dashboard(start: str | None, end: str | None, days: int):
    try:
        result=dashboard(store.records(),start,end,days,store.annotations())
        result["events"]=[e for e in load_events() if result["range"]["start"]<=e["day"]<=result["range"]["end"]]
        return result
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from exc


@app.get("/api/dashboard")
def get_data(start: str | None=None,end: str | None=None,days:int=Query(30,ge=1,le=731)):
    return get_dashboard(start,end,days)


@app.get("/api/activity-calendar")
def get_activity_calendar(days: int = Query(182,ge=7,le=366), end: str | None = None):
    try:
        result=activity_calendar(store.records(), days, end, store.annotations())
        events=load_events()
        for day in result["days"]:day["events"]=[e for e in events if e["day"]==day["date"]]
        return result
    except ValueError as exc:
        raise HTTPException(400,"日期格式应为 YYYY-MM-DD") from exc


@app.get("/api/long-term")
def get_long_term(end: str | None=None, weeks: int=Query(8,ge=4,le=52)):
    try:return long_term(end,weeks)
    except ValueError:raise HTTPException(400,"日期格式应为 YYYY-MM-DD")


class WeightInput(BaseModel):
    kg: float = Field(gt=0,le=500,allow_inf_nan=False)


@app.put("/api/weights/{day}")
def put_weight(day:str,body:WeightInput):
    try:date.fromisoformat(day)
    except ValueError:raise HTTPException(400,"日期格式应为 YYYY-MM-DD")
    with store.connection() as conn:
        conn.execute("INSERT OR REPLACE INTO weights VALUES (?,?,?)",(day,body.kg,store.now()))
    return {"saved":True}


@app.delete("/api/weights/{day}")
def delete_weight(day:str):
    try:date.fromisoformat(day)
    except ValueError:raise HTTPException(400,"日期格式应为 YYYY-MM-DD")
    with store.connection() as conn:conn.execute("DELETE FROM weights WHERE day=?",(day,))
    return {"deleted":True}


class EventInput(BaseModel):
    day: date
    time: str = Field(default="",pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$|^$")
    category: Literal['饮食','训练调整','作息','身体状态','其他'] = '其他'
    text: str = Field(min_length=1,max_length=1000)


@app.post("/api/events",status_code=201)
def add_event(body:EventInput):
    if not body.text.strip():raise HTTPException(400,"请输入事件内容")
    with store.connection() as conn:
        id=conn.execute("INSERT INTO events(day,time,category,text,created_at) VALUES (?,?,?,?,?)",(body.day.isoformat(),body.time,body.category,body.text.strip(),store.now())).lastrowid
    return {"id":id}


@app.delete("/api/events/{id}")
def delete_event(id:int):
    with store.connection() as conn:conn.execute("DELETE FROM events WHERE id=?",(id,))
    return {"deleted":True}


@app.get("/api/training-week")
def get_training_week(day:str|None=None):
    try:return training_week(day)
    except ValueError:raise HTTPException(400,"日期格式应为 YYYY-MM-DD")


class TemplateInput(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    weekday: int|None = Field(default=None,ge=0,le=6)
    kind: Literal['strength','interval','easy','any']


@app.put("/api/training-templates/{id}")
def put_training_template(id:int,body:TemplateInput):
    if id not in (1,2,3,4):raise HTTPException(400,"计划编号为 1–4")
    if not body.name.strip():raise HTTPException(400,"计划名称不能为空")
    with store.connection() as conn:
        conn.execute("UPDATE training_templates SET name=?,weekday=?,kind=? WHERE id=?",(body.name.strip(),body.weekday,body.kind,id))
    return {"saved":True}


class TrainingCheckInput(BaseModel):
    week: date
    state: Literal['pending','complete','skipped']
    workout_id: str|None = None
    scheduled_day: date|None = None
    note: str = Field(default="",max_length=1000)


@app.put("/api/training-checks/{id}")
def put_training_check(id:int,body:TrainingCheckInput):
    if id not in (1,2,3,4):raise HTTPException(400,"计划编号为 1–4")
    week=monday(body.week).isoformat()
    if body.workout_id and not any(str(w.get("id"))==body.workout_id for w in store.records()["workout"]):
        raise HTTPException(400,"关联的活动记录不存在")
    with store.connection() as conn:
        if body.state=='complete' and body.workout_id and conn.execute("SELECT 1 FROM training_checks WHERE workout_id=? AND state='complete' AND NOT (week=? AND template_id=?)",(body.workout_id,week,id)).fetchone():
            raise HTTPException(409,"这条活动已用于另一练，请选择其他记录或手动确认")
        conn.execute("INSERT OR REPLACE INTO training_checks VALUES (?,?,?,?,?,?)",(week,id,body.workout_id,body.state,body.scheduled_day.isoformat() if body.scheduled_day else None,body.note))
    return {"saved":True}


class SyncInput(BaseModel):
    days: int = Field(default=14,ge=1,le=365)


def do_sync(run_id,days):
    try:
        whoop.fetch_command(days)
        counts=store.import_snapshots()
        with store.connection() as conn:
            conn.execute("UPDATE sync_runs SET finished_at=?,state='success',message=?,counts=? WHERE id=?",
              (store.now(),f"已同步最近 {days} 天数据",json.dumps(counts),run_id))
    except BaseException as exc:
        # WHOOP HTTP error bodies may contain sensitive details: expose categories only.
        if isinstance(exc,SystemExit):
            message="授权配置不可用，请检查 .env 或重新连接 WHOOP。"
        else:
            message="WHOOP 同步失败，请检查网络；若授权已失效，请重新连接。历史数据仍可查看。"
        with store.connection() as conn:
            conn.execute("UPDATE sync_runs SET finished_at=?,state='failed',message=? WHERE id=?",(store.now(),message,run_id))
    finally:
        SYNC_LOCK.release()


@app.post("/api/sync",status_code=202)
def sync(body:SyncInput):
    if not SYNC_LOCK.acquire(blocking=False): raise HTTPException(409,"已有同步任务正在运行")
    try:
        with store.connection() as conn:
            run_id=conn.execute("INSERT INTO sync_runs(started_at,state,message) VALUES (?,'running',?)",(store.now(),f"正在同步最近 {body.days} 天…")).lastrowid
        threading.Thread(target=do_sync,args=(run_id,body.days),daemon=True).start()
        return {"id":run_id,"state":"running"}
    except Exception:
        SYNC_LOCK.release()
        raise


@app.post("/api/import")
def import_data():
    if SYNC_LOCK.locked():raise HTTPException(409,"请等待同步完成")
    return {"counts":store.import_snapshots()}


class NoteInput(BaseModel):
    text: str = Field(max_length=2000)


@app.put("/api/notes/{day}")
def save_note(day:str,body:NoteInput):
    try: date.fromisoformat(day)
    except ValueError: raise HTTPException(400,"日期格式应为 YYYY-MM-DD")
    store.save_annotation(day,body.text)
    return {"saved":True}


@app.post("/api/auth/start")
def auth_start():
    if CONFIG.insecure_http:
        raise HTTPException(409,"HTTP 临时模式不支持网页授权。已有有效令牌可同步；重新授权请改用 HTTPS。")
    if SYNC_LOCK.locked():raise HTTPException(409,"请等待同步完成再重新授权")
    try:client_id,_,redirect=whoop.config()
    except SystemExit:raise HTTPException(400,"请在 .env 中配置 WHOOP_CLIENT_ID 与 WHOOP_CLIENT_SECRET")
    p=urllib.parse.urlparse(redirect)
    if CONFIG.server:
        if redirect != CONFIG.origin + "/callback":
            raise HTTPException(400,"服务器模式需将 WHOOP_REDIRECT_URI 设置为看板 HTTPS 地址加 /callback，并在 WHOOP 开发者后台登记")
    elif p.hostname not in ("localhost","127.0.0.1") or p.path != "/callback" or (p.port or 80) != int(os.environ.get("WHOOP_PORT","8000")):
        raise HTTPException(400,"WHOOP_REDIRECT_URI 需匹配本地服务，如 http://localhost:8000/callback，并在 WHOOP 开发者后台登记")
    for key,expiry in list(OAUTH_STATES.items()):
        if expiry<time.time():OAUTH_STATES.pop(key,None)
    state=secrets.token_urlsafe(32)
    OAUTH_STATES[state]=time.time()+600
    url=whoop.AUTH_URL+"?"+urllib.parse.urlencode({"client_id":client_id,"redirect_uri":redirect,
      "response_type":"code","scope":" ".join(whoop.SCOPES),"state":state})
    response=JSONResponse({"url":url})
    response.set_cookie("whoop_oauth_state",state,httponly=True,secure=CONFIG.server,samesite="lax",max_age=600)
    return response


@app.get("/callback")
def auth_callback(request:Request,code:str="",state:str="",error:str=""):
    if CONFIG.insecure_http:
        raise HTTPException(409,"HTTP 临时模式已禁用授权回调，请改用 HTTPS 后重新连接 WHOOP。")
    expiry=OAUTH_STATES.pop(state,0)
    if error or not code or expiry<time.time() or not secrets.compare_digest(request.cookies.get("whoop_oauth_state",""),state):
        return HTMLResponse("<h1>授权未完成</h1><p>授权已取消或校验已过期，请返回健康空间重新连接。</p><a href='/'>返回</a>",status_code=400)
    if not SYNC_LOCK.acquire(blocking=False):raise HTTPException(409,"正在同步，请稍后重新授权")
    try:
        client_id,secret,redirect=whoop.config()
        with whoop.process_lock():
            tokens=whoop.exchange_code(code,client_id,secret,redirect)
            tokens["saved_at"]=store.now()
            whoop.save_private_json(whoop.TOKEN_FILE,tokens)
    except BaseException:
        return HTMLResponse("<h1>授权交换失败</h1><p>请检查网络和 WHOOP 应用配置，再重试。</p><a href='/'>返回</a>",status_code=400)
    finally:SYNC_LOCK.release()
    response=RedirectResponse("/?connected=1",status_code=303)
    response.delete_cookie("whoop_oauth_state")
    return response


@app.get("/api/export/{kind}")
def export(kind:str,start:str|None=None,end:str|None=None,days:int=Query(30,ge=1,le=731)):
    result=get_dashboard(start,end,days)
    suffix=f"{result['range']['start']}_{result['range']['end']}"
    if kind=="csv":
        buf=io.StringIO()
        keys=["date","recovery","hrv","rhr","spo2","sleep","naps","total_sleep","performance","efficiency","consistency","strain","workouts","note"]
        writer=csv.DictWriter(buf,fieldnames=keys,extrasaction="ignore")
        writer.writeheader()
        for row in result["daily"]:
            safe=dict(row)
            # Prevent spreadsheet formula injection from user annotations.
            if safe.get("note","").startswith(("=","+","-","@","\t","\r")):safe["note"]="'"+safe["note"]
            writer.writerow(safe)
        return Response("\ufeff"+buf.getvalue(),media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="whoop_{suffix}.csv"'})
    if kind=="markdown":
        return Response(report_text(result),media_type="text/markdown",headers={"Content-Disposition":f'attachment; filename="whoop_{suffix}.md"'})
    if kind=="json":
        return Response(json.dumps(result,ensure_ascii=False),media_type="application/json",headers={"Content-Disposition":f'attachment; filename="whoop_{suffix}.json"'})
    raise HTTPException(404,"导出格式不存在")


@app.get("/{path:path}")
def frontend(path:str):
    if path.startswith("api/"):raise HTTPException(404,"API 不存在")
    target=(DIST/path).resolve()
    if not target.is_relative_to(DIST.resolve()):raise HTTPException(404)
    if target.is_file():return FileResponse(target)
    if (DIST/"index.html").is_file():return FileResponse(DIST/"index.html")
    return HTMLResponse("<h1>请先构建前端</h1><p>在 frontend 目录运行 npm install 与 npm run build，再刷新此页。</p>",status_code=503)
