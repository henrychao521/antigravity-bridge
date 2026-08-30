// 封面、壹、貳
const L = require('./lib');
const { docx, P, H1, H2, H3, LI, Box, T, Caption, Cite } = L;
const { Paragraph, TextRun, AlignmentType, PageBreak, Table, TableRow, TableCell,
        WidthType, BorderStyle, ImageRun } = docx;
const { Fig } = require('./imgs');
const fs = require('fs'), path = require('path');

// ── 封面：主視覺與摘要橫幅包在同一個外框表格內，成為單一物件 ──
const heroBuf = fs.readFileSync(path.join(__dirname, 'figs', 'fig1_arch.png'));
const cell = (children, shading) => new TableCell({
  children, shading: shading ? { fill: shading } : undefined,
  margins: { top: 160, bottom: 160, left: 220, right: 220 },
  width: { size: 9000, type: WidthType.DXA },
});

const hero = new Table({
  columnWidths: [9000],
  width: { size: 9000, type: WidthType.DXA },
  borders: {
    top: { style: BorderStyle.SINGLE, size: 8, color: L.C_ACCENT },
    bottom: { style: BorderStyle.SINGLE, size: 8, color: L.C_ACCENT },
    left: { style: BorderStyle.SINGLE, size: 8, color: L.C_ACCENT },
    right: { style: BorderStyle.SINGLE, size: 8, color: L.C_ACCENT },
    insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: L.C_ACCENT },
  },
  rows: [
    new TableRow({ children: [cell([new Paragraph({
      children: [new ImageRun({ data: heroBuf, transformation: { width: 560, height: 280 } })],
      alignment: AlignmentType.CENTER })])] }),
    new TableRow({ children: [cell([
      new Paragraph({
        children: [new TextRun({ text: '三通道交叉驗證　·　202 次 API 呼叫　·　模型可線上打開',
          bold: true, size: 26, color: L.C_ACCENT, font: L.font(L.F_HEAD) })],
        alignment: AlignmentType.CENTER, spacing: { after: 60 } }),
      new Paragraph({
        children: [new TextRun({ text: '兩個代理各自獨立操作，以不同建構方式得到相同數字',
          size: 21, color: L.C_MUTED, font: L.font(L.F_BODY) })],
        alignment: AlignmentType.CENTER }),
    ], 'EDF3FA')] }),
  ],
});

const coverLine = (t, size, color, bold, after) => new Paragraph({
  children: [new TextRun({ text: t, size, color, bold: !!bold, font: L.font(L.F_BODY) })],
  alignment: AlignmentType.CENTER, spacing: { after: after || 80 },
});

const cover = [
  new Paragraph({ children: [new TextRun('')], spacing: { after: 520 } }),
  new Paragraph({
    children: [new TextRun({ text: '用兩個代理式 AI 操作 Onshape',
      bold: true, size: 52, color: L.C_INK, font: L.font(L.F_HEAD) })],
    alignment: AlignmentType.CENTER, spacing: { after: 140 } }),
  new Paragraph({
    children: [new TextRun({ text: 'FeatureScript MCP 實戰歷程與成本結構',
      size: 30, color: L.C_MUTED, font: L.font(L.F_BODY) })],
    alignment: AlignmentType.CENTER, spacing: { after: 380 } }),
  hero,
  new Paragraph({ children: [new TextRun('')], spacing: { after: 1150 } }),
  coverLine('趙翰宇', 26, L.C_INK, true, 60),
  coverLine('翰林出版社生活科技教科書作者', 21, L.C_MUTED, false, 60),
  coverLine('2026 年 8 月 29 日', 21, L.C_MUTED, false, 60),
  coverLine('github.com/henrychao521/antigravity-bridge', 20, L.C_ACCENT, false, 0),
];

// ── 壹 ──────────────────────────────────────────────────────
const ch1 = [
  new Paragraph({ children: [new PageBreak()] }),
  H1('壹、緣起：為什麼需要兩個代理'),

  P('2026 年 8 月 13 日，PTC 透過 Onshape Labs 推出官方 FeatureScript MCP Server，讓大型語言模型能以自然語言產生、測試並除錯 FeatureScript 自訂特徵。這是 CAD 領域少見的官方級 AI 介面——它不是讓 AI 直接畫幾何，而是讓 AI 寫出「產生幾何的程式」。'),

  P('本報告記錄一次完整的實作：讓兩個代理式 AI 分工協作，從零接上這個 MCP 伺服器，並完成一個具體的自訂特徵。過程中最有價值的不是成功的部分，而是兩個關鍵病因的定位方式——它們都不是問模型問出來的。'),

  H2('一、成本結構決定分工'),

  P('分工的理由不是能力差異，而是成本結構。Onshape 的 API 額度以「年」計算，本次使用的免費方案一年只有 2,500 次呼叫，用完即停止服務，不能加購。相對地，Antigravity 走的是 Google AI Pro 訂閱額度，以五小時與每週兩個窗口滾動重置，且該帳號的額度長期閒置。'),

  ...Box('兩種額度的本質差異', [
    [{ t: 'Onshape：年度 2,500 次，' }, { t: '用完硬停', b: true },
     { t: '（overageEnabled 為 false），週期跨越十二個月。每一次呼叫都是不可再生資源。' }],
    [{ t: 'Antigravity：五小時窗口滾動重置。' },
     { t: '燒掉才是賺到——不用它就過期作廢。', b: true }],
  ]),

  P('因此分工原則很清楚：凡是不需要真的碰到 Onshape 的工作，一律交給 Antigravity；只有必須送進 Onshape 驗證的那一版，才動用寶貴的 API 次數。'),

  ...Fig('fig1_arch.png', '圖 1-1　兩個代理的分工與成本邊界。左側所有工作都不消耗 Onshape 額度。'),

  H2('二、本報告的閱讀方式'),

  P('第參章給出各工具的實際成本——這些數字官方文件完全沒有記載，只能實測。第肆章是二十輪除錯的完整歷程。第伍章獨立列出「失敗路徑」，記錄那些整條走不通、最後掉頭重來的嘗試；這一章比成功步驟更值得讀。第柒章把全部經驗壓縮成七條可直接照做的準則。'),
];
module.exports = { cover, ch1 };
