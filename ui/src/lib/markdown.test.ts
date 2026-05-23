import { describe, it, expect } from "vitest";
import { renderMarkdown } from "./markdown";

describe("renderMarkdown sanitiser", () => {
  it("escapes <script> tags", () => {
    const out = renderMarkdown("# hi\n\n<script>alert(1)</script>\n");
    expect(out).not.toContain("<script>");
    expect(out).toContain("&lt;script&gt;");
  });

  it("strips javascript: hrefs from links", () => {
    const out = renderMarkdown("[click](javascript:alert(1))");
    expect(out).toContain('href="#"');
    expect(out).not.toContain("javascript:");
  });

  it("adds rel=noopener noreferrer to links", () => {
    const out = renderMarkdown("[ok](https://example.com)");
    expect(out).toContain('rel="noopener noreferrer"');
    expect(out).toContain('target="_blank"');
  });

  it("placeholders images instead of fetching them", () => {
    const out = renderMarkdown("![alt](https://remote.example.com/x.png)");
    expect(out).not.toContain("<img");
    expect(out).toContain("[image:");
  });
});
