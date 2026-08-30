// 把 Antigravity 產出的 Markdown 轉成 docx 內容元件。
// 對應規則：## → H1、### → H2、``` → 等寬區塊、[圖 X-Y] → 插圖、| → 表格、- → 條列
const fs = require('fs'), path = require('path');
const L = require('./lib');
const { docx, P, H1, H2, LI, T, Caption } = L;
const { Paragraph, TextRun, PageBreak } = docx;
const { Fig } = require('./imgs');

const FIGS = {
  '1-1': ['fig1_1_arch.png', '圖 1-1　AI 驅動 CAD 整合架構圖', 560],
  '2-1': ['fig2_1_oauth.png', '圖 2-1　OAuth 授權與 MCP 初始化流程', 330],
  '3-1': ['fig3_1_tools.png', '圖 3-1　MCP 常用工具的 API 消耗對照', 560],
  '4-1': ['fig4_1_idtype.png', '圖 4-1　兩種測試環境下 id 型別的差異', 560],
  '5-1': ['fig5_1_coords.png', '圖 5-1　幾何基元的空間座標與尺寸標示', 520],
  '5-2': ['fig5_2_boolean.png', '圖 5-2　opBoolean 聯集的錯誤與正確參數結構', 560],
  '6-1': ['fig6_1_units.png', '圖 6-1　ValueWithUnits 單位轉換流程', 560],
  '7-1': ['fig7_1_budget.png', '圖 7-1　各開發階段的 API 額度消耗', 430],
};

const mono = (t) => new Paragraph({
  children: [new TextRun({ text: t || ' ', size: 17, font: L.font(L.F_MONO), color: L.C_INK })],
  spacing: { line: 240, after: 0 },
  shading: { fill: 'F5F6F8' },
});

// 行內標記：**粗體** 與 `等寬`
function runs(text) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push({ t: text.slice(last, m.index) });
    const s = m[0];
    if (s.startsWith('**')) out.push({ t: s.slice(2, -2), b: true });
    else out.push({ t: s.slice(1, -1), mono: true });
    last = m.index + s.length;
  }
  if (last < text.length) out.push({ t: text.slice(last) });
  return out.length ? out : [{ t: text }];
}

function convert(md) {
  const lines = md.split('\n');
  const out = [];
  let i = 0, firstH1 = true, usedFig = new Set();
  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();   // 圍籬與條列可能有縮排

    if (trimmed.startsWith('```')) {                    // 程式碼區塊（容許縮排）
      i++;
      const buf = [];
      while (i < lines.length && !lines[i].trim().startsWith('```')) buf.push(lines[i++]);
      i++;
      out.push(new Paragraph({ children: [new TextRun('')], spacing: { after: 60 } }));
      buf.forEach((b) => out.push(mono(b)));
      out.push(new Paragraph({ children: [new TextRun('')], spacing: { after: 120 } }));
      continue;
    }

    if (trimmed.startsWith('|')) {                          // 表格
      const rows = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        const cells = lines[i].trim().slice(1, -1).split('|').map((c) => c.trim());
        if (!/^[-: ]+$/.test(cells.join(''))) rows.push(cells);
        i++;
      }
      if (rows.length) {
        const n = rows[0].length;
        const w = Math.floor(9600 / n);
        out.push(T(rows, Array(n).fill(w)));
      }
      continue;
    }

    const figMatch = line.match(/^\s*\[圖 ([0-9]+-[0-9]+)\]\s*$/);
    if (figMatch && FIGS[figMatch[1]] && !usedFig.has(figMatch[1])) {
      usedFig.add(figMatch[1]);
      const [f, cap, w] = FIGS[figMatch[1]];
      out.push(...Fig(f, cap, w));
      i++; continue;
    }
    if (figMatch) { i++; continue; }                     // 重複提及則略過

    if (trimmed.startsWith('## ')) {
      if (!firstH1) out.push(new Paragraph({ children: [new PageBreak()] }));
      firstH1 = false;
      out.push(H1(trimmed.slice(3).trim()));
      i++; continue;
    }
    if (trimmed.startsWith('### ')) { out.push(H2(trimmed.slice(4).trim())); i++; continue; }
    if (/^[-*] /.test(trimmed)) { out.push(LI(runs(trimmed.slice(2).trim()))); i++; continue; }
    if (line.startsWith('---')) { i++; continue; }
    if (line.trim() === '') { i++; continue; }

    // 內文段落：把圖號佔位從句中移除（圖已單獨插入）
    out.push(P(runs(trimmed.replace(/\[圖 [0-9]+-[0-9]+\]/g, '上圖').trim())));
    i++;
  }
  return out;
}

module.exports = { convert, body: () => convert(fs.readFileSync(path.join(__dirname, 'all.md'), 'utf8')) };
