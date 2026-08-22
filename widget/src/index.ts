import { getTranslations, I18nStrings } from "./i18n/index";
import { renderMarkdown } from "./markdown";
import { ChatStreamClient } from "./sse";
import styles from "./styles.css?raw";

interface WidgetOptions {
  siteKey: string;
  apiUrl?: string;
  lang?: string;
  position?: "bottom-right" | "bottom-left";
  accent?: string;
  greeting?: string;
  allowFullscreen?: boolean;
  fullscreen?: boolean;
}

interface MessageState {
  role: "user" | "assistant";
  content: string;
  citations?: Array<{ n: number; title: string; url: string; heading_path?: string[] }>;
}

/* ──────────────────────────────────────────────────────────────
   SVG Icon Helpers (from icons/ folder)
   ────────────────────────────────────────────────────────────── */

function svgMinimize(): string {
  return `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20 12L4 12" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}

function svgExpand(): string {
  return `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M16.4978 3.26621C17.3422 3.25421 20.1387 2.67328 20.7316 3.26621C21.3245 3.85913 20.7436 6.65559 20.7316 7.5M20.5038 3.49097L13.5 10.4961" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M3.26621 16.5001C3.25421 17.3445 2.67328 20.141 3.26621 20.7339C3.85913 21.3268 6.65559 20.7459 7.5 20.7339M10.5019 13.4976L3.49809 20.5027" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}

function svgSend(): string {
  return `<svg width="29" height="29" viewBox="0 0 29 29" fill="none" xmlns="http://www.w3.org/2000/svg"><g clip-path="url(#clip0_6_203)"><path d="M2.52861 14.4077L15.4178 14.1086M18.5158 21.2402C18.551 21.3176 18.5617 21.4039 18.5465 21.4876C18.5312 21.5712 18.4907 21.6482 18.4304 21.7081C18.3702 21.7681 18.293 21.8082 18.2093 21.8231C18.1256 21.8379 18.0393 21.8268 17.9621 21.7912L2.77011 14.7751C2.69829 14.7434 2.63698 14.6919 2.59337 14.6266C2.54975 14.5613 2.52563 14.485 2.52382 14.4065C2.52201 14.328 2.54259 14.2506 2.58316 14.1834C2.62372 14.1162 2.68259 14.0619 2.75288 14.0269L17.6056 6.31517C17.6811 6.27605 17.7668 6.26095 17.8511 6.27191C17.9354 6.28287 18.0143 6.31935 18.0773 6.37647C18.1403 6.43359 18.1842 6.5086 18.2033 6.59144C18.2224 6.67429 18.2158 6.76099 18.1842 6.83993L15.5366 13.4498C15.4528 13.6586 15.4122 13.8823 15.4172 14.1073C15.4222 14.3323 15.4726 14.5539 15.5656 14.7588L18.5158 21.2402Z" stroke="#595959" stroke-width="2" stroke-linecap="round"/></g><defs><clipPath id="clip0_6_203"><rect width="20" height="20" fill="white" transform="matrix(-0.690593 0.723243 0.723243 0.690593 13.8119 0)"/></clipPath></defs></svg>`;
}

function svgLiaraLogo(): string {
  return `<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M15.5307 4.80734C15.2393 4.58782 15.0275 4.42166 14.972 4.03664C14.8818 3.41189 15.224 2.85642 15.8758 2.77875C16.1578 2.74516 16.4388 2.81109 16.6636 2.98746C16.8852 3.16376 17.0277 3.42028 17.0597 3.70086C17.1159 4.20566 16.8913 4.53535 16.473 4.79354C16.4725 5.4054 16.4548 6.12854 16.4774 6.73164C17.1842 6.80341 17.589 7.14787 18.1845 7.47642C18.2834 7.53099 18.4892 7.66594 18.5842 7.70232L18.9471 6.97869C19.0921 6.69046 19.1875 6.45572 19.4141 6.21611C19.9008 5.70144 20.6776 5.5427 21.3015 5.90729C21.5324 6.0422 21.7745 6.19588 22.0116 6.33831L25.9944 8.74161C26.4005 8.98605 26.8131 9.22454 27.215 9.47509C28.042 9.99073 28.639 10.8086 28.936 11.7282C29.0471 12.0656 29.1137 12.4158 29.1346 12.7702C29.1493 13.0363 29.1421 13.3445 29.1418 13.6144L29.1401 14.9997L29.1406 22.5405C29.141 23.0224 29.1671 23.8227 29.1229 24.2722C29.0686 24.7932 28.9181 25.2995 28.6792 25.7661C28.4117 26.2752 28.041 26.7237 27.5906 27.0831C27.2853 27.3293 26.8505 27.5671 26.5065 27.7701L24.4493 28.9896C24.1435 29.1731 23.7779 29.3785 23.4886 29.5776C23.3511 29.6723 23.031 30.0025 22.9017 30.1294L21.7416 31.2524C21.5347 31.4511 21.3266 31.6586 21.1117 31.8479C20.9304 32.0074 20.7303 32.0543 20.5103 31.9264C20.314 31.8123 20.2633 31.6555 20.2594 31.4405C20.2534 31.1222 20.2566 30.8028 20.2571 30.4842C20.2556 29.7188 20.2592 28.9536 20.2679 28.1883C19.8552 28.4121 19.4563 28.663 19.0475 28.8916C18.7278 29.0705 18.2873 29.3709 17.9553 29.4968C17.5653 29.6447 17.0824 29.2739 17.118 28.8599C17.1146 28.3663 17.1178 27.8788 17.1186 27.3883L17.118 22.0369C17.1179 21.6474 17.1015 21.0991 17.1249 20.7246C17.1438 20.4578 17.1975 20.1946 17.2848 19.9416C17.4558 19.4282 17.7604 18.969 18.1678 18.6111C18.5255 18.2993 19.0657 18.0111 19.4835 17.7639L24.0923 15.0363C24.5144 14.7871 24.9337 14.53 25.3608 14.2904C25.4529 14.2388 25.5605 14.2319 25.6634 14.2357C26.04 14.2422 26.3016 14.5815 26.3034 14.9384C26.3062 15.4665 26.3016 15.9944 26.3013 16.5225L26.304 22.1283C26.3045 22.7738 26.3743 23.4922 26.1245 24.0959C25.9739 24.4664 25.7391 24.7974 25.4386 25.0626C25.1972 25.2754 24.912 25.4305 24.6353 25.5948L23.7364 26.1268C22.899 26.6208 22.061 27.1391 21.2136 27.613L21.2119 30.4424L22.212 29.4788C22.4878 29.2136 22.8537 28.846 23.1677 28.6435C23.4913 28.4348 23.86 28.2232 24.1936 28.0271L25.7546 27.1017C26.115 26.8876 26.613 26.6124 26.934 26.3634C27.7895 25.7004 28.1912 24.7912 28.1905 23.7221C28.19 22.9634 28.1879 22.2043 28.1879 21.4467L28.1861 14.0953C28.1876 13.592 28.2141 12.9364 28.1305 12.4426C28.0307 11.8537 27.6857 11.1728 27.2666 10.7431C27.1139 10.5872 26.9452 10.4476 26.7632 10.3267C26.4745 10.1353 26.1237 9.93451 25.8246 9.75225L23.6873 8.46063L21.9121 7.39089C21.5815 7.19024 21.252 6.96543 20.9098 6.78537C20.8068 6.73109 20.7 6.68373 20.5812 6.68066C20.41 6.67622 20.2557 6.74425 20.1351 6.86362C19.9612 7.03588 19.5066 7.94407 19.4006 8.20413C19.7674 8.43513 20.1808 8.66798 20.557 8.89099L23.071 10.3798L23.9529 10.9072C24.1386 11.0179 24.479 11.1944 24.6035 11.3709C24.7284 11.5481 24.7113 11.8927 24.5704 12.0515C24.5105 12.1287 24.3749 12.2185 24.2899 12.2697C23.7978 12.5658 23.3012 12.8554 22.8065 13.1473L18.326 15.7996C17.71 16.1631 17.2456 16.5132 16.5165 16.6329C15.1841 16.8516 14.3712 16.2134 13.2923 15.5703L10.7276 14.051L8.59886 12.7866L7.97655 12.4184C7.69744 12.2552 7.36058 12.1103 7.32005 11.7475C7.30086 11.5882 7.34886 11.4281 7.45262 11.3054C7.66816 11.0509 8.54262 10.6627 8.82374 10.4504C9.26736 10.1153 12.4788 8.38262 12.5974 8.19556C12.8184 8.08468 13.1735 7.84258 13.415 7.70374C13.5343 7.7107 14.5132 7.05642 14.7288 6.96391C15.0143 6.84136 15.2127 6.78746 15.5184 6.72962C15.5308 6.0898 15.5186 5.4481 15.5307 4.80734Z" fill="#87FCC4"/>
<path d="M4.20659 26.9134C4.12485 26.7912 3.98856 26.6898 3.89116 26.5762C3.7765 26.4424 3.67335 26.3005 3.57081 26.1583C2.73405 24.9973 2.85782 23.6331 2.85824 22.2751L2.85733 14.8988C2.85781 14.2155 2.84699 13.5221 2.86496 12.8381C2.90073 11.8087 3.38191 10.6961 4.13593 9.98163C4.61488 9.52781 5.42068 9.1058 6.0069 8.7508L10.0686 6.2938C10.3062 6.14826 10.5497 5.99048 10.7918 5.85769C11.1007 5.68817 11.5969 5.67109 11.9291 5.78512C12.5452 5.99659 12.7968 6.48063 13.0676 7.0141L13.415 7.70374C13.1735 7.84258 12.8184 8.08468 12.5974 8.19556C12.4367 7.87779 12.0597 7.00052 11.8246 6.80962C11.7013 6.70944 11.5443 6.65782 11.3849 6.67688C11.2821 6.68918 11.1829 6.73204 11.0928 6.78111C10.7694 6.95708 10.4582 7.16817 10.1427 7.35915L6.25545 9.70324C5.93672 9.89603 5.49653 10.1459 5.19936 10.3533C4.963 10.5215 4.75117 10.7215 4.56992 10.9475C3.82529 11.8645 3.82128 12.6137 3.82499 13.7134L3.82346 14.8168L3.82319 22.5428C3.82439 23.7926 3.70264 24.9148 4.59775 25.9361C4.70069 26.0535 5.11453 26.3748 5.13627 26.4883C5.23346 26.9954 5.12299 27.5756 5.17866 28.093C5.42884 27.9262 5.78698 27.7278 6.0507 27.57L7.41371 26.7449C7.64478 26.6064 8.14703 26.321 8.33804 26.167C7.35879 25.4859 6.3417 25.2832 5.86622 24.0422C5.77418 23.7993 5.72047 23.5439 5.70702 23.2848C5.68412 22.8591 5.70354 22.2684 5.70449 21.8288L5.70275 16.3839C5.70263 15.9062 5.7014 15.423 5.7049 14.9454C5.70705 14.8152 5.73591 14.706 5.78439 14.5869C5.91363 14.2693 6.37184 14.1412 6.66644 14.3035C7.04561 14.5125 7.42398 14.7458 7.80105 14.9681L10.2267 16.4048L12.4973 17.7431C13.5596 18.3709 14.2842 18.6893 14.7271 19.9565C14.8194 20.2171 14.8762 20.489 14.896 20.7646C14.9198 21.1293 14.9017 21.7157 14.9015 22.0935L14.9012 27.3824C14.9021 27.8716 14.907 28.3666 14.9017 28.856C14.898 28.9623 14.8734 29.079 14.8263 29.1739C14.6853 29.4579 14.2957 29.6231 13.9979 29.4832C13.6149 29.3031 13.2398 29.0495 12.8707 28.8315L10.5847 27.4936C10.2308 27.2854 9.64319 26.914 9.30119 26.7478L9.28185 26.7385L6.46582 28.4157C5.99012 28.7005 5.51069 28.9938 5.0298 29.2703C4.95583 29.309 4.87578 29.3503 4.79207 29.3596C4.56347 29.385 4.28234 29.2616 4.23478 29.0181C4.19391 28.8088 4.21798 28.5891 4.21207 28.3764C4.19871 27.8945 4.2348 27.3935 4.20659 26.9134Z" fill="#87FCC4"/>
<path d="M16.0134 0C16.4298 0.0528477 16.3404 0.471457 16.3491 0.782694C16.3567 1.05773 16.3523 1.34461 16.3388 1.61929C16.3289 1.82043 16.2069 1.92232 16.0163 1.95603C15.5146 1.90529 15.7001 1.313 15.6649 0.948962C15.6448 0.741216 15.6678 0.447761 15.6863 0.239981C15.7005 0.080755 15.8679 0.0142346 16.0134 0Z" fill="#87FCC4"/>
<path d="M18.3409 1.11055C18.8921 1.12952 18.6886 1.67105 18.3848 1.89538C18.155 2.06506 17.863 2.53359 17.5637 2.56823C17.2237 2.53951 17.1024 2.25165 17.3174 1.99831C17.5667 1.70455 17.8931 1.41294 18.1868 1.16296C18.2235 1.13169 18.2938 1.11793 18.3409 1.11055Z" fill="#87FCC4"/>
<path d="M13.6189 1.10717C13.9608 1.1118 14.4053 1.76127 14.6791 1.97999C14.8606 2.12496 14.8919 2.48823 14.5672 2.56532C14.1605 2.58405 13.9733 2.17573 13.6914 1.95374C13.4271 1.74552 13.0707 1.21899 13.6189 1.10717Z" fill="#87FCC4"/>
<path d="M13.6721 3.39394C13.9045 3.3448 14.1339 3.48919 14.1888 3.71922C14.2438 3.94926 14.1042 4.1809 13.8744 4.24109C13.7208 4.28132 13.5574 4.23555 13.4473 4.1215C13.3373 4.00747 13.2981 3.84307 13.3447 3.69195C13.3914 3.54086 13.5167 3.42679 13.6721 3.39394Z" fill="#87FCC4"/>
<path d="M18.1904 3.3943C18.4246 3.36238 18.641 3.52345 18.6765 3.75594C18.7119 3.98842 18.5532 4.20615 18.3201 4.24476C18.1663 4.27026 18.0106 4.21134 17.9127 4.0906C17.8148 3.96986 17.7898 3.806 17.8473 3.66178C17.9049 3.51757 18.036 3.41535 18.1904 3.3943Z" fill="#87FCC4"/>
</svg>`;
}

function svgChipHowTo(): string {
  return `<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M6.16661 8.0001C6.16649 8.13267 6.11373 8.25976 6.01994 8.35344L4.18661 10.1868C4.09182 10.2751 3.96646 10.3232 3.83692 10.3209C3.70739 10.3186 3.5838 10.2661 3.49219 10.1745C3.40058 10.0829 3.34811 9.95932 3.34582 9.82978C3.34354 9.70025 3.39162 9.57489 3.47994 9.4801L4.95994 8.0001L3.47994 6.5201C3.43081 6.47433 3.39141 6.41913 3.36409 6.35779C3.33676 6.29646 3.32206 6.23025 3.32088 6.16312C3.31969 6.09598 3.33204 6.0293 3.35719 5.96704C3.38234 5.90478 3.41977 5.84822 3.46725 5.80074C3.51473 5.75326 3.57128 5.71583 3.63354 5.69069C3.6958 5.66554 3.76249 5.65319 3.82962 5.65437C3.89676 5.65556 3.96297 5.67025 4.0243 5.69758C4.08563 5.72491 4.14083 5.76431 4.18661 5.81344L6.01994 7.64677C6.11394 7.7401 6.16661 7.86744 6.16661 8.0001ZM7.49994 9.33344C7.36733 9.33344 7.24015 9.38611 7.14639 9.47988C7.05262 9.57365 6.99994 9.70083 6.99994 9.83344C6.99994 9.96604 7.05262 10.0932 7.14639 10.187C7.24015 10.2808 7.36733 10.3334 7.49994 10.3334H10.8333C10.9659 10.3334 11.0931 10.2808 11.1868 10.187C11.2806 10.0932 11.3333 9.96604 11.3333 9.83344C11.3333 9.70083 11.2806 9.57365 11.1868 9.47988C11.0931 9.38611 10.9659 9.33344 10.8333 9.33344H7.49994Z" fill="#62E2DA"/><path d="M0 3.16667C0 2.52267 0.522667 2 1.16667 2H14.8333C15.4773 2 16 2.52267 16 3.16667V12.8333C16 13.1428 15.8771 13.4395 15.6583 13.6583C15.4395 13.8771 15.1428 14 14.8333 14H1.16667C0.857247 14 0.560501 13.8771 0.341709 13.6583C0.122916 13.4395 0 13.1428 0 12.8333L0 3.16667ZM1.16667 3C1.12246 3 1.08007 3.01756 1.04882 3.04882C1.01756 3.08007 1 3.12246 1 3.16667V12.8333C1 12.9253 1.07467 13 1.16667 13H14.8333C14.8775 13 14.9199 12.9824 14.9512 12.9512C14.9824 12.9199 15 12.8775 15 12.8333V3.16667C15 3.12246 14.9824 3.08007 14.9512 3.04882C14.9199 3.01756 14.8775 3 14.8333 3H1.16667Z" fill="#62E2DA"/></svg>`;
}

function svgChipStatus(): string {
  return `<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><g clip-path="url(#clip0_1_1767)"><path d="M13.5481 0.5H14.3321C14.6414 0.5 14.938 0.622825 15.1568 0.841473C15.3756 1.06012 15.4986 1.3567 15.4987 1.666V2.45067C15.4992 4.27801 14.8017 6.03653 13.5487 7.36667L12.7301 8.236C12.3917 8.59509 12.0366 8.93814 11.6661 9.264V12.6227C11.6661 13.0327 11.4507 13.412 11.0994 13.6227L8.09007 15.4287C8.02175 15.4697 7.94462 15.4938 7.86509 15.499C7.78557 15.5042 7.70596 15.4903 7.6329 15.4584C7.55984 15.4266 7.49545 15.3778 7.44509 15.316C7.39473 15.2542 7.35987 15.1813 7.3434 15.1033L6.70141 12.0553C6.66824 12.029 6.63705 12.0002 6.60807 11.9693L5.36007 10.64L4.03074 9.39133C3.99984 9.36236 3.97109 9.33116 3.94474 9.298L0.897405 8.656C0.819315 8.63971 0.746256 8.60497 0.684329 8.55469C0.622403 8.5044 0.573407 8.44003 0.541433 8.36695C0.509459 8.29386 0.495436 8.21419 0.500534 8.13458C0.505632 8.05497 0.529704 7.97774 0.570739 7.90933L2.37741 4.9C2.58807 4.54867 2.96741 4.33333 3.37741 4.33333H6.7354C7.06128 3.96324 7.40432 3.60863 7.7634 3.27067L8.63274 2.45067C9.96255 1.19795 11.7205 0.500215 13.5474 0.5H13.5481ZM9.31874 3.17867L8.4494 3.998C7.63123 4.76889 6.90323 5.63018 6.2794 6.56533L4.81741 8.75867L6.05674 9.92133C6.06462 9.92855 6.07219 9.93612 6.07941 9.944L7.24141 11.1827L9.4334 9.72133C10.3694 9.09727 11.2313 8.36881 12.0027 7.55L12.8214 6.68133C13.8997 5.53662 14.4999 4.02325 14.4994 2.45067V1.66667C14.4994 1.62246 14.4818 1.58007 14.4506 1.54882C14.4193 1.51756 14.3769 1.5 14.3327 1.5H13.5481C11.9759 1.50009 10.463 2.10054 9.31874 3.17867ZM4.33341 14C3.52741 14.806 1.73274 14.9633 1.17141 14.9933C1.14939 14.9947 1.12733 14.9915 1.10666 14.9838C1.08598 14.9761 1.06716 14.9641 1.05141 14.9487C1.03596 14.9329 1.02401 14.9141 1.01631 14.8934C1.00862 14.8727 1.00536 14.8507 1.00674 14.8287C1.03674 14.2673 1.19407 12.4727 2.00007 11.6667C2.60007 11.0667 3.73341 11.0667 4.33341 11.6667C4.93341 12.2667 4.93341 13.4 4.33341 14ZM3.93874 8.27467L5.44674 6.01133C5.60007 5.78067 5.76007 5.55467 5.92474 5.33333H3.37741C3.34869 5.33335 3.32047 5.34079 3.29547 5.35511L3.27407 5.36667C3.08914 5.47667 2.92836 5.6215 2.80096 5.79258L1.59074 7.39733L3.34941 7.76267L3.93874 8.27467Z" fill="#62E2DA"/></g><defs><clipPath id="clip0_1_1767"><rect width="16" height="16" fill="white"/></clipPath></defs></svg>`;
}

function svgChipProducts(): string {
  return `<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M1.45455 2.18182C1.45455 1.78182 1.78182 1.45455 2.18182 1.45455H3.63636V0H2.18182C0.974545 0 0 0.974545 0 2.18182V3.63636H1.45455V2.18182ZM1.45455 13.8182V12.3636H0V13.8182C0 15.0255 0.974545 16 2.18182 16H3.63636V14.5455H2.18182C1.78182 14.5455 1.45455 14.2182 1.45455 13.8182ZM13.8182 0H12.3636V1.45455H13.8182C14.2182 1.45455 14.5455 1.78182 14.5455 2.18182V3.63636H16V2.18182C16 0.974545 15.0255 0 13.8182 0ZM14.5455 13.8182C14.5455 14.2182 14.2182 14.5455 13.8182 14.5455H12.3636V16H13.8182C15.0255 16 16 15.0255 16 13.8182V12.3636H14.5455V13.8182ZM13.0909 10.0873V5.91273C13.0909 5.38909 12.8145 4.90909 12.3636 4.65455L8.72727 2.56C8.50182 2.42909 8.25455 2.36364 8 2.36364C7.74545 2.36364 7.49818 2.42909 7.27273 2.56L3.63636 4.64727C3.18545 4.90909 2.90909 5.38909 2.90909 5.91273V10.0873C2.90909 10.6109 3.18545 11.0909 3.63636 11.3455L7.27273 13.44C7.49818 13.5709 7.74545 13.6364 8 13.6364C8.25455 13.6364 8.50182 13.5709 8.72727 13.44L12.3636 11.3455C12.8145 11.0909 13.0909 10.6109 13.0909 10.0873ZM7.27273 11.76L4.36364 10.0873V6.72L7.27273 8.41455V11.76ZM8 7.15636L5.12 5.47636L8 3.81818L10.88 5.47636L8 7.15636ZM11.6364 10.0873L8.72727 11.76V8.41455L11.6364 6.72V10.0873Z" fill="#62E2DA"/></svg>`;
}

const chipIcons = [svgChipHowTo, svgChipStatus, svgChipProducts];

/* ──────────────────────────────────────────────────────────────
   LiaraChatWidget Class
   ────────────────────────────────────────────────────────────── */

class LiaraChatWidget {
  private options: WidgetOptions;
  private container: HTMLElement;
  private shadow: ShadowRoot;
  private isOpen: boolean = false;
  private isFullscreen: boolean = false;
  private conversationId: string | null = null;
  private messages: MessageState[] = [];
  private streamClient = new ChatStreamClient();
  private fontBaseUrl = "";
  private t: I18nStrings;
  private hostContext: Record<string, any> = {};

  constructor(options: WidgetOptions) {
    this.options = {
      apiUrl: "http://localhost:8000",
      lang: "fa",
      position: "bottom-right",
      accent: "#28c1f5",
      allowFullscreen: true,
      fullscreen: false,
      ...options,
    };
    this.isFullscreen = Boolean(this.options.allowFullscreen && this.options.fullscreen);
    this.t = getTranslations(this.options.lang);

    // Detect font base URL from the script element
    const currentScript = document.currentScript as HTMLScriptElement | null;
    if (currentScript?.src) {
      try {
        const scriptUrl = new URL(currentScript.src);
        this.fontBaseUrl = scriptUrl.href.replace(/\/[^\/]*$/, "/");
      } catch {
        this.fontBaseUrl = "";
      }
    }

    this.container = document.createElement("div");
    this.container.id = "liara-chat-widget-root";
    this.shadow = this.container.attachShadow({ mode: "open" });
    document.body.appendChild(this.container);

    this.initContextFromPage();
    this.render();
  }

  /* ── Context ── */

  private initContextFromPage() {
    this.hostContext = {
      page_url: window.location.href,
      title: document.title,
    };
  }

  public setContext(context: Record<string, any>) {
    this.hostContext = { ...this.hostContext, ...context };
  }

  /* ── Open / Close / Toggle ── */

  public open() {
    this.isOpen = true;
    const panel = this.shadow.querySelector(".liara-panel");
    if (panel) {
      panel.classList.add("open");
      panel.classList.toggle("fullscreen", this.isFullscreen);
    }
    const input = this.shadow.querySelector<HTMLInputElement>(".liara-input");
    if (input) input.focus();
  }

  public close() {
    this.isOpen = false;
    const panel = this.shadow.querySelector(".liara-panel");
    if (panel) panel.classList.remove("open");
  }

  public toggle() {
    if (this.isOpen) this.close();
    else this.open();
  }

  /* ── Fullscreen ── */

  private toggleFullscreen() {
    if (!this.options.allowFullscreen) return;
    this.isFullscreen = !this.isFullscreen;
    const panel = this.shadow.querySelector(".liara-panel");
    if (panel) panel.classList.toggle("fullscreen", this.isFullscreen);
    this.updateFullscreenButton();
  }

  private updateFullscreenButton() {
    const button = this.shadow.querySelector<HTMLButtonElement>(".liara-fullscreen-btn");
    if (!button) return;
    button.title = this.isFullscreen ? this.t.exitFullscreen : this.t.enterFullscreen;
    button.setAttribute("aria-label", button.title);
    button.innerHTML = this.isFullscreen
      ? `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M16.4978 3.26621C17.3422 3.25421 20.1387 2.67328 20.7316 3.26621C21.3245 3.85913 20.7436 6.65559 20.7316 7.5M20.5038 3.49097L13.5 10.4961" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M3.26621 16.5001C3.25421 17.3445 2.67328 20.141 3.26621 20.7339C3.85913 21.3268 6.65559 20.7459 7.5 20.7339M10.5019 13.4976L3.49809 20.5027" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`
      : svgExpand();
  }

  /* ── Reset ── */

  public reset() {
    this.streamClient.abort();
    this.conversationId = null;
    this.messages = [];
    if (this.options.greeting) {
      this.messages.push({
        role: "assistant",
        content: this.options.greeting,
      });
    }
    this.updateMessagesDOM();
    this.renderQuickActions();
    const suggestionsContainer = this.shadow.querySelector(".liara-suggestions");
    if (suggestionsContainer) suggestionsContainer.innerHTML = "";
  }

  /* ── Public Ask ── */

  public async ask(text: string) {
    this.open();
    await this.sendMessage(text);
  }

  /* ── Suggestions (after response) ── */

  private renderSuggestions(suggestions: string[]) {
    const container = this.shadow.querySelector(".liara-suggestions");
    if (!container) return;
    container.innerHTML = "";

    suggestions.forEach((text) => {
      const btn = document.createElement("button");
      btn.className = "liara-chip-btn";
      btn.textContent = text;
      btn.onclick = () => {
        container.innerHTML = "";
        this.sendMessage(text);
      };
      container.appendChild(btn);
    });
  }

  /* ── Quick Actions (initial greeting grid) ── */

  private renderQuickActions() {
    const container = this.shadow.querySelector(".liara-quick-actions");
    if (!container) return;
    container.innerHTML = "";

    const actions = this.t.quickActions;
    if (!actions || actions.length === 0) return;

    const title = document.createElement("div");
    title.className = "liara-quick-actions-title";
    title.textContent = this.t.quickActionsTitle;
    container.appendChild(title);

    const grid = document.createElement("div");
    grid.className = "liara-quick-actions-grid";

    if (actions[0]) {
      const row1 = document.createElement("div");
      row1.className = "liara-quick-actions-row";
      row1.appendChild(this.createChip(actions[0], 0));
      grid.appendChild(row1);
    }

    const remaining = actions.slice(1);
    if (remaining.length > 0) {
      const row2 = document.createElement("div");
      row2.className = "liara-quick-actions-row multi";
      remaining.forEach((action, i) => {
        const chip = this.createChip(action, i + 1);
        row2.appendChild(chip);
      });
      grid.appendChild(row2);
    }

    container.appendChild(grid);
  }

  private createChip(text: string, index: number): HTMLButtonElement {
    const btn = document.createElement("button");
    btn.className = "liara-chip-btn";

    const textSpan = document.createElement("span");
    textSpan.textContent = text;

    const iconSpan = document.createElement("span");
    iconSpan.className = "liara-chip-icon";
    const iconFn = chipIcons[index % chipIcons.length];
    iconSpan.innerHTML = iconFn();

    btn.appendChild(textSpan);
    btn.appendChild(iconSpan);

    btn.onclick = () => {
      const qa = this.shadow.querySelector(".liara-quick-actions");
      if (qa) (qa as HTMLElement).style.display = "none";
      this.sendMessage(text);
    };

    return btn;
  }

  /* ── Timestamp Helper ── */

  private formatTime(): string {
    const now = new Date();
    const hours = now.getHours().toString().padStart(2, "0");
    const minutes = now.getMinutes().toString().padStart(2, "0");
    return `${hours}:${minutes}`;
  }

  /* ── Main Render ── */

  private render() {
    const isLeft = this.options.position === "bottom-left";
    const positionStyle = isLeft ? "left: 24px; right: auto;" : "right: 24px; left: auto;";

    this.shadow.innerHTML = `
      <style>
        @font-face {
          font-family: 'Yekan Bakh';
          src: url('${this.fontBaseUrl}fonts/YekanBakh-Regular.woff2') format('woff2');
          font-weight: 400;
          font-style: normal;
          font-display: swap;
        }
        @font-face {
          font-family: 'Yekan Bakh';
          src: url('${this.fontBaseUrl}fonts/YekanBakh-SemiBold.woff2') format('woff2');
          font-weight: 600;
          font-style: normal;
          font-display: swap;
        }
        @font-face {
          font-family: 'Yekan Bakh';
          src: url('${this.fontBaseUrl}fonts/YekanBakh-Bold.woff2') format('woff2');
          font-weight: 700;
          font-style: normal;
          font-display: swap;
        }
        ${styles}
        :host {
          --primary-color: ${this.options.accent || "#28c1f5"};
          font-family: 'Yekan Bakh', sans-serif;
        }
        .liara-launcher, .liara-panel {
          ${positionStyle}
        }
      </style>

      <!-- Launcher Button -->
      <button class="liara-launcher" aria-label="Open Liara Chat">
        <svg viewBox="0 0 24 24">
          <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/>
        </svg>
      </button>

      <!-- Chat Panel -->
      <div class="liara-panel">

        <!-- Header -->
        <div class="liara-header">
          <div class="liara-header-top">
            <div class="liara-header-actions">
              <button class="liara-btn-icon liara-minimize-btn" title="Minimize" aria-label="Minimize">
                ${svgMinimize()}
              </button>
              ${this.options.allowFullscreen ? `<button class="liara-btn-icon liara-fullscreen-btn" type="button" title="${this.t.enterFullscreen}" aria-label="${this.t.enterFullscreen}"></button>` : ""}
            </div>
            <div class="liara-header-brand">
              <span class="liara-header-title">${this.t.title}</span>
              <div class="liara-header-logo">
                ${svgLiaraLogo()}
              </div>
            </div>
          </div>
          <div class="liara-header-subtitle">${this.t.subtitle}</div>
        </div>

        <!-- Messages -->
        <div class="liara-messages"></div>

        <!-- Quick Actions (shown on initial load) -->
        <div class="liara-quick-actions"></div>

        <!-- Suggestions (shown after bot response) -->
        <div class="liara-suggestions"></div>

        <!-- Input Footer -->
        <div class="liara-footer">
          <button class="liara-send-btn" aria-label="Send">
            ${svgSend()}
          </button>
          <div class="liara-input-wrapper">
            <input type="text" class="liara-input" placeholder="${this.t.inputPlaceholder}" />
          </div>
        </div>
      </div>
    `;

    /* ── Bind Event Listeners ── */

    this.shadow.querySelector(".liara-launcher")?.addEventListener("click", () => this.toggle());
    this.shadow.querySelector(".liara-minimize-btn")?.addEventListener("click", () => this.close());
    this.shadow.querySelector(".liara-fullscreen-btn")?.addEventListener("click", () => this.toggleFullscreen());
    this.updateFullscreenButton();

    /* ── Offline/Online Detection ── */
    const offlineMsgId = "liara-offline-msg";
    const updateOnlineStatus = () => {
      const messagesContainer = this.shadow.querySelector(".liara-messages");
      if (!messagesContainer) return;
      const existing = messagesContainer.querySelector(`#${offlineMsgId}`);
      if (!navigator.onLine) {
        if (!existing) {
          const bannerEl = document.createElement("div");
          bannerEl.id = offlineMsgId;
          bannerEl.className = "liara-offline-banner";
          bannerEl.innerHTML = `<p>${this.t.offlineMessage}</p>`;
          messagesContainer.appendChild(bannerEl);
          bannerEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
      } else {
        if (existing) existing.remove();
      }
    };
    window.addEventListener("online", updateOnlineStatus);
    window.addEventListener("offline", updateOnlineStatus);
    updateOnlineStatus();

    const input = this.shadow.querySelector<HTMLInputElement>("input.liara-input")!;
    const sendBtn = this.shadow.querySelector<HTMLButtonElement>("button.liara-send-btn")!;

    const handleSend = () => {
      const val = input.value.trim();
      if (val) {
        input.value = "";
        this.sendMessage(val);
      }
    };

    sendBtn.addEventListener("click", handleSend);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") handleSend();
    });

    // Initial greeting
    if (this.options.greeting) {
      this.messages.push({
        role: "assistant",
        content: this.options.greeting,
      });
      this.updateMessagesDOM();
      this.renderQuickActions();

      // Add timestamp to the greeting message
      const messagesContainer = this.shadow.querySelector(".liara-messages");
      if (messagesContainer) {
        const lastMsg = messagesContainer.querySelector(".liara-message.assistant:last-child");
        if (lastMsg) {
          const metaEl = document.createElement("div");
          metaEl.className = "liara-message-meta";
          metaEl.innerHTML = `<span>${this.formatTime()}</span><span class="liara-meta-dot"></span><span>${this.t.title}</span>`;
          lastMsg.appendChild(metaEl);
        }
      }
    }
  }

  /* ── Send Message & Stream ── */

  private async sendMessage(text: string) {
    const messagesContainer = this.shadow.querySelector(".liara-messages")!;

    this.renderSuggestions([]);

    const qa = this.shadow.querySelector(".liara-quick-actions");
    if (qa) (qa as HTMLElement).style.display = "none";

    // 1. Append User Message
    this.messages.push({ role: "user", content: text });
    const userMsgEl = document.createElement("div");
    userMsgEl.className = "liara-message user";
    userMsgEl.innerHTML = `<div class="liara-bubble">${renderMarkdown(text)}</div>`;
    const userMetaEl = document.createElement("div");
    userMetaEl.className = "liara-message-meta";
    userMetaEl.innerHTML = `<span>${this.formatTime()}</span><span class="liara-meta-dot"></span><span>${this.t.you}</span>`;
    userMsgEl.appendChild(userMetaEl);
    messagesContainer.appendChild(userMsgEl);
    userMsgEl.scrollIntoView({ behavior: "smooth", block: "nearest" });

    // 2. Prepare Assistant Message container & stage indicator
    const assistantIndex = this.messages.length;
    this.messages.push({ role: "assistant", content: "" });

    const assistantMsgEl = document.createElement("div");
    assistantMsgEl.className = "liara-message assistant";

    const assistantBubble = document.createElement("div");
    assistantBubble.className = "liara-bubble";
    assistantMsgEl.appendChild(assistantBubble);

    const stageEl = document.createElement("div");
    stageEl.className = "liara-stage-indicator";
    stageEl.innerHTML = `<div class="liara-spinner"></div><span>${this.t.searchingStage}</span>`;
    assistantMsgEl.appendChild(stageEl);

    messagesContainer.appendChild(assistantMsgEl);

    let assistantContent = "";
    let citationsContainer: HTMLElement | null = null;

    await this.streamClient.streamChat(
      this.options.apiUrl!,
      this.options.siteKey,
      {
        conversation_id: this.conversationId || undefined,
        message: text,
        context: this.hostContext,
        options: { lang: this.options.lang },
      },
      {
        onMeta: (meta) => {
          this.conversationId = meta.conversation_id;
        },
        onStatus: (st) => {
          if (st.stage === "reading") {
            stageEl.innerHTML = `<div class="liara-spinner"></div><span>${this.t.readingStage} (${st.sources || 1})</span>`;
          }
        },
        onToken: (tok) => {
          if (stageEl.parentNode) stageEl.remove();
          assistantContent += tok.text;
          this.messages[assistantIndex].content = assistantContent;
          assistantBubble.innerHTML = renderMarkdown(assistantContent);
        },
        onCitations: (cite) => {
          const items = cite.items || [];
          this.messages[assistantIndex].citations = items;
          if (items.length > 0 && !citationsContainer) {
            citationsContainer = document.createElement("div");
            citationsContainer.className = "liara-citations";

            const seenUrls = new Set<string>();
            items.forEach((c) => {
              if (c.url && !seenUrls.has(c.url)) {
                seenUrls.add(c.url);
                const chip = document.createElement("a");
                chip.className = "liara-citation-chip";
                chip.href = c.url;
                chip.target = "_blank";
                chip.rel = "noopener nofollow";
                chip.innerHTML = `<span>[${c.n}]</span> ${c.title}`;
                citationsContainer!.appendChild(chip);
              }
            });
            if (citationsContainer.childNodes.length > 0) {
              assistantMsgEl.appendChild(citationsContainer);
            }
          }
        },
        onActions: (acts) => {
          this.renderSuggestions(acts.suggestions || []);
        },
        onDone: () => {
          if (stageEl.parentNode) stageEl.remove();
          const metaEl = document.createElement("div");
          metaEl.className = "liara-message-meta";
          metaEl.innerHTML = `<span>${this.formatTime()}</span><span class="liara-meta-dot"></span><span>${this.t.title}</span>`;
          assistantMsgEl.appendChild(metaEl);
        },
        onError: (err) => {
          if (stageEl.parentNode) stageEl.remove();
          if (err.code === "network_error") {
            assistantBubble.innerHTML = `
              <div class="liara-offline-banner">
                <p>${this.t.offlineMessage}</p>
              </div>`;
          } else {
            assistantBubble.innerHTML = `
              <div class="liara-error-card">
                <p class="liara-error-card-title">${this.t.errorTitle}</p>
                <p class="liara-error-card-desc">${this.t.errorDesc}</p>
                <div class="liara-error-card-actions">
                  <button class="liara-error-card-retry">${this.t.retry}</button>
                </div>
              </div>`;
            const retryBtn = assistantBubble.querySelector(".liara-error-card-retry")!;
            retryBtn.addEventListener("click", () => {
              this.messages.splice(assistantIndex, 2);
              this.sendMessage(text);
            });
          }
        },
      }
    );
  }

  /* ── Update Messages DOM ── */

  private updateMessagesDOM() {
    const messagesContainer = this.shadow.querySelector(".liara-messages");
    if (!messagesContainer) return;

    messagesContainer.innerHTML = "";

    this.messages.forEach((msg) => {
      const msgEl = document.createElement("div");
      msgEl.className = `liara-message ${msg.role}`;

      const bubbleEl = document.createElement("div");
      bubbleEl.className = "liara-bubble";
      bubbleEl.innerHTML = renderMarkdown(msg.content);
      msgEl.appendChild(bubbleEl);

      if (msg.role === "user") {
        const metaEl = document.createElement("div");
        metaEl.className = "liara-message-meta";
        metaEl.innerHTML = `<span>${this.formatTime()}</span><span class="liara-meta-dot"></span><span>${this.t.you}</span>`;
        msgEl.appendChild(metaEl);
      }

      if (msg.citations && msg.citations.length > 0) {
        const citeContainer = document.createElement("div");
        citeContainer.className = "liara-citations";
        const seen = new Set<string>();

        msg.citations.forEach((c) => {
          if (c.url && !seen.has(c.url)) {
            seen.add(c.url);
            const chip = document.createElement("a");
            chip.className = "liara-citation-chip";
            chip.href = c.url;
            chip.target = "_blank";
            chip.rel = "noopener nofollow";
            chip.innerHTML = `<span>[${c.n}]</span> ${c.title}`;
            citeContainer.appendChild(chip);
          }
        });

        if (citeContainer.childNodes.length > 0) {
          msgEl.appendChild(citeContainer);
        }
      }

      messagesContainer.appendChild(msgEl);
    });
  }
}

/* ── Auto-bootstrap ── */

(function () {
  const currentScript = document.currentScript as HTMLScriptElement;
  if (currentScript) {
    const siteKey = currentScript.getAttribute("data-site-key");
    if (siteKey) {
      const apiUrl = currentScript.getAttribute("data-api-url") || "http://localhost:8000";
      const lang = currentScript.getAttribute("data-lang") || "fa";
      const position = (currentScript.getAttribute("data-position") as any) || "bottom-right";
      const accent = currentScript.getAttribute("data-accent") || "#28c1f5";
      const greeting = currentScript.getAttribute("data-greeting") || undefined;
      const allowFullscreen = currentScript.getAttribute("data-allow-fullscreen") !== "false";
      const fullscreen = currentScript.getAttribute("data-fullscreen") === "true";

      const widget = new LiaraChatWidget({
        siteKey,
        apiUrl,
        lang,
        position,
        accent,
        greeting,
        allowFullscreen,
        fullscreen,
      });

      (window as any).LiaraChat = widget;
    }
  }
})();

export { LiaraChatWidget };
