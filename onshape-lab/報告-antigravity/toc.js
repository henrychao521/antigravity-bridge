// 手動目錄（LibreOffice 不會自動更新 TOC 欄位，故自製以確保 PDF 亦有目錄）
const fs = require('fs');
const path = require('path');
const L = require('./lib');
const { docx } = L;
const { Paragraph, TextRun, AlignmentType, TabStopType, TabStopPosition, PageBreak, BorderStyle } = docx;

// key 用於在 PDF 純文字中定位該章節所在頁
const ITEMS = [
  { lv: 1, label: '第一章：前言與 Onshape 雲端 CAD 革命', key: '第一章：前言與 Onshap' },
  { lv: 1, label: '第二章：環境準備與認證機制 (App Store 與 OAuth)', key: '第二章：環境準備與認證機制' },
  { lv: 2, label: '2.1 訂閱 Onshape App Store', key: '2.1 訂閱 Onshape' },
  { lv: 2, label: '2.2 獲取 OAuth Client ID 與 Secret', key: '2.2 獲取 OAuth C' },
  { lv: 2, label: '2.3 使用者同意授權 (User Authorization)', key: '2.3 使用者同意授權' },
  { lv: 2, label: '2.4 取得 Access Token', key: '2.4 取得 Access ' },
  { lv: 2, label: '2.5 啟動 MCP 伺服器並進行連線驗證', key: '2.5 啟動 MCP 伺服器' },
  { lv: 1, label: '第三章：Onshape MCP 核心工具集總覽', key: '第三章：Onshape MC' },
  { lv: 2, label: '3.1 探索與檢索：`search_featurescript_documentation`', key: '3.1 探索與檢索：`sea' },
  { lv: 2, label: '3.2 局部邏輯驗證：`test_featurescript`', key: '3.2 局部邏輯驗證：`te' },
  { lv: 2, label: '3.3 真實環境編譯：`test_feature`', key: '3.3 真實環境編譯：`te' },
  { lv: 1, label: '第四章：FeatureScript 基礎觀念與避坑指南', key: '第四章：FeatureScr' },
  { lv: 2, label: '4.1 幾何基元 (Primitives) vs 特徵操作 (Operations) 的命名潛規則', key: '4.1 幾何基元vs 特徵操' },
  { lv: 2, label: '4.2 令人崩潰的 `Id` 型別與測試環境差異', key: '4.2 令人崩潰的 `Id`' },
  { lv: 2, label: '4.3 版本宣告與預設值 (Defaults) 的重要性', key: '4.3 版本宣告與預設值的重' },
  { lv: 1, label: '第五章：實戰演練：從無到有建立與聯集幾何', key: '第五章：實戰演練：從無到有建' },
  { lv: 2, label: '5.1 步驟一：環境配置與特徵骨架 (Boilerplate)', key: '5.1 步驟一：環境配置與特' },
  { lv: 2, label: '5.2 步驟二：精準生成基體 (`fCuboid`)', key: '5.2 步驟二：精準生成基體' },
  { lv: 2, label: '5.3 步驟三：在頂面中央生成定位柱 (`fCylinder`)', key: '5.3 步驟三：在頂面中央生' },
  { lv: 2, label: '5.4 步驟四：布林聯集的災難與重生 (`opBoolean`)', key: '5.4 步驟四：布林聯集的災' },
  { lv: 2, label: '5.5 步驟五：完整可執行的 FeatureScript 特徵程式碼', key: '5.5 步驟五：完整可執行的' },
  { lv: 1, label: '第六章：精準量測：實體體積與單位轉換', key: '第六章：精準量測：實體體積與' },
  { lv: 2, label: '6.1 呼叫 `evVolume` 取得體積', key: '6.1 呼叫 `evVolu' },
  { lv: 2, label: '6.2 單位轉換與 `ValueWithUnits` 陷阱', key: '6.2 單位轉換與 `Val' },
  { lv: 2, label: '6.3 讀者手動數學驗證指南', key: '6.3 讀者手動數學驗證指南' },
  { lv: 1, label: '第七章：API 額度管理與開發策略', key: '第七章：API 額度管理與開' },
  { lv: 2, label: '準則一：文檔先行（低成本、高投報）', key: '準則一：文檔先行（低成本、高' },
  { lv: 2, label: '準則二：沙盒局部驗證（中成本、專注邏輯）', key: '準則二：沙盒局部驗證（中成本' },
  { lv: 2, label: '準則三：最後一哩路的整合測試（高成本、謹慎動用）', key: '準則三：最後一哩路的整合測試' },
  { lv: 1, label: '第八章：常見錯誤訊息與除錯 (Debugging) 圖鑑', key: '第八章：常見錯誤訊息與除錯圖' },
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
