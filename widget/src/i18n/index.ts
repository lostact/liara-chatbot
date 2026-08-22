export interface I18nStrings {
  title: string;
  subtitle: string;
  online: string;
  inputPlaceholder: string;
  searchingStage: string;
  readingStage: string;
  sources: string;
  copy: string;
  copied: string;
  feedbackHelpful: string;
  feedbackUnhelpful: string;
  submitTicket: string;
  enterFullscreen: string;
  exitFullscreen: string;
  poweredBy: string;
  quickActionsTitle: string;
  quickActions: string[];
  you: string;
  errorTitle: string;
  errorDesc: string;
  retry: string;
  offlineMessage: string;
}

export const translations: Record<string, I18nStrings> = {
  fa: {
    title: "لیارا یار",
    subtitle: "لیارا یار، همراه شما برای استقرار برنامه‌ها، پاسخگویی سوالات و حل مشکلات است.",
    online: "آنلاین",
    inputPlaceholder: "پیام خود را بنویسید...",
    searchingStage: "در حال جست‌وجو در مستندات لیارا...",
    readingStage: "در حال مطالعه منابع...",
    sources: "منابع",
    copy: "کپی",
    copied: "کپی شد!",
    feedbackHelpful: "مفید بود",
    feedbackUnhelpful: "پاسخ ناقص یا نامناسب بود",
    submitTicket: "ثبت تیکت پشتیبانی",
    enterFullscreen: "تمام‌صفحه",
    exitFullscreen: "خروج از تمام‌صفحه",
    poweredBy: "قدرت گرفته از لیارا",
    quickActionsTitle: "دسترسی سریع",
    quickActions: [
      "چطور شروع کنم؟",
      "وضعیت سرویس",
      "لیست محصولات",
    ],
    you: "شما",
    errorTitle: "خطا در دریافت اطلاعات",
    errorDesc: "متأسفانه در حال حاضر امکان اتصال به سرور وجود ندارد. لطفاً دوباره تلاش کنید.",
    retry: "تلاش مجدد",
    offlineMessage: "اتصال قطع شد؛ در حال اتصال مجدد...",
  },
  en: {
    title: "Liara Yar",
    subtitle: "Liara Yar is here to help with deployment, answering questions, and solving problems.",
    online: "Online",
    inputPlaceholder: "Write your message...",
    searchingStage: "Searching Liara docs...",
    readingStage: "Reading sources...",
    sources: "Sources",
    copy: "Copy",
    copied: "Copied!",
    feedbackHelpful: "Helpful",
    feedbackUnhelpful: "Not helpful",
    submitTicket: "Submit Support Ticket",
    enterFullscreen: "Enter fullscreen",
    exitFullscreen: "Exit fullscreen",
    poweredBy: "Powered by Liara",
    quickActionsTitle: "Quick Actions",
    quickActions: [
      "How to get started?",
      "Service Status",
      "Product List",
    ],
    you: "You",
    errorTitle: "Error fetching data",
    errorDesc: "Unfortunately, the server is currently unreachable. Please try again.",
    retry: "Retry",
    offlineMessage: "Connection lost; reconnecting...",
  },
};

export function getTranslations(lang: string = "fa"): I18nStrings {
  return translations[lang] || translations.fa;
}
