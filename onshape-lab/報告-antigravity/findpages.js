// 自 PDF 純文字擷取各章節所在頁碼，寫入 toc-pages.json 供目錄回填
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { ITEMS } = require('./toc');

const pdf = path.join(__dirname, process.env.PDF_FILE || 'AI運動分析課程規劃_修正版v2.pdf');
if (!fs.existsSync(pdf)) { console.error('找不到 PDF，請先轉檔'); process.exit(1); }

// 逐頁抽文字（-f/-l 指定頁範圍）
const nPages = parseInt(
  execSync(`pdfinfo "${pdf}" | awk '/^Pages/{print $2}'`).toString().trim(), 10);

// 封面為獨立 section，其頁不計入正文頁碼；正文自 PDF 第 2 頁起，頁碼為 PDF頁-1
const OFFSET = 1;

const pageText = [];
for (let i = 1; i <= nPages; i++) {
  const t = execSync(`pdftotext -f ${i} -l ${i} "${pdf}" - 2>/dev/null`).toString();
  pageText.push(t.replace(/\s+/g, ''));   // 去除所有空白，避免換行切斷比對
}

const norm = (s) => s.replace(/\s+/g, '');

// 目錄頁本身列有全部章節名稱，必須排除，否則所有項目都會指向目錄頁。
// 目錄可能橫跨多頁，故以其專有特徵（點線 leader）辨識，而非單一關鍵字。
const isTocPage = pageText.map((t) => /\.{10,}/.test(t));
const lastTocIdx = isTocPage.lastIndexOf(true);
const startIdx = lastTocIdx === -1 ? 1 : lastTocIdx + 1;

const map = {};
const missing = [];

const items = process.env.CLEAN === '1'
  ? ITEMS.filter((it) => it.key !== '本版修訂說明')
  : ITEMS;
items.forEach((it) => {
  const key = norm(it.key);
  // 先在目錄之後尋找；若無（如位於目錄之前的「本版修訂說明」），則全範圍尋找但排除目錄頁
  let idx = pageText.findIndex((t, i) => i >= startIdx && t.includes(key));
  if (idx === -1) {
    // 位於目錄之前者（如「本版修訂說明」），全範圍尋找但排除目錄頁
    idx = pageText.findIndex((t, i) => i >= 1 && !isTocPage[i] && t.includes(key));
  }
  if (idx === -1) { missing.push(it.key); return; }
  map[it.key] = idx + 1 - OFFSET;
});

fs.writeFileSync(path.join(__dirname, process.env.TOC_FILE || 'toc-pages.json'), JSON.stringify(map, null, 2));
console.log(`✓ 已定位 ${Object.keys(map).length}/${items.length} 個章節，總頁數 ${nPages}`);
if (missing.length) console.log('⚠ 未找到：\n  - ' + missing.join('\n  - '));
