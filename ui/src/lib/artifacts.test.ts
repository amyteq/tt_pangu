import { describe, it, expect } from "vitest";
import {
  canPreview,
  capCsv,
  isBinaryPath,
  MAX_PREVIEW_BYTES,
  CSV_PREVIEW_ROWS,
} from "./artifacts";

describe("artifact previews", () => {
  it("blocks binary extensions from preview", () => {
    for (const ext of [".pkl", ".pt", ".h5", ".bin", ".so"]) {
      expect(isBinaryPath(`foo${ext}`)).toBe(true);
      expect(canPreview(`foo${ext}`, 100).preview).toBe(false);
    }
  });

  it("blocks > 1 MB files", () => {
    expect(canPreview("foo.txt", MAX_PREVIEW_BYTES + 1).preview).toBe(false);
    expect(canPreview("foo.txt", MAX_PREVIEW_BYTES - 1).preview).toBe(true);
  });

  it("caps CSV at 100 rows", () => {
    const rows = Array.from({ length: 200 }, (_, i) => `row${i}`);
    const capped = capCsv(rows);
    expect(capped.length).toBe(CSV_PREVIEW_ROWS);
    expect(capped[0]).toBe("row0");
  });
});
