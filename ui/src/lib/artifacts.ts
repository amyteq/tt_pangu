/** Helpers shared by Artifacts + ArtifactDetail pages. */

export const MAX_PREVIEW_BYTES = 1024 * 1024; // 1 MB
export const CSV_PREVIEW_ROWS = 100;

const BINARY_EXTENSIONS = [".pkl", ".pt", ".h5", ".bin", ".so"];

const TEXT_PREFIXES = [
  "text/",
  "application/json",
  "application/x-yaml",
  "application/javascript",
];

export function isBinaryPath(path: string): boolean {
  const lower = path.toLowerCase();
  return BINARY_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

export function canPreview(path: string, size: number | null | undefined): {
  preview: boolean;
  reason?: string;
} {
  if (isBinaryPath(path)) {
    return { preview: false, reason: "binary extension" };
  }
  if (typeof size === "number" && size > MAX_PREVIEW_BYTES) {
    return { preview: false, reason: ">1 MB" };
  }
  return { preview: true };
}

export function looksLikeText(contentType: string | null | undefined): boolean {
  if (!contentType) return false;
  const ct = contentType.toLowerCase();
  return TEXT_PREFIXES.some((p) => ct.startsWith(p));
}

export function capCsv(rows: string[]): string[] {
  return rows.slice(0, CSV_PREVIEW_ROWS);
}
