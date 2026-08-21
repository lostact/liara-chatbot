export function escapeHtml(text: string): string {
  return text
    .split("&").join("&" + "amp;")
    .split("<").join("&" + "lt;")
    .split(">").join("&" + "gt;")
    .split(String.fromCharCode(34)).join("&" + "quot;")
    .split(String.fromCharCode(39)).join("&#" + "039;");
}

function normalizeCodeBlock(code: string, language?: string): string {
  const normalized = code.replace(/\r\n?/g, "\n").trim();
  const normalizedLanguage = (language || "").toLowerCase();

  // LLMs often return valid JSON with inconsistent whitespace. Pretty-print
  // JSON blocks so nested objects are readable and consistently indented.
  if (normalizedLanguage === "json" || /^[\[{]/.test(normalized)) {
    try {
      return JSON.stringify(JSON.parse(normalized), null, 2);
    } catch {
      // Fall through for JSON-like snippets that are incomplete while the
      // response is still streaming or contain comments/trailing commas.
    }
  }

  // Remove indentation introduced uniformly by the Markdown container while
  // preserving meaningful relative indentation inside ordinary code blocks.
  const lines = normalized.split("\n");
  const indents = lines
    .filter((line) => line.trim())
    .map((line) => line.match(/^[ \t]*/)?.[0].length || 0);
  const commonIndent = indents.length ? Math.min(...indents) : 0;
  return lines.map((line) => line.slice(Math.min(commonIndent, line.length))).join("\n");
}

export function renderMarkdown(markdownText: string): string {
  if (!markdownText) return "";

  const codeBlocks: string[] = [];
  let text = markdownText.replace(/```([a-zA-Z0-9_\-\+]+)?\n([\s\S]*?)```/g, (_, lang, code) => {
    const langStr = lang ? ` data-lang="${escapeHtml(lang)}"` : "";
    const cleanCode = escapeHtml(normalizeCodeBlock(code, lang));
    const placeholder = `__CODE_BLOCK_${codeBlocks.length}__`;
    codeBlocks.push(`<pre><code${langStr}>${cleanCode}</code></pre>`);
    return placeholder;
  });

  text = escapeHtml(text);

  text = text.replace(/^### (.*$)/gim, "<h4>$1</h4>");
  text = text.replace(/^## (.*$)/gim, "<h3>$1</h3>");
  text = text.replace(/^# (.*$)/gim, "<h2>$1</h2>");

  text = text.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/\*(.*?)\*/g, "<em>$1</em>");

  text = text.replace(/`([^`]+)`/g, "<code>$1</code>");

  text = text.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    "<a href=\"$2\" target=\"_blank\" rel=\"noopener nofollow\">$1</a>"
  );

  text = text.replace(/\[(\d+)\]/g, "<sup class=\"liara-cite-ref\" data-cite=\"$1\">[$1]</sup>");

  text = text.replace(/^\s*-\s+(.*)$/gim, "<li>$1</li>");
  text = text.replace(/(<li>.*<\/li>)/s, "<ul>$1</ul>");

  text = text.replace(/\n\n+/g, "<br><br>");
  text = text.replace(/\n/g, "<br>");

  codeBlocks.forEach((block, idx) => {
    text = text.replace(`__CODE_BLOCK_${idx}__`, block);
  });

  return text;
}
