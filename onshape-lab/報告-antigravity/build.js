const fs = require('fs'), path = require('path');
const L = require('./lib');
const { docx } = L;
const { Document, Packer, Paragraph, TextRun, Header, Footer, PageNumber,
        AlignmentType, BorderStyle, convertInchesToTwip, Table, TableRow, TableCell,
        WidthType, ImageRun, PageBreak } = docx;
const { body } = require('./md2docx');
const { buildTOC } = require('./toc');

const M = { margin: { top: convertInchesToTwip(1), bottom: convertInchesToTwip(1),
                      left: convertInchesToTwip(1.1), right: convertInchesToTwip(1.1) } };
const hdr = new Header({ children: [new Paragraph({
  children: [new TextRun({ text: 'Antigravity ｜ AI 操作 Onshape MCP 完整教學報告',
    size: 18, color: L.C_MUTED, font: L.font(L.F_BODY) })],
  alignment: AlignmentType.RIGHT,
  border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: L.C_RULE, space: 4 } },
  spacing: { after: 120 } })] });
const ftr = new Footer({ children: [new Paragraph({
  children: [new TextRun({ children: [PageNumber.CURRENT], size: 20, color: L.C_MUTED, font: L.font(L.F_BODY) })],
  alignment: AlignmentType.CENTER })] });
const blank = new Header({ children: [new Paragraph({ children: [new TextRun('')] })] });

const heroBuf = fs.readFileSync(path.join(__dirname, 'figs', 'fig1_1_arch.png'));
const cell = (children, fill) => new TableCell({
  children, shading: fill ? { fill } : undefined,
  margins: { top: 160, bottom: 160, left: 220, right: 220 },
  width: { size: 9000, type: WidthType.DXA } });
const hero = new Table({
  columnWidths: [9000], width: { size: 9000, type: WidthType.DXA },
  borders: {
    top: { style: BorderStyle.SINGLE, size: 8, color: 'C2681B' },
    bottom: { style: BorderStyle.SINGLE, size: 8, color: 'C2681B' },
    left: { style: BorderStyle.SINGLE, size: 8, color: 'C2681B' },
    right: { style: BorderStyle.SINGLE, size: 8, color: 'C2681B' },
    insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: 'C2681B' } },
  rows: [
    new TableRow({ children: [cell([new Paragraph({
      children: [new ImageRun({ data: heroBuf, transformation: { width: 560, height: 198 } })],
      alignment: AlignmentType.CENTER })])] }),
    new TableRow({ children: [cell([
      new Paragraph({ children: [new TextRun({ text: '八章 · 八圖 · 由 AI 代理親自操作後撰寫',
        bold: true, size: 26, color: 'C2681B', font: L.font(L.F_HEAD) })],
        alignment: AlignmentType.CENTER, spacing: { after: 60 } }),
      new Paragraph({ children: [new TextRun({ text: '第一手經驗與查證所得全程分別標示',
        size: 21, color: L.C_MUTED, font: L.font(L.F_BODY) })],
        alignment: AlignmentType.CENTER })], 'FBF1E6')] }),
  ] });

const cl = (t, size, color, bold, after) => new Paragraph({
  children: [new TextRun({ text: t, size, color, bold: !!bold, font: L.font(L.F_BODY) })],
  alignment: AlignmentType.CENTER, spacing: { after: after || 80 } });

const cover = [
  new Paragraph({ children: [new TextRun('')], spacing: { after: 520 } }),
  new Paragraph({ children: [new TextRun({ text: 'AI 代理操作 Onshape 完整教學',
    bold: true, size: 50, color: L.C_INK, font: L.font(L.F_HEAD) })],
    alignment: AlignmentType.CENTER, spacing: { after: 140 } }),
  new Paragraph({ children: [new TextRun({ text: 'FeatureScript MCP 從零開始的實作手冊',
    size: 29, color: L.C_MUTED, font: L.font(L.F_BODY) })],
    alignment: AlignmentType.CENTER, spacing: { after: 380 } }),
  hero,
  new Paragraph({ children: [new TextRun('')], spacing: { after: 1150 } }),
  cl('Antigravity（Gemini 3.1 Pro）', 26, L.C_INK, true, 60),
  cl('親自操作 Onshape FeatureScript MCP 後撰寫', 21, L.C_MUTED, false, 60),
  cl('委託：趙翰宇　·　2026 年 8 月 29 日', 21, L.C_MUTED, false, 60),
  cl('組版：Claude Code', 20, L.C_MUTED, false, 0),
];

const doc = new Document({
  creator: 'Antigravity', title: 'AI 代理操作 Onshape 完整教學：FeatureScript MCP 從零開始的實作手冊',
  styles: L.styles, numbering: L.numbering,
  sections: [
    { properties: { page: M }, headers: { default: blank },
      footers: { default: new Footer({ children: [new Paragraph({ children: [new TextRun('')] })] }) },
      children: cover },
    { properties: { page: { ...M, pageNumbers: { start: 1 } } },
      headers: { default: hdr }, footers: { default: ftr },
      children: [...buildTOC(), ...body()] },
  ] });

const out = path.join(__dirname, process.env.FONT_MODE === 'pdf'
  ? '_pdfsrc.docx' : 'AI代理操作Onshape完整教學.docx');
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(out, b);
  console.log('✓ ' + path.basename(out) + '  (' + (b.length/1024).toFixed(0) + ' KB)'); });
