from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def get_client_ip(request: Request) -> str:
    """Retrieve client IP address, checking X-Forwarded-For if behind a reverse proxy (Caddy)."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Take the first IP in the comma-separated chain
        client_ip = forwarded_for.split(",")[0].strip()
        if client_ip:
            return client_ip
    return get_remote_address(request) or "127.0.0.1"


from app.core.config import settings

limiter = Limiter(key_func=get_client_ip, enabled=(settings.ENVIRONMENT != "test"))

