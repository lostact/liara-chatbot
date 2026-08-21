import re
from typing import Optional, Tuple
from shared.text import normalize_search_text

INJECTION_PATTERNS = [
    re.compile(r"(?i)ignore\s+(all\s+)?(previous|above)\s+instructions"),
    re.compile(r"(?i)system\s+prompt"),
    re.compile(r"(?i)you\s+are\s+now\s+in\s+(developer|dan)\s+mode"),
    re.compile(r"(?i)disregard\s+(the\s+)?(previous\s+)?rules"),
    re.compile(r"(?i)jailbreak"),
    re.compile(r"(?i)reveal\s+(your\s+)?(hidden\s+)?instructions"),
    re.compile(r"(?i)print\s+the\s+prompt"),
]

GREETING_PATTERNS = [
    re.compile(r"^(سلام|درود|سلام وقت بخیر|درود وقت بخیر|سلام علیکم|hi|hello|hey)[\s!.]*$", re.IGNORECASE),
]

THANKS_PATTERNS = [
    re.compile(r"^(ممنون|مرسی|متشکرم|تشکر|دستت درد نکنه|thanks|thank you|thx)[\s!.]*$", re.IGNORECASE),
]

BARE_PRODUCT_MAP = {
    "django": ("https://docs.liara.ir/paas/django/getting-started", "مستندات پلتفرم Django در لیارا"),
    "nodejs": ("https://docs.liara.ir/paas/nodejs/getting-started", "مستندات پلتفرم NodeJS در لیارا"),
    "node": ("https://docs.liara.ir/paas/nodejs/getting-started", "مستندات پلتفرم NodeJS در لیارا"),
    "react": ("https://docs.liara.ir/paas/react/getting-started", "مستندات پلتفرم React در لیارا"),
    "nextjs": ("https://docs.liara.ir/paas/nextjs/getting-started", "مستندات پلتفرم Next.js در لیارا"),
    "laravel": ("https://docs.liara.ir/paas/laravel/getting-started", "مستندات پلتفرم Laravel در لیارا"),
    "flask": ("https://docs.liara.ir/paas/flask/getting-started", "مستندات پلتفرم Flask در لیارا"),
    "postgres": ("https://docs.liara.ir/databases/postgresql/getting-started", "مستندات دیتابیس PostgreSQL در لیارا"),
    "postgresql": ("https://docs.liara.ir/databases/postgresql/getting-started", "مستندات دیتابیس PostgreSQL در لیارا"),
    "mysql": ("https://docs.liara.ir/databases/mysql/getting-started", "مستندات دیتابیس MySQL در لیارا"),
    "mariadb": ("https://docs.liara.ir/databases/mariadb/getting-started", "مستندات دیتابیس MariaDB در لیارا"),
    "mongodb": ("https://docs.liara.ir/databases/mongodb/getting-started", "مستندات دیتابیس MongoDB در لیارا"),
    "redis": ("https://docs.liara.ir/databases/redis/getting-started", "مستندات دیتابیس Redis در لیارا"),
    "cli": ("https://docs.liara.ir/references/cli/about", "مستندات Liara CLI"),
    "object storage": ("https://docs.liara.ir/buckets/about", "مستندات فضای ذخیره‌سازی ابری (Object Storage) لیارا"),
    "dns": ("https://docs.liara.ir/dns/about", "مستندات سرویس DNS لیارا"),
    "email": ("https://docs.liara.ir/email/about", "مستندات سرویس ایمیل لیارا"),
}


class GuardResult:
    def __init__(
        self,
        is_safe: bool,
        shortcut_type: Optional[str] = None,  # "greeting" | "thanks" | "product_nav" | "injection"
        shortcut_response: Optional[str] = None,
        shortcut_links: Optional[list] = None,
        rejection_reason: Optional[str] = None,
    ):
        self.is_safe = is_safe
        self.shortcut_type = shortcut_type
        self.shortcut_response = shortcut_response
        self.shortcut_links = shortcut_links or []
        self.rejection_reason = rejection_reason


def check_input_guard(message: str, lang: str = "fa") -> GuardResult:
    """
    Check input against security rules, length caps, prompt injection,
    and deterministic shortcuts (greeting, thanks, bare product names).
    """
    cleaned = message.strip()
    norm = normalize_search_text(cleaned)

    # 1. Length check
    if len(cleaned) > 1500:
        return GuardResult(
            is_safe=False,
            rejection_reason="پیام شما بیش از حد مجاز (۱۵۰۰ کاراکتر) است. لطفاً سوال خود را خلاصه‌تر بپرسید.",
        )

    # 2. Prompt injection check
    for pattern in INJECTION_PATTERNS:
        if pattern.search(cleaned):
            return GuardResult(
                is_safe=False,
                shortcut_type="injection",
                shortcut_response=(
                    "متأسفانه نمی‌توانم این دستور را پردازش کنم. من دستیار هوشمند مستندات لیارا هستم و تنها به سوالات مرتبط با پلتفرم و سرویس‌های لیارا پاسخ می‌دهم."
                    if lang == "fa"
                    else "I cannot process this request. I am the Liara Documentation Assistant and only answer questions related to Liara services."
                ),
            )

    # 3. Greeting shortcut
    for pattern in GREETING_PATTERNS:
        if pattern.match(cleaned):
            resp = (
                "سلام! من دستیار هوشمند مستندات لیارا هستم. درباره استقرار برنامه‌ها، دیتابیس‌ها، فضای ذخیره‌سازی یا CLI لیارا چه سوالی دارید؟"
                if lang == "fa"
                else "Hello! I am Liara Docs Assistant. How can I help you with Liara deployment, databases, object storage, or CLI?"
            )
            return GuardResult(is_safe=True, shortcut_type="greeting", shortcut_response=resp)

    # 4. Thanks shortcut
    for pattern in THANKS_PATTERNS:
        if pattern.match(cleaned):
            resp = (
                "خواهش می‌کنم! اگر سوال دیگری درباره لیارا دارید، خوشحال می‌شوم کمکتان کنم."
                if lang == "fa"
                else "You're welcome! Let me know if you have any other questions about Liara."
            )
            return GuardResult(is_safe=True, shortcut_type="thanks", shortcut_response=resp)

    # 5. Bare product name shortcut
    if norm in BARE_PRODUCT_MAP:
        url, title = BARE_PRODUCT_MAP[norm]
        resp = (
            f"برای مشاهده مستندات کامل **{norm}** در لیارا می‌توانید به صفحه زیر مراجعه کنید:\n- [{title}]({url})\n\nاگر سوال مشخصی درباره استقرار یا تنظیمات آن دارید، بفرمایید تا راهنماییتان کنم."
            if lang == "fa"
            else f"You can find documentation for **{norm}** here:\n- [{title}]({url})\n\nFeel free to ask specific questions about deployment or configurations!"
        )
        return GuardResult(
            is_safe=True,
            shortcut_type="product_nav",
            shortcut_response=resp,
            shortcut_links=[{"label": title, "url": url}],
        )

    return GuardResult(is_safe=True)
