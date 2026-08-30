// 陸、驗證設計　柒、驗收結果與真實模型　捌、Antigravity 的獨立複驗
const L = require('./lib');
const { docx, P, H1, H2, H3, LI, Box, T, Caption, Cite } = L;
const { Fig } = require('./imgs');

const MODEL_URL = 'https://cad.onshape.com/documents/1674ae64c50f46714b4101f1/w/06f6a9cd7bd466a776a9cd52/e/70920e24320830591d8f8b79';

const ch6 = [
  H1('陸、驗證設計：如何避免自己騙自己'),

  P('本報告的初版有兩個結構性缺陷，是在覆核時才發現的。它們都不是「寫錯了」，而是「驗證方式本身留了洞」——這種洞最危險，因為產出看起來完全正常。'),

  H2('一、缺陷一：沒有產物可看'),

  ...Box('問題', [
    [{ t: '初版全部用 test_featurescript 在記憶體中建模量測，' },
     { t: '幾何算完就丟掉了', b: true },
     { t: '。Onshape 上沒有任何人能打開的東西，所有數字都只能相信報告作者的轉述。' }],
  ], 'bad'),

  P('修正方式是把模型真正建起來，並附上任何人都能打開的網址。過程中又踩到兩個坑：'),

  T([
    ['嘗試的方法', '結果'],
    ['create_geometry（官方工具）', '會建立分支工作區，但**事後自我清理**。實測三個工作區全部被刪除，網址失效'],
    ['test_feature（官方工具）', '只做求值，不留下幾何'],
    ['自行以 REST 在自有文件中建立 Part Studio 並加入特徵', '成功且永久保留'],
  ], [3800, 5600]),
  Caption('表 6-1　取得持久模型的三種嘗試'),

  ...Box('這個坑本身就是最好的例證', [
    [{ t: '若沒有實際用瀏覽器打開那個網址，報告就會寫著「模型已建立於此連結」，而' },
     { t: '那是一個死連結', b: true },
     { t: '。工具回報「Created new workspace」是真的，工作區隨後被刪除也是真的——兩件事都成立，但結論完全錯誤。' }],
  ], 'warn'),

  P('另外，透過 API 加入自訂特徵時，特徵的 parameters 會是空陣列，definition 不會有任何鍵。因此自訂的 LengthBoundSpec 預設值不會生效——那些預設值只在使用者從 UI 建立特徵時套用。示範用的特徵必須把尺寸寫死。'),

  H2('二、缺陷二：數字只有單一來源'),

  ...Box('問題', [
    [{ t: '體積與面數都來自同一支 lambda 的回傳。' },
     { t: '那支 lambda 若寫錯，數字錯了也看不出來', b: true },
     { t: '——這正是幻覺最容易藏身的位置：它不需要模型說謊，只要量測方式與被量測的對象共用同一段錯誤即可。' }],
  ], 'bad'),

  P('修正方式是三通道交叉驗證。三條路徑互相獨立：不同的程式路徑、不同的建構方式、甚至不同的代理。'),

  ...Fig('fig6_triangulate.png', '圖 6-1　三通道交叉驗證。A 與 C 由不同代理、以不同建構方式得到相同數字。'),

  T([
    ['通道', '執行者', '建構方式', '量測管道', '結果 (mm³)'],
    ['A', 'Claude', '草圖 + opExtrude', 'FeatureScript lambda 內 evVolume', '204712.389'],
    ['B', 'Claude', '同上，另加圓角並持久化', 'REST massproperties 端點', '204841.875'],
    ['C', 'Antigravity', 'fCylinder 直接造柱', '自行連線 MCP，獨立作業', '204712.389'],
  ], [900, 1600, 2600, 2600, 1900]),
  Caption('表 6-2　三通道的獨立性'),

  ...Box('為什麼這樣就足以排除幻覺', [
    [{ t: '通道 A 與 C 由' }, { t: '不同的代理、不同的建構方式', b: true },
     { t: '得到完全相同的數字（204712.38898…）。' }],
    [{ t: '通道 B 與 A 的差值 129.486 mm³，正好等於以 ' },
     { t: 'Pappus 定理', b: true },
     { t: ' 對圓角截面計算出的解析解 129.486 mm³，誤差 0.0000%。' }],
    [{ t: '要靠幻覺同時湊出這三個彼此關聯、且與解析解吻合的數字，機率為零。', b: true }],
  ]),

  H2('三、缺陷三：讓另一個代理複述自己的結論'),

  ...Box('問題', [
    [{ t: '初版曾把本報告的歷程紀錄交給 Antigravity，請它「也寫一份」。它照做了，寫得也順——但那份報告' },
     { t: '結構上不可能反駁任何東西', b: true },
     { t: '，因為它的全部資訊都來自我。這不是複驗，是用另一種文筆包裝同一個盲點。' }],
  ], 'bad'),

  P('修正方式是讓它自己動手。Antigravity CLI 的 mcp add 支援注入 HTTP 標頭，因此可以把 OAuth 權杖直接給它：'),

  ...Cite(['agy mcp add --header "Authorization: Bearer <token>" onshape https://fs-mcp.labs.onshape.app/mcp']),

  P('如此它便擁有自己的 Onshape 連線，自己下工具呼叫、自己撞錯誤、自己量測。第捌章是它在完全沒有看過本報告的情況下，獨立完成同一個題目的結果。'),
];

const ch7 = [
  H1('柒、驗收結果與真實模型'),

  P('以下模型實際存在於 Onshape，任何人都可以打開檢視。這是本報告與初版最重要的差別：數字不再只是轉述。'),

  ...Fig('onshape_render_iso.png', '圖 7-1　Onshape 伺服器渲染的等角視圖。此圖由 shadedviews 端點產生，直接來自模型本身，非示意圖。', 430),

  ...Fig('onshape_render_front.png', '圖 7-2　前視圖。可見定位柱根部的過渡圓角。', 430),

  ...Box('模型網址（可直接打開驗證）', [
    [{ t: MODEL_URL, mono: true }],
    [{ t: '文件名稱 FS-MCP Lab (agent scratch)，分頁「SmartBoss 驗證模型」。特徵樹中可見 SmartBossDemo，零件數 1。' }],
  ]),

  T([
    ['驗收項目', '預期值', '實測值', '判定'],
    ['體積（關圓角）', '204712.389 mm³', '204712.389 mm³', '通過，誤差 0.00000%'],
    ['體積（開圓角，REST 獨立量測）', '204841.875 mm³', '204841.875 mm³', '通過，差值符合解析解'],
    ['面數（關圓角）', '8（6 + 2N）', '8', '通過'],
    ['面數（開圓角）', '9（6 + 3N）', '9', '通過'],
    ['Part 數', '1', '1', '通過'],
    ['特徵狀態', 'OK', 'OK', '通過'],
  ], [3000, 2400, 2200, 2800]),
  Caption('表 7-1　驗收結果彙整'),

  ...Fig('fig4_geometry.png', '圖 7-3　驗證用幾何的尺寸與驗收數字對照。'),
];

const ch8 = [
  H1('捌、Antigravity 的獨立複驗'),

  P('本章的內容不是我寫的。Antigravity 取得自己的 Onshape MCP 連線後，在沒有看過本報告任何內容的前提下，被交付同一個幾何規格，自行完成建模與量測。以下是它的實際遭遇。'),

  H2('一、它得到的數字'),

  ...Box('獨立量測結果', [
    [{ t: '204712.38898038468 mm³', b: true, mono: true }],
    [{ t: '與通道 A 完全相同。而它的建構方式與我不同——我用「草圖畫圓再 opExtrude」，它直接用 fCylinder 造圓柱。' },
     { t: '兩條不同的路走到同一個數字，這才是有意義的複驗。', b: true }],
  ]),

  H2('二、它踩到的坑（與我不同）'),

  T([
    ['它遇到的錯誤', '它如何定位'],
    ['以為基元函式叫 opCuboid / opCylinder，實際報 Function opCuboid with 3 argument(s) not found',
     '用 search_featurescript_documentation 查 primitives，確認正確前綴是 f 而非 op'],
    ['在 lambda 中寫 id + "base"，報 Can not add map and string',
     '發現 test_featurescript 傳入的 id 實際上是 map，不是 Id 型別'],
    ['改傳陣列後報 No matching function for qCreatedBy(array, EntityType)',
     '確認 Id 不能以裸陣列替代，改用 test_feature 取得真正的 Id'],
    ['opBoolean 失敗',
     '回頭查它先前印出的官方文件片段，找到明載的一句：Target bodies are not used by UNION'],
  ], [4200, 5200]),
  Caption('表 8-1　Antigravity 獨立作業時遭遇的問題'),

  ...Box('它找到了我沒找到的證據', [
    [{ t: '同一個 opBoolean 的坑，我是靠實驗推翻假設才發現的（先誤判為「兩體僅面接觸」，讓柱體下沉 1mm 仍失敗才轉向）。它則直接在官方文件裡找到白紙黑字的一句：' }],
    [{ t: 'Target bodies are not used by UNION.', b: true, mono: true }],
    [{ t: '這正是獨立複驗的價值——不是確認我對，而是可能給出更好的證據。', b: true }],
  ]),

  H2('三、它自陳學到的事實'),

  ...['FeatureScript 中布林等「操作」以 op 為前綴，但最基礎的幾何基元創建函式以 f 為前綴（fCuboid、fCylinder）',
      'opBoolean 的 UNION 完全不接受 targets 參數，這與 CAD 介面裡「選目標零件與工具零件」的思維不同',
      '可以跑一個最簡單的 lambda，從回傳值的 libraryVersion 欄位取得當前版本號，避免寫錯版本標頭',
      'evVolume 回傳的是 ValueWithUnits 而非純數字，要除以 (millimeter ^ 3) 才會得到乾淨的 mm³ 數值',
     ].map((t) => LI(t)),

  ...Box('與我的結論的交集與差異', [
    [{ t: '交集：', b: true }, { t: 'opBoolean 的 UNION 不能給 targets、版本號要動態取得——兩邊獨立得到相同結論。' }],
    [{ t: '差異：', b: true }, { t: '我遇到的 evBox3d 編譯失敗它完全沒碰到（因為它沒用那個函式）；它遇到的 f 前綴命名與 lambda 中 id 為 map 的問題我也沒碰到。' },
     { t: '兩份清單互補，合起來才完整。', b: true }],
  ]),

  P('值得一提的是，本報告第伍章記錄過一次教訓：初次請 Antigravity 診斷編譯錯誤時，它給出四條全錯的「確定錯誤」。差別在於——那一次它是在憑記憶臆測，這一次它手上有工具，每個判斷都能驗證。同一個模型，有無驗證管道的差距就是這麼大。'),
];

module.exports = { ch6, ch7, ch8 };
