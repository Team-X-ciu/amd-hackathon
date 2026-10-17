// Image, mask and heatmap files. Names are generated here (inspection id + suffix), never taken
// from the upload, so a client-supplied filename can't pick a path.
import { mkdir, rm, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";

// npm run dev runs from backend/ (./uploads is git-ignored); docker compose sets /app/uploads.
const UPLOAD_DIR = resolve(process.env.UPLOAD_DIR ?? "uploads");

export type ImageType = "png" | "jpeg";

/** PNG or JPEG from the file's first bytes, or null for anything else. */
export function sniffImage(buf: Buffer): ImageType | null {
  if (buf.length >= 8 && buf.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))) return "png";
  if (buf.length >= 3 && buf[0] === 0xff && buf[1] === 0xd8 && buf[2] === 0xff) return "jpeg";
  return null;
}

/** Writes `name` under the upload dir and returns its path relative to it (what the DB stores). */
export async function saveFile(name: string, data: Buffer): Promise<string> {
  await mkdir(UPLOAD_DIR, { recursive: true });
  await writeFile(join(UPLOAD_DIR, name), data);
  return name;
}

export async function removeFiles(names: string[]): Promise<void> {
  await Promise.all(names.map((n) => rm(join(UPLOAD_DIR, n), { force: true })));
}
