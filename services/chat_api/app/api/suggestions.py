from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from app.security.site_key import verify_site_key

router = APIRouter(prefix="/v1/suggestions", tags=["Suggestions"])

PAGE_SUGGESTIONS_MAP = {
    "django": [
        "چطور برنامه Django رو روی لیارا دیپلوی کنم؟",
        "تنظیم دیتابیس Postgres برای Django",
        "اجرای دستورات manage.py migrate",
        "مدیریت فایلهای استاتیک و مدیا در Object Storage",
    ],
    "nodejs": [
        "نحوه استقرار برنامه NodeJS",
        "تنظیم پورت و متغیرهای محیطی",
        "استقرار Next.js روی پلتفرم لیارا",
        "اتصال به دیتابیس MongoDB",
    ],
    "laravel": [
        "استقرار برنامه Laravel در لیارا",
        "تنظیم کلید APP_KEY و متغیرهای محیطی",
        "اجرای migrationها در لاراول",
        "اتصال به دیتابیس MariaDB",
    ],
    "postgres": [
        "نحوه اتصال به دیتابیس Postgres در لیارا",
        "روش‌های پشتیبان‌گیری و بازیابی داده‌ها",
        "افزایش منابع سخت‌افزاری دیتابیس",
    ],
    "cli": [
        "نحوه نصب و لاگین در Liara CLI",
        "دستورات پرکاربرد liara deploy",
        "مشاهده لاگ‌های زنده با CLI",
    ],
}


@router.get("")
async def get_page_suggestions(
    context: Optional[str] = Query(default=None, description="Current page url or service tag"),
    site_key: str = Depends(verify_site_key),
) -> List[str]:
    if context:
        ctx_lower = context.lower()
        for key, suggestions in PAGE_SUGGESTIONS_MAP.items():
            if key in ctx_lower:
                return suggestions

    # Default general starter suggestions
    return [
        "چطور برنامه‌ام را روی لیارا مستقر کنم؟",
        "نحوه اتصال دیتابیس به برنامه",
        "راهنمای نصب و استفاده از Liara CLI",
        "نحوه تنظیم دامنه‌ی اختصاصی",
    ]
