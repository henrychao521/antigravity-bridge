// 圖片元件：自動依 PNG 實際尺寸等比縮放到版面寬度
const fs = require('fs');
const path = require('path');
const L = require('./lib');
const { docx } = L;
const { Paragraph, ImageRun, AlignmentType } = docx;

const MAX_W = 605;   // 8.5in - 2.2in 邊界 ≈ 6.3in @96dpi

function pngSize(buf) {           // PNG 的寬高在 IHDR，位元組 16..24
  return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) };
}

function Fig(file, caption, maxWidth = MAX_W) {
  const buf = fs.readFileSync(path.join(__dirname, 'figs', file));
  const { w, h } = pngSize(buf);
  const width = Math.min(maxWidth, w);
  const height = Math.round(h * (width / w));
  const out = [new Paragraph({
    children: [new ImageRun({ data: buf, transformation: { width, height } })],
    alignment: AlignmentType.CENTER,
    spacing: { before: 240, after: 80 },
  })];
  if (caption) out.push(L.Caption(caption));
  return out;
}

module.exports = { Fig };
