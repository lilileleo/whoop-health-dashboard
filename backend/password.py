"""Generate a self-hosted dashboard password hash without exposing the password."""
from getpass import getpass
from .security import password_hash

if __name__ == "__main__":
    password = getpass("设置看板密码（至少 12 个字符）：")
    if len(password) < 12:
        raise SystemExit("密码至少需要 12 个字符。")
    if password != getpass("再次输入："):
        raise SystemExit("两次密码不一致。")
    print("WHOOP_DASHBOARD_PASSWORD_HASH=" + password_hash(password))
