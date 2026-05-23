/**
 * Tiny safe Markdown renderer.
 *
 * Intentionally no remote dependency. Supports headings, paragraphs,
 * inline code, fenced code blocks, lists, and links. Everything else falls
 * through as plain text. Hostile inputs (`<script>`, `javascript:` URLs,
 * inline event handlers) are stripped — we never inject raw user HTML.
 */

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function sanitiseHref(href: string): string {
  const trimmed = href.trim();
  if (/^javascript:/i.test(trimmed)) return "#";
  if (/^data:/i.test(trimmed)) return "#";
  return trimmed;
}

export function renderMarkdown(src: string): string {
  if (!src) return "";

  const lines = src.split(/\r?\n/);
  let html = "";
  let inCode = false;
  let inList = false;

  for (const raw of lines) {
    if (raw.startsWith("```")) {
      if (inCode) {
        html += "</code></pre>";
        inCode = false;
      } else {
        if (inList) {
          html += "</ul>";
          inList = false;
        }
        html += "<pre><code>";
        inCode = true;
      }
      continue;
    }
    if (inCode) {
      html += escapeHtml(raw) + "\n";
      continue;
    }

    if (raw.startsWith("# ")) {
      if (inList) {
        html += "</ul>";
        inList = false;
      }
      html += `<h1>${inline(escapeHtml(raw.slice(2)))}</h1>`;
      continue;
    }
    if (raw.startsWith("## ")) {
      if (inList) {
        html += "</ul>";
        inList = false;
      }
      html += `<h2>${inline(escapeHtml(raw.slice(3)))}</h2>`;
      continue;
    }
    if (raw.startsWith("- ") || raw.startsWith("* ")) {
      if (!inList) {
        html += "<ul>";
        inList = true;
      }
      html += `<li>${inline(escapeHtml(raw.slice(2)))}</li>`;
      continue;
    }
    if (raw.trim() === "") {
      if (inList) {
        html += "</ul>";
        inList = false;
      }
      continue;
    }

    html += `<p>${inline(escapeHtml(raw))}</p>`;
  }

  if (inCode) html += "</code></pre>";
  if (inList) html += "</ul>";
  return html;
}

function inline(s: string): string {
  // Strip any HTML tags that slipped through escapeHtml (defensive: should
  // be impossible since we already escaped them).
  s = s.replace(/(?:<[^>]+>)/g, "");
  // Inline code
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
  // Image FIRST (so it doesn't get eaten by the link rule): ![alt](url)
  s = s.replace(
    /!\[([^\]]*)\]\(([^)]+)\)/g,
    (_match, alt: string, url: string) => {
      const safe = sanitiseHref(url);
      return `<span class="rounded bg-slate-100 px-1 text-xs text-slate-600">[image: ${alt || safe}]</span>`;
    },
  );
  // Links: [text](url) — sanitise href.
  s = s.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    (_match, text: string, url: string) => {
      const href = sanitiseHref(url);
      return `<a href="${href}" target="_blank" rel="noopener noreferrer">${text}</a>`;
    },
  );
  return s;
}
