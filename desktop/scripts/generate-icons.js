/**
 * JARVIS Icon Generator (no dependencies)
 *
 * Procedurally draws a glowing orb icon (dark rounded square + cyan ring + indigo core)
 * and writes:
 *   resources/icon.png   — 256x256 PNG (used by the system tray)
 *   resources/icon.ico   — multi-size ICO with embedded PNGs (used by electron-builder)
 *
 * Also prints a 16x16 PNG as base64 — this is the embedded fallback used in
 * desktop/src/main.ts so the tray icon is never empty.
 *
 * Usage:  node scripts/generate-icons.js
 */

const zlib = require("zlib");
const fs = require("fs");
const path = require("path");

// ─── Minimal PNG encoder ───────────────────────────────────────────────────

const CRC_TABLE = (() => {
  const t = new Int32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c;
  }
  return t;
})();

function crc32(buf) {
  let c = -1;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ -1) >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const typeBuf = Buffer.from(type, "ascii");
  const crcBuf = Buffer.alloc(4);
  crcBuf.writeUInt32BE(crc32(Buffer.concat([typeBuf, data])));
  return Buffer.concat([len, typeBuf, data, crcBuf]);
}

function encodePNG(size, rgba) {
  const sig = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0); // width
  ihdr.writeUInt32BE(size, 4); // height
  ihdr[8] = 8; // bit depth
  ihdr[9] = 6; // color type: RGBA
  const stride = size * 4 + 1;
  const raw = Buffer.alloc(size * stride);
  for (let y = 0; y < size; y++) {
    raw[y * stride] = 0; // filter: none
    rgba.copy(raw, y * stride + 1, y * size * 4, (y + 1) * size * 4);
  }
  const idat = zlib.deflateSync(raw, { level: 9 });
  return Buffer.concat([sig, chunk("IHDR", ihdr), chunk("IDAT", idat), chunk("IEND", Buffer.alloc(0))]);
}

// ─── Icon drawing ──────────────────────────────────────────────────────────

/**
 * Draw the JARVIS orb into an RGBA buffer.
 * Design: rounded-square dark background, glowing cyan ring, indigo core.
 */
function drawIcon(size) {
  const buf = Buffer.alloc(size * size * 4);
  const c = (size - 1) / 2;
  const cornerRadius = size * 0.2;
  const ringR1 = size * 0.34;
  const ringR2 = size * 0.44;
  const coreR = size * 0.17;

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const dx = x - c;
      const dy = y - c;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const i = (y * size + x) * 4;

      // Rounded-rectangle mask
      const hx = Math.max(Math.abs(dx) - (c - cornerRadius), 0);
      const hy = Math.max(Math.abs(dy) - (c - cornerRadius), 0);
      const inRect = hx * hx + hy * hy <= cornerRadius * cornerRadius;

      if (!inRect) {
        buf[i + 3] = 0;
        continue;
      }

      // Vertical gradient background (#0b1026 → #1c1240)
      const t = y / size;
      let r = Math.round(11 + (28 - 11) * t);
      let g = Math.round(16 + (18 - 16) * t);
      let b = Math.round(38 + (64 - 38) * t);

      // Cyan ring (#22d3ee) with soft falloff
      const ringCenter = (ringR1 + ringR2) / 2;
      const ringHalf = (ringR2 - ringR1) / 2;
      const ringT = Math.abs(dist - ringCenter);
      if (ringT < ringHalf) {
        const k = 1 - ringT / ringHalf;
        r = Math.round(r + (34 - r) * k * 0.92);
        g = Math.round(g + (211 - g) * k * 0.92);
        b = Math.round(b + (238 - b) * k * 0.92);
      }

      // Indigo core (#6366f1) with glow
      if (dist < coreR) {
        const k = 1 - dist / coreR;
        r = Math.round(r + (99 - r) * k);
        g = Math.round(g + (102 - g) * k);
        b = Math.round(b + (241 - b) * k);
      }

      buf[i] = r;
      buf[i + 1] = g;
      buf[i + 2] = b;
      buf[i + 3] = 255;
    }
  }
  return buf;
}

// ─── Write files ───────────────────────────────────────────────────────────

const outDir = path.join(__dirname, "..", "resources");
fs.mkdirSync(outDir, { recursive: true });

const sizes = [256, 48, 32, 16];
const images = sizes.map((s) => encodePNG(s, drawIcon(s)));

// icon.png — 256x256 for the tray
fs.writeFileSync(path.join(outDir, "icon.png"), images[0]);

// icon.ico — ICO container with embedded PNG entries (Vista+ format)
const icoHeader = Buffer.alloc(6);
icoHeader.writeUInt16LE(0, 0); // reserved
icoHeader.writeUInt16LE(1, 2); // type: icon
icoHeader.writeUInt16LE(sizes.length, 4); // image count

let offset = 6 + sizes.length * 16;
const entries = [];
for (let idx = 0; idx < sizes.length; idx++) {
  const s = sizes[idx];
  const e = Buffer.alloc(16);
  e[0] = s >= 256 ? 0 : s; // width (0 = 256)
  e[1] = s >= 256 ? 0 : s; // height
  e[2] = 0; // colors
  e[3] = 0; // reserved
  e.writeUInt16LE(1, 4); // planes
  e.writeUInt16LE(32, 6); // bits per pixel
  e.writeUInt32LE(images[idx].length, 8);
  e.writeUInt32LE(offset, 12);
  offset += images[idx].length;
  entries.push(e);
}
fs.writeFileSync(path.join(outDir, "icon.ico"), Buffer.concat([icoHeader, ...entries, ...images]));

// 16x16 base64 — embedded tray fallback for desktop/src/main.ts
const fallback = images[3].toString("base64");
const fallbackFile = path.join(outDir, "tray-fallback.base64.txt");
fs.writeFileSync(fallbackFile, fallback);

console.log("OK — wrote resources/icon.png, resources/icon.ico, resources/tray-fallback.base64.txt");
console.log("FALLBACK_BASE64_BEGIN");
console.log(fallback);
console.log("FALLBACK_BASE64_END");
