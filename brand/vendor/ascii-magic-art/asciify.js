/*
 * asciify.js · Omar's ASCII block look (27 Nov 2026), built on ascii-magic-art's glyph engine (glyphs.js, MIT).
 *
 * The look: a photo's own colours drawn as a grid of glyphs, two layers merged with "lighten"
 * (the Grainrad recipe from reference R21): a DETAIL layer of characters chosen by brightness
 * from an ink-sorted ramp, and a BLOCKS layer of lower-block bars (1/8 to 8/8 of the cell high).
 * The bars sit on each row's baseline, so every row reads as a horizontal stripe with a dark gap
 * above it: the asciiart.club / R21 texture. Characters are drawn centred in fixed cells, so any
 * face works (no monospace needed); bars are drawn as rectangles, so no block glyphs are needed.
 *
 *   import { sampleImage, drawAscii } from "VENDOR/ascii-magic-art/asciify.js";
 *   const grid = sampleImage(img, { cols: 160, rows: 90, crop, zoom });   // once per source
 *   drawAscii(ctx, grid, { x, y, w, h, t, ...options });                  // every frame
 *
 * drawAscii options (all optional):
 *   look      "detailed" (default), "ascii", "numbers", "binary", "letters" ... any glyphs.js LOOKS key
 *   chars     your own characters instead of a look (sorted light to dark by ink for you)
 *   layers    "both" (default), "detail", "blocks"
 *   colour    "original" (default), "mono" (one ink), "duotone" ([dark, light] hex pair)
 *   ink       hex for mono, default "#FBFAF6"
 *   font      CSS font for the detail layer, default 500 weight Familjen Grotesk at 0.92 x cell height
 *   gap       share of each row left dark between stripes, default 0.22
 *   gamma     brightness curve, default 0.9; contrast 0..1 extra, default 0.15
 *   resolve   0..1: coarse to fine (R20); below 1 the grid is drawn at a coarser pitch
 *   dissolve  0..1: share of cells gone, chosen by a fixed noise so it is deterministic in t
 *   dissolveFrom "random" (default), "right", "edges"
 *   blockShade 0..1 brightness of the bars, default 0.72; detailLift brightness of the glyphs, default 1.3
 *   invert    true for ink on paper: dark parts of the source get the big glyphs (print look), layers merge with "darken"
 *   colour    also "solid": glyphs in one ink colour; bars in that ink mixed toward `paper` by `blockTint` (default 0.6)
 *   blend     override how the detail layer merges (e.g. "source-over" to keep true colours over a coloured ground)
 *   bg        fill colour drawn first, or null for transparent
 */
import { ramp, LOOKS } from "./glyphs.js";

const hash = (x, y, n = 0) => {
  let h = (x * 374761393 + y * 668265263 + n * 2147483647) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
};

/** Average colour and brightness per cell. crop: {x, y, w, h} in source pixels; zoom > 1 pushes in on the centre. */
export function sampleImage(img, { cols = 160, rows = 90, crop = null, zoom = 1 } = {}) {
  const sw = img.naturalWidth || img.width, sh = img.naturalHeight || img.height;
  let c = crop || { x: 0, y: 0, w: sw, h: sh };
  if (zoom !== 1) { const w = c.w / zoom, h = c.h / zoom; c = { x: c.x + (c.w - w) / 2, y: c.y + (c.h - h) / 2, w, h }; }
  const cv = document.createElement("canvas"); cv.width = cols; cv.height = rows;
  const g = cv.getContext("2d", { willReadFrequently: true });
  g.imageSmoothingQuality = "high";
  g.drawImage(img, c.x, c.y, c.w, c.h, 0, 0, cols, rows);
  const d = g.getImageData(0, 0, cols, rows).data, cells = new Array(cols * rows);
  for (let i = 0; i < cols * rows; i++) {
    const r = d[i * 4], gr = d[i * 4 + 1], b = d[i * 4 + 2];
    cells[i] = { r, g: gr, b, l: (0.2126 * r + 0.7152 * gr + 0.0722 * b) / 255 };
  }
  return { cols, rows, cells };
}

function coarsen(grid, f) {             // average blocks of f x f cells (resolve < 1)
  if (f <= 1) return grid;
  const cols = Math.ceil(grid.cols / f), rows = Math.ceil(grid.rows / f), cells = new Array(cols * rows);
  for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++) {
    let r = 0, g = 0, b = 0, l = 0, n = 0;
    for (let j = 0; j < f; j++) for (let i = 0; i < f; i++) {
      const sx = x * f + i, sy = y * f + j;
      if (sx >= grid.cols || sy >= grid.rows) continue;
      const c = grid.cells[sy * grid.cols + sx]; r += c.r; g += c.g; b += c.b; l += c.l; n++;
    }
    cells[y * cols + x] = { r: r / n, g: g / n, b: b / n, l: l / n };
  }
  return { cols, rows, cells };
}

const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));

export function drawAscii(ctx, grid0, o = {}) {
  const { x = 0, y = 0, w = ctx.canvas.width, h = ctx.canvas.height } = o;
  const f = o.resolve != null && o.resolve < 1 ? Math.max(1, Math.round(1 + (1 - o.resolve) * 7)) : 1;
  const grid = coarsen(grid0, f);
  const cw = w / grid.cols, ch = h / grid.rows, gap = o.gap ?? 0.22;
  const chars = ramp(o.chars || (LOOKS[o.look || "dense"] || LOOKS.dense).chars || LOOKS.dense.chars);
  const gamma = o.gamma ?? 0.9, contrast = o.contrast ?? 0.15, layers = o.layers || "both";
  const mono = o.colour === "mono" ? hex(o.ink || "#FBFAF6") : null;
  const duo = o.colour === "duotone" ? (o.duotone || ["#111111", "#FBFAF6"]).map(hex) : null;
  const dis = o.dissolve || 0, from = o.dissolveFrom || "random";
  if (o.bg) { ctx.fillStyle = o.bg; ctx.fillRect(x, y, w, h); }
  ctx.save();
  ctx.font = o.font || `500 ${Math.max(6, ch * 0.92)}px "Familjen Grotesk", sans-serif`;
  ctx.textAlign = "center"; ctx.textBaseline = "alphabetic";
  const draw = (pass) => {
    for (let j = 0; j < grid.rows; j++) for (let i = 0; i < grid.cols; i++) {
      const c = grid.cells[j * grid.cols + i];
      let l = Math.pow(Math.min(1, Math.max(0, o.invert ? 1 - c.l : c.l)), gamma);
      l = Math.min(1, Math.max(0, (l - 0.5) * (1 + contrast) + 0.5));
      if (dis > 0) {
        const n = from === "right" ? i / grid.cols * 0.7 + hash(i, j) * 0.3
          : from === "edges" ? (1 - Math.min(i, grid.cols - 1 - i, j, grid.rows - 1 - j) / (Math.min(grid.cols, grid.rows) / 2)) * 0.7 + hash(i, j) * 0.3
          : hash(i, j);
        if (n > 1 - dis) continue;
      }
      if (l < 0.04) continue;
      let r = c.r, g = c.g, b = c.b;
      if (o.colour === "solid") { const ink = hex(o.ink || "#111111"), pap = hex(o.paper || "#FBFAF6"), tn = pass === "blocks" ? (o.blockTint ?? 0.6) : 0; [r, g, b] = ink.map((v, k) => v * (1 - tn) + pap[k] * tn); }
      else if (mono) [r, g, b] = mono.map((v) => v * Math.max(0.25, l));
      else if (duo) [r, g, b] = duo[0].map((v, k) => v + (duo[1][k] - v) * l);
      const k2 = o.colour === "solid" ? 1 : pass === "blocks" ? (o.blockShade ?? 0.72) : (o.detailLift ?? 1.3);   // bars sit darker, glyphs lighter, so "lighten" shows the characters
      ctx.fillStyle = `rgb(${Math.min(255, r * k2) | 0},${Math.min(255, g * k2) | 0},${Math.min(255, b * k2) | 0})`;
      const px = x + i * cw, py = y + j * ch;
      if (pass === "blocks") {
        const lv = Math.max(1, Math.round(l * 8)) / 8, bh = ch * (1 - gap) * lv;
        ctx.fillRect(px, py + ch * (1 - gap) - bh, cw + 0.6, bh);   // a bar on the row's baseline, touching its neighbours so the row reads as one stripe
      } else {
        const k = Math.min(chars.length - 1, Math.max(1, Math.round(l * (chars.length - 1))));
        ctx.fillText(chars[k], px + cw / 2, py + ch * (1 - gap));
      }
    }
  };
  if (layers !== "detail") draw("blocks");
  if (layers !== "blocks") { ctx.globalCompositeOperation = o.blend || (layers === "both" ? (o.invert ? "darken" : "lighten") : "source-over"); draw("detail"); }
  ctx.restore();
}
