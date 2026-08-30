const fs = require('fs'), path = require('path');
const L = require('./lib');
const { docx } = L;
const { Document, Packer, Paragraph, TextRun, Header, Footer, PageNumber,
        AlignmentType, BorderStyle, convertInchesToTwip } = docx;
const { cover, ch1 } = require('./content-1');
const { ch2, ch3 } = require('./content-2');
const { ch4, ch5 } = require('./content-3');
const { ch9, appendix } = require('./content-4');
const { ch6, ch7, ch8 } = require('./content-5');
const { buildTOC } = require('./toc');

const PAGE_MARGIN = { margin: {
  top: convertInchesToTwip(1), bottom: convertInchesToTwip(1),
  left: convertInchesToTwip(1.1), right: convertInchesToTwip(1.1) } };

const runningHeader = new Header({ children: [new Paragraph({
  children: [new TextRun({ text: '用兩個代理式 AI 操作 Onshape　｜　FeatureScript MCP 實戰歷程',
    size: 18, color: L.C_MUTED, font: L.font(L.F_BODY) })],
  alignment: AlignmentType.RIGHT,
  border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: L.C_RULE, space: 4 } },
  spacing: { after: 120 } })] });

const pageFooter = new Footer({ children: [new Paragraph({
  children: [new TextRun({ children: [PageNumber.CURRENT], size: 20,
    color: L.C_MUTED, font: L.font(L.F_BODY) })],
  alignment: AlignmentType.CENTER })] });

const blank = new Header({ children: [new Paragraph({ children: [new TextRun('')] })] });

const doc = new Document({
  creator: '趙翰宇',
  title: '用兩個代理式 AI 操作 Onshape：FeatureScript MCP 實戰歷程與成本結構',
  description: 'Onshape 官方 FeatureScript MCP Server 的接通方式、成本量測、二十輪除錯歷程與失敗路徑',
  styles: L.styles, numbering: L.numbering,
  sections: [
    { properties: { page: PAGE_MARGIN }, headers: { default: blank },
      footers: { default: new Footer({ children: [new Paragraph({ children: [new TextRun('')] })] }) },
      children: cover },
    { properties: { page: { ...PAGE_MARGIN, pageNumbers: { start: 1 } } },
      headers: { default: runningHeader }, footers: { default: pageFooter },
      children: [...buildTOC(), ...ch1, ...ch2, ...ch3, ...ch4, ...ch5, ...ch6, ...ch7, ...ch8, ...ch9, ...appendix] },
  ],
});

const out = path.join(__dirname, process.env.FONT_MODE === 'pdf'
  ? '_pdfsrc.docx' : '用兩個代理式AI操作Onshape.docx');
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(out, buf);
  console.log('✓ 已輸出：' + path.basename(out) + '  (' + (buf.length / 1024).toFixed(0) + ' KB)');
});
