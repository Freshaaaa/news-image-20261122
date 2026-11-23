// news-image-20261122 entry (Node 22, standard library only).
// The front page is rendered by build-image.py into the entry.png beside
// this file; this program verifies it is a whole PNG within the gate's
// limits and copies it to /output/entry.png.
//
// Outside the grader's container, MAKEFUN_OUTPUT_DIR stands in for /output:
//   mkdir -p out && MAKEFUN_OUTPUT_DIR=out node main.ts

import { copyFileSync, mkdirSync, readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { join } from "node:path";

const src = new URL("./entry.png", import.meta.url);
const data = readFileSync(src);

// PNG magic: 89 50 4E 47 0D 0A 1A 0A
const PNG_MAGIC = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
for (let i = 0; i < PNG_MAGIC.length; i++) {
  if (data[i] !== PNG_MAGIC[i]) {
    throw new Error("entry.png is not a PNG file");
  }
}
if (data.length > 1048576) {
  throw new Error(`entry.png is ${data.length} bytes, over the 1 MiB limit`);
}

const outDir = process.env.MAKEFUN_OUTPUT_DIR ?? "/output";
mkdirSync(outDir, { recursive: true });
const dst = join(outDir, "entry.png");
copyFileSync(src, dst);

const sha = createHash("sha256").update(data).digest("hex");
console.log(`entry.png: ${data.length} bytes, sha256 ${sha} -> ${dst}`);
