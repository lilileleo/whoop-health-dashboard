#!/usr/bin/env python3
"""Local OAuth and data fetcher for the WHOOP Developer API v2."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import secrets
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Iterator

from weekly import archive_snapshot


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
TOKEN_FILE = DATA_DIR / "token.json"
LOCK_FILE = DATA_DIR / "whoop.lock"
WEEK_DATA_DIR = DATA_DIR / "weeks"
API_ROOT = "https://api.prod.whoop.com"
AUTH_URL = f"{API_ROOT}/oauth/oauth2/auth"
TOKEN_URL = f"{API_ROOT}/oauth/oauth2/token"
SCOPES = (
    "offline",
    "read:recovery",
    "read:cycles",
    "read:workout",
    "read:sleep",
    "read:profile",
    "read:body_measurement",
)
COLLECTIONS = {
    "recovery": "/developer/v2/recovery",
    "sleep": "/developer/v2/activity/sleep",
    "cycle": "/developer/v2/cycle",
    "workout": "/developer/v2/activity/workout",
}


def load_dotenv(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"").strip("'"))


def config() -> tuple[str, str, str]:
    load_dotenv()
    client_id = os.getenv("WHOOP_CLIENT_ID", "").strip()
    client_secret = os.getenv("WHOOP_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv(
        "WHOOP_REDIRECT_URI", "http://localhost:8000/callback"
    ).strip()
    if not client_id or not client_secret:
        raise SystemExit(
            "请通过环境变量或本机 .env 设置 WHOOP_CLIENT_ID 和 "
            "WHOOP_CLIENT_SECRET；不要将凭据提交到版本管理。"
        )
    return client_id, client_secret, redirect_uri


def request_json(
    url: str,
    *,
    method: str = "GET",
    bearer: str | None = None,
    form: dict[str, str] | None = None,
) -> dict[str, Any]:
    headers = {"Accept": "application/json", "User-Agent": "whoop-summary/0.1"}
    data = None
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    if form is not None:
        data = urllib.parse.urlencode(form).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # Retrying token rotation after an ambiguous failure can lose the
            # refresh token. Retry only safe GETs, with bounded backoff.
            if method == "GET" and exc.code in (429, 500, 502, 503, 504) and attempt < 3:
                retry = exc.headers.get("Retry-After") or exc.headers.get("X-RateLimit-Reset") or ""
                delay = min(60, max(1, int(retry))) if retry.isdigit() else 2 ** (attempt + 1)
                time.sleep(delay)
                continue
            raise RuntimeError(f"WHOOP API 返回 HTTP {exc.code}，请检查授权或稍后重试。") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("无法连接 WHOOP API，请检查网络或代理。") from exc
    raise RuntimeError("WHOOP API 重试次数已用尽。")


def save_private_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


@contextmanager
def process_lock() -> Iterator[None]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def exchange_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict[str, Any]:
    return request_json(
        TOKEN_URL,
        method="POST",
        form={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        },
    )


def refresh_tokens(client_id: str, client_secret: str) -> dict[str, Any]:
    if not TOKEN_FILE.exists():
        raise SystemExit("尚未授权，请先运行：python3 whoop.py auth")
    current = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    refresh_token = current.get("refresh_token")
    if not refresh_token:
        raise SystemExit("token.json 中没有 refresh_token，请重新执行授权并确认包含 offline scope。")
    fresh = request_json(
        TOKEN_URL,
        method="POST",
        form={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "offline",
        },
    )
    fresh["saved_at"] = datetime.now(timezone.utc).isoformat()
    save_private_json(TOKEN_FILE, fresh)
    return fresh


def auth_command() -> None:
    client_id, client_secret, redirect_uri = config()
    parsed = urllib.parse.urlparse(redirect_uri)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise SystemExit("当前本地授权器要求 WHOOP_REDIRECT_URI 使用 http://localhost:端口/路径。")
    state = secrets.token_urlsafe(24)
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "state": state,
        }
    )
    result: dict[str, str] = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            incoming = urllib.parse.urlparse(self.path)
            expected_path = parsed.path or "/"
            if incoming.path != expected_path:
                self.send_response(404)
                self.end_headers()
                return
            values = urllib.parse.parse_qs(incoming.query)
            result["code"] = values.get("code", [""])[0]
            result["state"] = values.get("state", [""])[0]
            result["error"] = values.get("error", [""])[0]
            body = "WHOOP 授权已收到，可以关闭此页面并返回终端。".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: object) -> None:
            return

    port = parsed.port or 80
    server = HTTPServer((parsed.hostname or "localhost", port), CallbackHandler)
    server.timeout = 300
    url = f"{AUTH_URL}?{query}"
    print(f"浏览器未自动打开时，请访问：\n{url}\n")
    webbrowser.open(url)
    server.handle_request()
    server.server_close()
    if result.get("error"):
        raise SystemExit(f"WHOOP 拒绝授权：{result['error']}")
    if not result.get("code") or not secrets.compare_digest(result.get("state", ""), state):
        raise SystemExit("未收到有效授权码，或 state 校验失败。")
    tokens = exchange_code(result["code"], client_id, client_secret, redirect_uri)
    tokens["saved_at"] = datetime.now(timezone.utc).isoformat()
    save_private_json(TOKEN_FILE, tokens)
    print(f"授权成功，令牌已安全保存到 {TOKEN_FILE}")


def fetch_collection(path: str, token: str, start: str, end: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    next_token: str | None = None
    seen_tokens: set[str] = set()
    for _ in range(1000):
        params = {"start": start, "end": end, "limit": "25"}
        if next_token:
            params["nextToken"] = next_token
        payload = request_json(
            f"{API_ROOT}{path}?{urllib.parse.urlencode(params)}", bearer=token
        )
        records.extend(payload.get("records", []))
        next_token = payload.get("next_token")
        if not next_token:
            return records
        if next_token in seen_tokens:
            raise RuntimeError("WHOOP 分页游标重复，本次同步未保存，请稍后重试。")
        seen_tokens.add(next_token)
    raise RuntimeError("WHOOP 返回页数超过安全上限，本次同步未保存，请缩小时间范围。")


def fetch_command(days: int) -> None:
    client_id, client_secret, _ = config()
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    with process_lock():
        tokens = refresh_tokens(client_id, client_secret)
        access_token = tokens.get("access_token")
        if not access_token:
            raise SystemExit("刷新响应中没有 access_token。")
        snapshot: dict[str, Any] = {
            "fetched_at": now.isoformat(),
            "start": start.isoformat(),
            "end": now.isoformat(),
        }
        for name, path in COLLECTIONS.items():
            snapshot[name] = fetch_collection(path, access_token, start.isoformat(), now.isoformat())
        save_private_json(DATA_DIR / "latest.json", snapshot)
        weekly_paths = archive_snapshot(snapshot, WEEK_DATA_DIR)
    print(json.dumps({key: len(snapshot.get(key, [])) for key in COLLECTIONS}, ensure_ascii=False, indent=2))
    print(f"原始数据已保存到 {DATA_DIR / 'latest.json'}")
    print(f"周归档已更新：{', '.join(path.stem for path in weekly_paths) or '无可归档记录'}")


def archive_command(*, quiet: bool = False) -> list[Path]:
    latest_path = DATA_DIR / "latest.json"
    if not latest_path.exists():
        raise SystemExit(f"找不到数据文件：{latest_path}。请先运行 python3 whoop.py fetch --days 14")
    with process_lock():
        snapshot = json.loads(latest_path.read_text(encoding="utf-8"))
        paths = archive_snapshot(snapshot, WEEK_DATA_DIR)
    if not quiet:
        print(f"周归档已更新：{', '.join(path.stem for path in paths) or '无可归档记录'}")
    return paths


def report_command() -> None:
    from report import generate_report

    archive_command(quiet=True)
    markdown_path, html_path = generate_report()
    print(f"文本摘要：{markdown_path}")
    print(f"可视化报告：{html_path}")


def daily_command(days: int) -> None:
    fetch_command(days)
    report_command()


def main() -> None:
    parser = argparse.ArgumentParser(description="WHOOP 本地授权与数据拉取")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("auth", help="启动本地 OAuth 回调并完成首次授权")
    fetch_parser = sub.add_parser("fetch", help="刷新令牌并获取最近数据")
    fetch_parser.add_argument("--days", type=int, default=2, help="获取最近多少天，默认 2")
    sub.add_parser("archive", help="将 latest.json 按 ISO 周合并到独立归档")
    sub.add_parser("report", help="根据已拉取的数据生成中文摘要和可视化报告")
    daily_parser = sub.add_parser("daily", help="拉取数据并生成日报")
    daily_parser.add_argument("--days", type=int, default=14, help="获取最近多少天，默认 14")
    args = parser.parse_args()
    try:
        if args.command == "auth":
            auth_command()
        elif args.command == "fetch":
            fetch_command(max(1, args.days))
        elif args.command == "archive":
            archive_command()
        elif args.command == "report":
            report_command()
        elif args.command == "daily":
            daily_command(max(1, args.days))
    except RuntimeError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
