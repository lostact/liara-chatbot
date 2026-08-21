from typing import Any, Dict
from fastapi import APIRouter, Depends
from app.security.site_key import verify_site_key
from shared.settings import get_settings

router = APIRouter(prefix="/v1/config", tags=["Config"])
settings = get_settings()


@router.get("")
async def get_widget_config(
    site_key: str = Depends(verify_site_key),
) -> Dict[str, Any]:
    """
    Bootstrap config for widget: theme, features, support ticket URL, default language.
    """
    return {
        "site_key": site_key,
        "features": {
            "streaming": True,
            "feedback": True,
            "suggestions": True,
            "citations": True,
        },
        "theme": {
            "accent_color": "#0f9d58",
            "position": "bottom-right",
        },
        "support_url": "https://console.liara.ir/tickets/create",
        "docs_url": "https://docs.liara.ir",
        "default_greeting": "سلام! سوالی درباره استقرار یا سرویس‌های لیارا دارید؟",
    }
