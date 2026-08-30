#!/bin/bash
# 產出 Word（微軟正黑體）+ PDF（Arial Unicode MS），目錄頁碼兩輪回填
set -e
cd "$(dirname "$0")"
export NODE_PATH=/opt/homebrew/lib/node_modules
DOC="AI代理操作Onshape完整教學.docx"; PDF="AI代理操作Onshape完整教學.pdf"
export TOC_FILE="toc-pages.json"

echo "▸ 第一輪：建置（目錄頁碼佔位）"; rm -f "$TOC_FILE"
FONT_MODE=pdf node build.js 2>/dev/null | grep '✓'
rm -f _pdfsrc.pdf; soffice --headless --convert-to pdf _pdfsrc.docx --outdir . >/dev/null 2>&1
mv -f _pdfsrc.pdf "$PDF"

echo "▸ 擷取章節頁碼"
PDF_FILE="$PDF" node findpages.js 2>/dev/null | grep -E '✓|⚠' || true

echo "▸ 第二輪：回填頁碼後重建"
FONT_MODE=pdf node build.js 2>/dev/null | grep '✓'
rm -f _pdfsrc.pdf "$PDF"; soffice --headless --convert-to pdf _pdfsrc.docx --outdir . >/dev/null 2>&1
mv -f _pdfsrc.pdf "$PDF"

echo "▸ 產出 Word 版"; node build.js 2>/dev/null | grep '✓'; rm -f _pdfsrc.docx
pdfinfo "$PDF" | awk '/^Pages/{print "  → '"$PDF"'（" $2 " 頁）"}'
echo "  → $DOC"
