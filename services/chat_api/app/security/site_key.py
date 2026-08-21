import hashlib
import hmac
from typing import Optional
from fastapi import HTTPException, Header, Request, status
from shared.settings import get_settings

settings = get_settings()


def compute_visitor_hash(ip: str, user_agent: str) -> str:
    """
    Generate opaque visitor hash using HMAC-SHA256 with daily rotating salt.
    """
    salt = settings.security.HMAC_SALT
    raw = f"{ip}|{user_agent}|{salt}"
    return hmac.new(salt.encode(), raw.encode(), hashlib.sha256).hexdigest()[:32]


async def verify_site_key(
    request: Request,
    x_site_key: Optional[str] = Header(None),
) -> str:
    """
    Validates X-Site-Key header against allowed site keys and origin checks.
    """
    if not x_site_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Site-Key header",
        )

    if x_site_key not in settings.security.ALLOWED_SITE_KEYS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or unauthorized site key",
        )

    # Origin header check if present
    origin = request.headers.get("origin")
    if origin and settings.ENV == "production":
        if origin not in settings.security.CORS_ORIGINS:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Origin not allowed for this site key",
            )

    return x_site_key
