// 報告產生共用元件：中文排版設定與版面元素
const docx = require('docx');
const {
  Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, PageBreak, LevelFormat, convertInchesToTwip,
} = docx;

// 字型策略：
//   word 模式 → 微軟正黑體（台灣 Word 使用者標配，供編輯用）
//   pdf  模式 → Arial Unicode MS（本機 LibreOffice 唯一能正確嵌入之繁中字型）
// 兩者皆為無襯線黑體，兩版視覺一致。
const PDF_MODE = process.env.FONT_MODE === 'pdf';
const F_BODY = PDF_MODE ? 'Arial Unicode MS' : '微軟正黑體';
const F_HEAD = PDF_MODE ? 'Arial Unicode MS' : '微軟正黑體';
const F_MONO = PDF_MODE ? 'Arial Unicode MS' : 'Consolas';

const C_INK = '1A1A1A';
const C_ACCENT = '1D4E89';   // 深藍：標題與強調
const C_MUTED = '595959';
const C_RULE = 'BFBFBF';
const C_BAD = 'B3372E';      // 勘誤紅
const C_OK = '1E7F4F';       // 確認綠
const C_SHADE = 'EDF1F5';    // 表頭底色
const C_SHADE2 = 'F7F9FB';

const font = (name) => ({ name, eastAsia: name, ascii: name, hAnsi: name });

/**
 * 審閱版（CLEAN=1）：略過所有「初版錯了什麼」的修訂註記，
 * 只呈現最終內容，供同仁審閱課程規劃本身。
 * 一般版則保留修訂痕跡，作為查證與版本管理的紀錄。
 */
const CLEAN = process.env.CLEAN === '1';

/** 包裝修訂註記：審閱版會整段略過 */
function Rev(...items) {
  return CLEAN ? [] : items.flat();
}

/** 依版本擇一：Pick(給審閱版的內容, 給修訂版的內容) */
function Pick(cleanVer, revVer) {
  return CLEAN ? cleanVer : revVer;
}

/** 內文段落。text 可為字串或 [{t, b, i, c, mono}] 陣列 */
function P(text, opts = {}) {
  const {
    size = 24, spacing = { before: 60, after: 120, line: 340 },
    align = AlignmentType.BOTH, indent, color = C_INK, keepNext = false,
  } = opts;
  const runs = (Array.isArray(text) ? text : [{ t: text }]).map((r) => new TextRun({
    text: r.t,
    bold: !!r.b,
    italics: !!r.i,
    color: r.c || color,
    size: r.size || size,
    font: font(r.mono ? F_MONO : (r.head ? F_HEAD : F_BODY)),
  }));
  return new Paragraph({ children: runs, spacing, alignment: align, indent, keepNext });
}

/** 章標題（壹、貳…）另起新頁 */
function H1(text, opts = {}) {
  return new Paragraph({
    children: [new TextRun({ text, bold: true, size: 34, color: C_ACCENT, font: font(F_HEAD) })],
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 240, after: 200 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: C_ACCENT, space: 6 } },
    pageBreakBefore: opts.newPage !== false,
  });
}

function H2(text) {
  return new Paragraph({
    children: [new TextRun({ text, bold: true, size: 28, color: C_ACCENT, font: font(F_HEAD) })],
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 300, after: 140 },
    keepNext: true,
  });
}

function H3(text) {
  return new Paragraph({
    children: [new TextRun({ text, bold: true, size: 25, color: C_INK, font: font(F_HEAD) })],
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 220, after: 100 },
    keepNext: true,
  });
}

/** 項目符號 */
function LI(text, opts = {}) {
  const runs = (Array.isArray(text) ? text : [{ t: text }]).map((r) => new TextRun({
    text: r.t, bold: !!r.b, italics: !!r.i, color: r.c || C_INK, size: 24,
    font: font(r.mono ? F_MONO : F_BODY),
  }));
  return new Paragraph({
    children: runs,
    numbering: { reference: opts.numbered ? 'num-list' : 'bullet-list', level: opts.level || 0 },
    spacing: { before: 40, after: 80, line: 320 },
    alignment: AlignmentType.BOTH,
  });
}

/** 引用書目區塊（左側色條、淺底） */
function Cite(lines) {
  const arr = Array.isArray(lines) ? lines : [lines];
  return arr.map((line, i) => new Paragraph({
    children: (Array.isArray(line) ? line : [{ t: line }]).map((r) => new TextRun({
      text: r.t, bold: !!r.b, italics: !!r.i, size: 21,
      color: r.c || (r.meta ? C_MUTED : C_INK),
      font: font(r.mono ? F_MONO : F_BODY),
    })),
    spacing: { before: i === 0 ? 100 : 0, after: i === arr.length - 1 ? 140 : 40, line: 300 },
    indent: { left: 340 },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: C_ACCENT, space: 10 } },
    shading: { type: ShadingType.CLEAR, fill: C_SHADE2 },
    alignment: AlignmentType.LEFT,
  }));
}

/** 提示方塊 */
function Box(title, body, tone = 'info') {
  const bar = tone === 'warn' ? '96610A' : tone === 'bad' ? C_BAD : C_ACCENT;
  const fill = tone === 'warn' ? 'FDF6E7' : tone === 'bad' ? 'FBEEEC' : 'EDF3FA';
  const out = [new Paragraph({
    children: [new TextRun({ text: title, bold: true, size: 23, color: bar, font: font(F_HEAD) })],
    spacing: { before: 160, after: 40, line: 300 },
    indent: { left: 280, right: 160 },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: bar, space: 10 } },
    shading: { type: ShadingType.CLEAR, fill },
  })];
  const bodyArr = Array.isArray(body) && Array.isArray(body[0]) ? body : [body];
  bodyArr.forEach((b, i) => out.push(new Paragraph({
    children: (Array.isArray(b) ? b : [{ t: b }]).map((r) => new TextRun({
      text: r.t, bold: !!r.b, italics: !!r.i, size: 22, color: r.c || C_INK,
      font: font(r.mono ? F_MONO : F_BODY),
    })),
    spacing: { before: 0, after: i === bodyArr.length - 1 ? 160 : 60, line: 300 },
    indent: { left: 280, right: 160 },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: bar, space: 10 } },
    shading: { type: ShadingType.CLEAR, fill },
    alignment: AlignmentType.BOTH,
  })));
  return out;
}

/**
 * 表格。rows[0] 為表頭。widths 為各欄 DXA 寬度（總和需等於表寬）
 * 每格內容可為字串或 [{t,b,c}]
 */
function T(rows, widths, opts = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  const mk = (cell, isHead, colIdx) => {
    const runs = (Array.isArray(cell) ? cell : [{ t: String(cell) }]).map((r) => new TextRun({
      text: r.t,
      bold: isHead || !!r.b,
      italics: !!r.i,
      size: r.size || (isHead ? 21 : 21),
      color: r.c || (isHead ? 'FFFFFF' : C_INK),
      font: font(r.mono ? F_MONO : (isHead ? F_HEAD : F_BODY)),
    }));
    return new TableCell({
      width: { size: widths[colIdx], type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill: isHead ? C_ACCENT : 'FFFFFF' },
      margins: { top: 90, bottom: 90, left: 120, right: 120 },
      children: [new Paragraph({
        children: runs,
        spacing: { before: 20, after: 20, line: 280 },
        alignment: opts.center && !isHead ? AlignmentType.CENTER : AlignmentType.LEFT,
      })],
    });
  };
  return new Table({
    columnWidths: widths,
    width: { size: total, type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 6, color: C_RULE },
      bottom: { style: BorderStyle.SINGLE, size: 6, color: C_RULE },
      left: { style: BorderStyle.SINGLE, size: 6, color: C_RULE },
      right: { style: BorderStyle.SINGLE, size: 6, color: C_RULE },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: C_RULE },
      insideVertical: { style: BorderStyle.SINGLE, size: 4, color: C_RULE },
    },
    rows: rows.map((r, i) => new TableRow({
      children: r.map((c, j) => mk(c, i === 0, j)),
      tableHeader: i === 0,
      cantSplit: true,
    })),
  });
}

/** 表格說明文字 */
function Caption(text) {
  return new Paragraph({
    children: [new TextRun({ text, size: 20, color: C_MUTED, font: font(F_BODY) })],
    spacing: { before: 60, after: 200, line: 280 },
  });
}

function Spacer(after = 160) {
  return new Paragraph({ children: [new TextRun('')], spacing: { after } });
}

const numbering = {
  config: [
    {
      reference: 'bullet-list',
      levels: [
        { level: 0, format: LevelFormat.BULLET, text: '●', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 420, hanging: 240 } },
                   run: { size: 16, color: C_ACCENT } } },
        { level: 1, format: LevelFormat.BULLET, text: '○', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 800, hanging: 240 } },
                   run: { size: 16, color: C_MUTED } } },
      ],
    },
    {
      reference: 'num-list',
      levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 440, hanging: 260 } },
                   run: { bold: true, color: C_ACCENT } } },
        { level: 1, format: LevelFormat.LOWER_LETTER, text: '(%2)', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 820, hanging: 300 } } } },
      ],
    },
  ],
};

const styles = {
  default: {
    document: { run: { font: font(F_BODY), size: 24, color: C_INK }, paragraph: { spacing: { line: 340 } } },
  },
  paragraphStyles: [
    { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
      run: { font: font(F_HEAD), size: 34, bold: true, color: C_ACCENT } },
    { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
      run: { font: font(F_HEAD), size: 28, bold: true, color: C_ACCENT } },
    { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
      run: { font: font(F_HEAD), size: 25, bold: true, color: C_INK } },
  ],
};

module.exports = {
  docx, P, H1, H2, H3, LI, Cite, Box, T, Caption, Spacer, numbering, styles, font,
  CLEAN, Rev, Pick,
  F_BODY, F_HEAD, F_MONO, C_INK, C_ACCENT, C_MUTED, C_BAD, C_OK, C_SHADE, C_SHADE2, C_RULE,
};
