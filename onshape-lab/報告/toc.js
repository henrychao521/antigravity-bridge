// 手動目錄（LibreOffice 不會自動更新 TOC 欄位，故自製以確保 PDF 亦有目錄）
const fs = require('fs');
const path = require('path');
const L = require('./lib');
const { docx } = L;
const { Paragraph, TextRun, AlignmentType, TabStopType, TabStopPosition, PageBreak, BorderStyle } = docx;

// key 用於在 PDF 純文字中定位該章節所在頁
const ITEMS = [
  { lv: 1, label: '壹、緣起：為什麼需要兩個代理', key: '壹、緣起' },
  { lv: 2, label: '一、成本結構決定分工', key: '一、成本結構決定分工' },
  { lv: 1, label: '貳、環境建置：從訂閱到可程式化呼叫', key: '貳、環境建置' },
  { lv: 2, label: '一、訂閱與權限落差', key: '一、訂閱與權限落差' },
  { lv: 2, label: '二、為什麼要自己實作 MCP 用戶端', key: '二、為什麼要自己實作' },
  { lv: 1, label: '參、成本結構：文件沒寫的真實單價', key: '參、成本結構' },
  { lv: 1, label: '肆、實戰歷程：二十輪除錯', key: '肆、實戰歷程' },
  { lv: 2, label: '二、第一階段：讓它編譯得過', key: '二、第一階段' },
  { lv: 2, label: '三、第二階段：幾何驗證', key: '三、第二階段' },
  { lv: 1, label: '伍、失敗路徑', key: '伍、失敗路徑' },
  { lv: 2, label: '失敗路徑一：相信模型對標準函式庫的記憶', key: '失敗路徑一' },
  { lv: 2, label: '失敗路徑二：把工具的「空輸出」當成「沒有錯誤」', key: '失敗路徑二' },
  { lv: 2, label: '失敗路徑三：用最貴的工具做除錯迴圈', key: '失敗路徑三' },
  { lv: 2, label: '失敗路徑四：以為官方工具會留下模型', key: '失敗路徑四' },
  { lv: 1, label: '陸、驗證設計：如何避免自己騙自己', key: '陸、驗證設計' },
  { lv: 2, label: '一、缺陷一：沒有產物可看', key: '一、缺陷一' },
  { lv: 2, label: '二、缺陷二：數字只有單一來源', key: '二、缺陷二' },
  { lv: 2, label: '三、缺陷三：讓另一個代理複述自己的結論', key: '三、缺陷三' },
  { lv: 1, label: '柒、驗收結果與真實模型', key: '柒、驗收結果與真實模型' },
  { lv: 1, label: '捌、Antigravity 的獨立複驗', key: '捌、Antigravity 的獨立複驗' },
  { lv: 2, label: '一、它得到的數字', key: '一、它得到的數字' },
  { lv: 2, label: '二、它踩到的坑（與我不同）', key: '二、它踩到的坑' },
  { lv: 2, label: '三、它自陳學到的事實', key: '三、它自陳學到的事實' },
  { lv: 1, label: '玖、給後來者的操作準則', key: '玖、給後來者的操作準則' },
  { lv: 1, label: '附錄　smartBoss 完整原始碼', key: '附錄' },
];

function buildTOC() {
  const pageMapPath = path.join(__dirname, process.env.TOC_FILE || 'toc-pages.json');
  const pages = fs.existsSync(pageMapPath)
    ? JSON.parse(fs.readFileSync(pageMapPath, 'utf8')) : {};

  const out = [
    new Paragraph({
      children: [new TextRun({ text: '目　次', bold: true, size: 36, color: L.C_ACCENT, font: L.font(L.F_HEAD) })],
      alignment: AlignmentType.CENTER,
      spacing: { before: 0, after: 360 },
      pageBreakBefore: true,
    }),
  ];

  const items = process.env.CLEAN === '1'
    ? ITEMS.filter((it) => it.key !== '本版修訂說明')
    : ITEMS;
  items.forEach((it) => {
    const pg = pages[it.key] != null ? String(pages[it.key]) : '　';
    out.push(new Paragraph({
      children: [
        new TextRun({
          text: it.label,
          bold: it.lv === 1,
          size: it.lv === 1 ? 24 : 21,
          color: it.lv === 1 ? L.C_ACCENT : L.C_INK,
          font: L.font(L.F_BODY),
        }),
        new TextRun({ text: '\t' + pg, size: it.lv === 1 ? 24 : 21, color: L.C_MUTED, font: L.font(L.F_BODY) }),
      ],
      tabStops: [{ type: TabStopType.RIGHT, position: 9000, leader: 'dot' }],
      indent: { left: it.lv === 1 ? 0 : 400 },
      spacing: { before: it.lv === 1 ? 130 : 30, after: 30, line: 300 },
    }));
  });

  out.push(new Paragraph({ children: [new PageBreak()] }));
  return out;
}

module.exports = { buildTOC, ITEMS };
