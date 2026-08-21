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

class LiaraChatWidget {
  private options: WidgetOptions;
  private container: HTMLElement;
  private shadow: ShadowRoot;
  private isOpen: boolean = false;
  private isFullscreen: boolean = false;
  private conversationId: string | null = null;
  private messages: MessageState[] = [];
  private streamClient = new ChatStreamClient();
  private t: I18nStrings;
  private hostContext: Record<string, any> = {};

  constructor(options: WidgetOptions) {
    this.options = {
      apiUrl: "http://localhost:8000",
      lang: "fa",
      position: "bottom-right",
      accent: "#0f9d58",
      allowFullscreen: true,
      fullscreen: false,
      ...options,
    };
    this.isFullscreen = Boolean(this.options.allowFullscreen && this.options.fullscreen);
    this.t = getTranslations(this.options.lang);

    // Create custom host container
    this.container = document.createElement("div");
    this.container.id = "liara-chat-widget-root";
    this.shadow = this.container.attachShadow({ mode: "open" });
    document.body.appendChild(this.container);

    this.initContextFromPage();
    this.render();
  }

  private initContextFromPage() {
    this.hostContext = {
      page_url: window.location.href,
      title: document.title,
    };
  }

  public setContext(context: Record<string, any>) {
    this.hostContext = { ...this.hostContext, ...context };
  }

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
      ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm0-14v5h5V8h-3V5h-2z"/></svg>'
      : '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/></svg>';
  }

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
    const suggestionsContainer = this.shadow.querySelector(".liara-suggestions");
    if (suggestionsContainer) suggestionsContainer.innerHTML = "";
  }

  public async ask(text: string) {
    this.open();
    await this.sendMessage(text);
  }

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

  private render() {
    const isLeft = this.options.position === "bottom-left";
    const positionStyle = isLeft ? "left: 24px; right: auto;" : "right: 24px; left: auto;";

    this.shadow.innerHTML = `
      <style>
        ${styles}
        :host {
          --primary-color: ${this.options.accent || "#0f9d58"};
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
        <div class="liara-header">
          <div class="liara-header-info">
            <div>
              <div class="liara-header-title">${this.t.title}</div>
              <div class="liara-header-status">● ${this.t.online}</div>
            </div>
          </div>
          <div class="liara-header-actions">
            <button class="liara-btn-icon liara-reset-btn" title="Reset Chat">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>
            </button>
            ${this.options.allowFullscreen ? '<button class="liara-btn-icon liara-fullscreen-btn" type="button"></button>' : ""}
            <button class="liara-btn-icon liara-close-btn" title="Close">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
            </button>
          </div>
        </div>

        <div class="liara-messages"></div>

        <div class="liara-suggestions"></div>

        <div class="liara-footer">
          <input type="text" class="liara-input" placeholder="${this.t.inputPlaceholder}" />
          <button class="liara-send-btn" aria-label="Send">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
          </button>
        </div>
      </div>
    `;

    // Bind event listeners
    this.shadow.querySelector(".liara-launcher")?.addEventListener("click", () => this.toggle());
    this.shadow.querySelector(".liara-close-btn")?.addEventListener("click", () => this.close());
    this.shadow.querySelector(".liara-reset-btn")?.addEventListener("click", () => this.reset());
    this.shadow.querySelector(".liara-fullscreen-btn")?.addEventListener("click", () => this.toggleFullscreen());
    this.updateFullscreenButton();

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

    // Add initial greeting if configured
    if (this.options.greeting) {
      this.messages.push({
        role: "assistant",
        content: this.options.greeting,
      });
      this.updateMessagesDOM();
    }
  }

  private async sendMessage(text: string) {
    const messagesContainer = this.shadow.querySelector(".liara-messages")!;

    // Suggestions belong to the previous answer. Clear them before rendering
    // the next turn so stale chips cannot be selected for a new question.
    this.renderSuggestions([]);

    // 1. Append User Message
    this.messages.push({ role: "user", content: text });
    const userMsgEl = document.createElement("div");
    userMsgEl.className = "liara-message user";
    userMsgEl.innerHTML = `<div class="liara-bubble">${renderMarkdown(text)}</div>`;
    messagesContainer.appendChild(userMsgEl);

    // Scroll once so the user question is in view
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
          // In-place bubble update without scroll jump
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
          // Always replace the chips, including an empty list from cached,
          // clarified, or refused responses.
          this.renderSuggestions(acts.suggestions || []);
        },
        onDone: () => {
          if (stageEl.parentNode) stageEl.remove();
        },
        onError: (err) => {
          if (stageEl.parentNode) stageEl.remove();
          assistantContent = `خطا: ${err.message || "ارتباط با سرور برقرار نشد."}`;
          this.messages[assistantIndex].content = assistantContent;
          assistantBubble.innerHTML = renderMarkdown(assistantContent);
        },
      }
    );
  }

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

// Auto-bootstrap
(function () {
  const currentScript = document.currentScript as HTMLScriptElement;
  if (currentScript) {
    const siteKey = currentScript.getAttribute("data-site-key");
    if (siteKey) {
      const apiUrl = currentScript.getAttribute("data-api-url") || "http://localhost:8000";
      const lang = currentScript.getAttribute("data-lang") || "fa";
      const position = (currentScript.getAttribute("data-position") as any) || "bottom-right";
      const accent = currentScript.getAttribute("data-accent") || "#0f9d58";
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
