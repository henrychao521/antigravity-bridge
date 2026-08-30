// 貳、環境建置　參、成本結構
const L = require('./lib');
const { docx, P, H1, H2, H3, LI, Box, T, Caption, Cite } = L;
const { Fig } = require('./imgs');

const ch2 = [
  H1('貳、環境建置：從訂閱到可程式化呼叫'),

  P('整個接通過程分成四步：訂閱、授權、取得權杖、呼叫。其中第三步是多數人會卡住的地方——官方文件只說「把伺服器加進你的 AI 客戶端」，但沒說如果客戶端無法進行互動式授權該怎麼辦。'),

  H2('一、訂閱與權限落差'),

  P('FeatureScript MCP 必須先在 Onshape App Store 訂閱（App Store → Categories → Onshape Labs）。方案標示「免費」，但註明 API limits apply。訂閱本身不需要信用卡。'),

  ...Box('商店頁與授權頁的權限描述不一致', [
    [{ t: '商店頁寫的是：can delete workspaces ' }, { t: 'from the FeatureScript MCP Workspace document', b: true },
     { t: '（僅限它自己建立的工作文件）。' }],
    [{ t: '但 OAuth 同意頁列出的是：「應用程式可以刪除' }, { t: '您的文件與工作區', b: true },
     { t: '」——沒有限定範圍。' }],
    [{ t: '實測結果：實際核發的權杖 scope 只有 OAuth2Read 與 OAuth2Write，', b: true },
     { t: '沒有 Delete。同意頁顯示的是該應用程式註冊時宣告的完整權限集，不是本次授權的實得範圍。' }],
  ], 'warn'),

  P('若仍要收緊，Onshape 提供「逐份文件授權」：在 My account → Applications 開啟該功能後，應用程式只能存取你主動以 Share 對話框分享給它的文件。授權前先開啟這項設定是較穩健的做法。'),

  H2('二、為什麼要自己實作 MCP 用戶端'),

  P('該伺服器走 OAuth 2.0 的動態用戶端註冊（DCR）流程，授權需要瀏覽器互動。非互動的工作階段無法完成標準的客戶端授權，因此本案直接以四十行程式碼自行實作整條流程。'),

  T([
    ['步驟', '端點', '要點'],
    ['1. 動態註冊', 'POST /register', '公開用戶端（token_endpoint_auth_method 為 none）＋ PKCE，回傳 client_id'],
    ['2. 使用者授權', 'GET /authorize', '帶 code_challenge（S256），在瀏覽器完成同意；回呼導向本機監聽埠'],
    ['3. 換取權杖', 'POST /token', '以 code 加 code_verifier 交換；expires_in 為 3599 秒，另附 refresh_token'],
    ['4. 呼叫工具', 'POST /mcp', 'Authorization 帶 Bearer；須保留伺服器回傳的 Mcp-Session-Id'],
  ], [1500, 2200, 5700]),
  Caption('表 2-1　自行實作的 OAuth 與 MCP 呼叫流程'),

  ...Box('兩個實作細節', [
    [{ t: '回應格式可能是純 JSON，也可能是 SSE（以 ' }, { t: 'data:', mono: true },
     { t: ' 開頭的事件串流），解析器兩種都要處理。' }],
    [{ t: '權杖一小時過期，務必實作 refresh_token 換發，否則長時間的除錯過程會中斷。' }],
  ]),

  P('自行實作還有一個附帶好處：可以在每次呼叫時記帳。本案的每一次工具呼叫都寫入 JSONL 帳本，完整輸出另存檔案——後者是花錢買到的教訓，見第伍章。'),
];

const ch3 = [
  H1('參、成本結構：文件沒寫的真實單價'),

  P('官方文件只說「API calls made by this MCP server count toward your overall Onshape API allocation」，但沒有任何一份文件說明各工具分別消耗幾次。這些數字只能靠實測：每次呼叫前後各查一次用量，相減即得。'),

  ...Fig('fig2_cost.png', '圖 3-1　各工具的實際 API 消耗（實測值）。test_feature 是其他工具的四倍。'),

  T([
    ['工具', '每次消耗', '用途與建議'],
    ['test_featurescript', '1 次', '執行一段 lambda。最划算的工具，語法探針與幾何驗證都用它'],
    ['search_featurescript_documentation', '1 次', '查官方文件。語意搜尋，關鍵字要精準'],
    ['get_api_usage', '1 次', '查剩餘額度。諷刺的是查額度本身也扣額度'],
    ['create_feature_studio', '1 次', '建立 Feature Studio'],
    ['自建 REST 探測器', '2 次', 'PUT 內容加 GET featurespecs，本案的主力除錯工具'],
    ['test_feature', '4 次', '寫入 Feature Studio 再評估。最貴，且錯誤訊息無行號'],
  ], [3100, 1200, 5100]),
  Caption('表 3-1　工具單價對照（2026 年 8 月 29 日實測）'),

  ...Box('最重要的成本結論', [
    [{ t: '除錯迴圈不要用 test_feature。', b: true },
     { t: '它一次吃掉四次額度，而且只回傳一句沒有行號的 ' },
     { t: 'could not find Trojan feature spec: no features found', mono: true },
     { t: '。自建的 REST 探測器成本只有一半，而且回傳「找到幾個特徵」這個明確訊號。' }],
  ]),

  H2('一、本次實驗的額度帳'),

  ...Fig('fig5_budget.png', '圖 3-2　年度額度的使用情形。本次完整實驗消耗 91 次，約占年度額度的 3.6%。'),

  P('91 次呼叫完成了一個自訂特徵從無到有的全部過程，包含兩次錯誤定位與四項幾何驗收。以剩餘 2,049 次推算，同等規模的題目還能做約二十題。但若沿用最初那種「寫完直接送 test_feature」的做法，同樣的除錯過程會膨脹到兩百次以上。'),
];
module.exports = { ch2, ch3 };
