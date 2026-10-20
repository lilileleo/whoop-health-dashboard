"""Optional single-owner authentication for a self-hosted deployment."""
import base64
import hashlib
import hmac
import ipaddress
import os
from dataclasses import dataclass
from urllib.parse import urlparse

TAILSCALE_IPV4 = ipaddress.ip_network("100.64.0.0/10")
TAILSCALE_IPV6 = ipaddress.ip_network("fd7a:115c:a1e0::/48")


def tailscale_peer_allowed(host: str) -> bool:
    """Defense in depth; actual device authorization remains the tailnet policy's job."""
    try:
        address = ipaddress.ip_address(host)
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        return address.is_loopback or address in (TAILSCALE_IPV4 if address.version == 4 else TAILSCALE_IPV6)
    except ValueError:
        return False


def password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600000).hex()
    return f"pbkdf2_sha256:600000:{salt}:{digest}"


def verify_password(password, encoded):
    try:
        algorithm, iterations, salt, digest = encoded.split(":")
        if algorithm != "pbkdf2_sha256" or not 100000 <= int(iterations) <= 2000000:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class Settings:
    server: bool = False
    origin: str = ""
    username: str = "owner"
    password: str = ""
    sync_minutes: int = 0
    allow_http: bool = False
    auth_mode: str = "basic"
    tailscale_ip: str = ""

    @property
    def insecure_http(self):
        return self.server and self.origin.startswith("http://")

    @property
    def hostname(self):
        return urlparse(self.origin).hostname

    @classmethod
    def load(cls):
        settings = cls(
            server=os.environ.get("WHOOP_SERVER_MODE", "false").lower() == "true",
            origin=os.environ.get("WHOOP_PUBLIC_ORIGIN", "").rstrip("/"),
            username=os.environ.get("WHOOP_DASHBOARD_USER", "owner"),
            password=os.environ.get("WHOOP_DASHBOARD_PASSWORD_HASH", ""),
            sync_minutes=int(os.environ.get("WHOOP_SYNC_INTERVAL_MINUTES", "0")),
            allow_http=os.environ.get("WHOOP_ALLOW_INSECURE_HTTP", "false").lower() == "true",
            auth_mode=os.environ.get("WHOOP_AUTH_MODE", "basic"),
            tailscale_ip=os.environ.get("WHOOP_TAILSCALE_IP", ""),
        )
        if settings.auth_mode not in ("basic", "tailscale"):
            raise RuntimeError("WHOOP_AUTH_MODE 仅支持 basic 或 tailscale")
        if settings.auth_mode == "tailscale" and not settings.server:
            raise RuntimeError("Tailscale 免登录必须保持 WHOOP_SERVER_MODE=true")
        if settings.server:
            parsed = urlparse(settings.origin)
            try:
                port = parsed.port
                valid_http = False
                if settings.allow_http and parsed.scheme == "http":
                    address = ipaddress.ip_address(parsed.hostname or "")
                    valid_http = address.version == 4 and not address.is_unspecified and not address.is_multicast
                valid_origin = (parsed.scheme == "https" or valid_http) and parsed.hostname and not (
                    parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password
                ) and port != 0
            except ValueError:
                valid_origin = False
            if not valid_origin:
                raise RuntimeError("服务器默认要求 HTTPS；临时 IPv4 HTTP 测试需显式设置 WHOOP_ALLOW_INSECURE_HTTP=true")
            if settings.auth_mode == "tailscale":
                try:
                    address = ipaddress.IPv4Address(settings.tailscale_ip)
                    valid_tailnet = address in TAILSCALE_IPV4 and parsed.hostname == str(address)
                except ValueError:
                    valid_tailnet = False
                if not valid_tailnet:
                    raise RuntimeError("免登录仅支持 Tailscale IPv4：WHOOP_TAILSCALE_IP 需属于 100.64.0.0/10，且必须与访问地址一致")
            else:
                try:
                    alg, rounds, salt, digest = settings.password.split(":")
                    valid_hash = alg == "pbkdf2_sha256" and 100000 <= int(rounds) <= 2000000 and len(bytes.fromhex(salt)) >= 16 and len(bytes.fromhex(digest)) == 32
                except (ValueError, TypeError):
                    valid_hash = False
                if not settings.username or not valid_hash:
                    raise RuntimeError("服务器模式需先设置用户名和密码哈希；运行 python3 -m backend.password 生成")
        if settings.sync_minutes and settings.sync_minutes < 15:
            raise RuntimeError("自动同步间隔至少为 15 分钟；设为 0 则关闭")
        return settings


def authorized(header: str, settings: Settings):
    if not settings.server or settings.auth_mode == "tailscale":
        return True
    try:
        scheme, value = header.split(" ", 1)
        if scheme.lower() != "basic": return False
        user, password = base64.b64decode(value, validate=True).decode().split(":", 1)
        return hmac.compare_digest(user.encode(), settings.username.encode()) and verify_password(password, settings.password)
    except (ValueError, UnicodeDecodeError):
        return False
