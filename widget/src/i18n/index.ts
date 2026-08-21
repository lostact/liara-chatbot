export interface I18nStrings {
  title: string;
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
}

export const translations: Record<string, I18nStrings> = {
  fa: {
    title: "دستیار مستندات لیارا",
    online: "آنلاین",
    inputPlaceholder: "سوال خود را بپرسید...",
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
  },
  en: {
    title: "Liara Docs Assistant",
    online: "Online",
    inputPlaceholder: "Ask a question...",
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
  },
};

export function getTranslations(lang: string = "fa"): I18nStrings {
  return translations[lang] || translations.fa;
}
