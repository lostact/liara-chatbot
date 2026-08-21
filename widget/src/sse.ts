export interface SSEHandlers {
  onMeta?: (data: { conversation_id: string; message_id: number; trace_id: string }) => void;
  onStatus?: (data: { stage: string; detail?: string; sources?: number }) => void;
  onToken?: (data: { text: string }) => void;
  onCitations?: (data: { items: Array<{ n: number; title: string; url: string; heading_path?: string[] }> }) => void;
  onActions?: (data: { suggestions?: string[]; links?: Array<{ label: string; url: string }>; clarify?: any }) => void;
  onDone?: (data: { confidence: string; cost_usd?: number }) => void;
  onError?: (error: { code: string; message: string }) => void;
}

export class ChatStreamClient {
  private abortController: AbortController | null = null;

  async streamChat(
    apiBaseUrl: string,
    siteKey: string,
    payload: {
      conversation_id?: string;
      message: string;
      context?: any;
      options?: any;
    },
    handlers: SSEHandlers
  ): Promise<void> {
    this.abort();
    this.abortController = new AbortController();

    try {
      const response = await fetch(`${apiBaseUrl.replace(/\/$/, "")}/v1/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Site-Key": siteKey,
        },
        body: JSON.stringify(payload),
        signal: this.abortController.signal,
      });

      if (!response.ok) {
        let errData = { code: `http_${response.status}`, message: response.statusText };
        try {
          const body = await response.json();
          if (body.detail) errData = body.detail;
        } catch (_) {}
        handlers.onError?.(errData);
        return;
      }

      if (!response.body) {
        handlers.onError?.({ code: "no_body", message: "No response body received" });
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const rawEvent of events) {
          if (!rawEvent.trim()) continue;

          let eventType = "message";
          let eventData = "";

          const lines = rawEvent.split("\n");
          for (const line of lines) {
            if (line.startsWith("event: ")) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              eventData = line.slice(6).trim();
            }
          }

          if (eventData) {
            try {
              const parsed = JSON.parse(eventData);
              switch (eventType) {
                case "meta":
                  handlers.onMeta?.(parsed);
                  break;
                case "status":
                  handlers.onStatus?.(parsed);
                  break;
                case "token":
                  handlers.onToken?.(parsed);
                  break;
                case "citations":
                  handlers.onCitations?.(parsed);
                  break;
                case "actions":
                  handlers.onActions?.(parsed);
                  break;
                case "done":
                  handlers.onDone?.(parsed);
                  break;
                case "error":
                  handlers.onError?.(parsed);
                  break;
              }
            } catch (e) {
              console.warn("Could not parse SSE JSON:", eventData);
            }
          }
        }
      }
    } catch (err: any) {
      if (err.name === "AbortError") {
        console.log("Chat stream aborted by user.");
      } else {
        handlers.onError?.({ code: "network_error", message: err.message || "Network error" });
      }
    } finally {
      this.abortController = null;
    }
  }

  abort() {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }
}
