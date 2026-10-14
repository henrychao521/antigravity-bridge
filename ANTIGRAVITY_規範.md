# Antigravity 派工規範

> 貼給新對話視窗用。搭配 `/Users/Shared/antigravity-bridge/` 底下的操作檔案。
> 最後更新：2026-10-13（agy 1.3.4 模型大換血：3.7 Flash、3.1 Pro、Claude 4.6 全下架，第二～四節改用新 id）
> 前次：2026-09-10（新增第十一節：教材圖片；第十二節：監測項目與 1.2.0 變更）

## 一、這是什麼

Antigravity 是 Google 的代理式 AI CLI（`agy`），**走 Google AI Pro 訂閱額度，不另外計費**。
它可以被 Claude Code 當成第二個 LLM 使喚：分攤工作、或做多方交叉驗證。

執行檔：`~/.local/bin/agy`（v1.3.4，2026-10-13 確認）　憑證：沿用 Antigravity app 的 Google 登入，機器層級 keyring

## 二、模型選擇

`agy models` 實測可用清單（2026-10-13，agy 1.3.4，**完整清單就這 10 個**）：

| 模型 id | 配額組 | 定位 |
|---|---|---|
| `gemini-3.8-flash-high` / `-medium` / `-low` | Gemini | **唯一的 Gemini**，快、便宜；預設主力 |
| `claude-sonnet-5-5-high` / `-medium` / `-low` | Claude/GPT | 異家族觀點 |
| `claude-opus-5-5-high` / `-medium` / `-low` | Claude/GPT | **最高能力**，配額成本約 Flash 的 86 倍（見第三節） |
| `gpt-oss-120b-medium` | Claude/GPT | 第三家族觀點 |

**已下架（2026-10-13 實測回 `not recognized as a known model`）**：`gemini-3.7-flash-*`、
`gemini-3.6/3.5-flash-*`、`gemini-3.1-pro-*`、`claude-sonnet-4-6`、`claude-opus-4-6-thinking`。
帶舊 id 的呼叫在送出前就失敗、0 token，但**會讓整批派工空轉**。agy 升版後先跑 `agy models`
（不耗額度）對一次清單；`agy_meter.capabilities()` 的 `new_models` 會列出新增的 id。
注意 Claude 這組現在用 `-high/-medium/-low` 後綴，**沒有 `-thinking` 後綴了**。

### 實測比較（2026-10-14，現役模型重跑同一份 8 題測驗＋一題寫程式）

知識測驗沿用 8/29 的題目與實測標準答案（`bench/score_2026_10_14.py`，逐題理由寫在檔內）；
寫程式題是「民國日期轉西元」函式，37 個隱藏測試自動判分（`bench/roc_date/`）。

| 模型 | 知識 8 題 | 答錯時平均信心 | 寫程式 37 題 | 每次吃掉 5h／週配額 | 耗時 |
|---|---|---|---|---|---|
| `claude-opus-5-5-high` | **7.5 / 8** | **0.30** | 37 / 37 | **10.6–14.1% ／ 5.3–7.0%** | 43–71s |
| `claude-sonnet-5-5-high` | 5.5 / 8 | 0.43 | 37 / 37 | 5.6–7.7% ／ 2.8–3.9% | 44–77s |
| `gemini-3.8-flash-high` | 4 / 8 | 0.69 | 37 / 37 | 0.8% ／ 0.2% | **174–307s** |
| `gpt-oss-120b-medium` | 3.5 / 8 | 0.85 | 35 / 37 | 0.1–0.4% | 53–166s |

- **Opus 5.5 是目前最強，也最會示弱**：8/29 三家全錯的 Q2（UNION 不能給 targets）它答對，
  Q4 答不出但自承不熟（信心 0.3）。比舊 3.1 Pro（5.5/8、錯題信心 0.92）明顯好。
- **代價很高**：一次 5 萬 token 級的呼叫吃 Claude 組 5h 窗口 11–14%、**週額度 5–7%**，一週約十幾次就見底。
  只留給真的需要最強判斷的交叉驗證；一般異家族觀點用 Sonnet 5.5（約一半價）。
  → **`cross_check.py` 與 agyq 預設已改用 Sonnet 5.5（2026-10-14）**，要 Opus 時明確指定。
- **Gemini 3.8 Flash 知識面和 3.7 一樣（4/8）**，但寫程式不輸；**沒有 Pro 之後，它也是最慢的**（3–5 分鐘）。
- gpt-oss 會捏造 API（`box()`、`@libraryVersion 9`）且信心高，國字數字也寫錯，只適合當第三票。
- 寫程式題太簡單（前三家全對），分不出高下；下次要加更刁的題目。

**`gemini-4-argon`（-high/-medium/-low）已寫在 agy 1.3.4 程式裡，但伺服器還沒開給這個帳號**
（2026-10-14 實測 not recognized，`agy models` 也沒有）。等它出現在 `agy models` 再測，不要用自訂模型設定硬叫。

**`--effort` 新增 `xhigh`／`max`，但目前三個模型都只支援 low/medium/high**（錯誤訊息會列出可用強度）。
`--effort` 要配不帶後綴的 id（`--model gemini-3.8-flash --effort high`），和 `-high` 後綴同時給會報 conflicts。

### 實測比較（2026-08-29，8 題有標準答案的 FeatureScript 知識測驗）

> ⚠️ 下表三個模型都已下架，數字只當歷史參考；3.8 Flash／Claude 5.5 尚未重測（腳本在 `bench/`）。

標準答案來源＝同一場 session 在 Onshape 上實際跑出來的結果，不是文獻。

| 模型 | 得分 | 答錯時的平均信心 | 耗時 |
|---|---|---|---|
| `gemini-3.1-pro-high` | **5.5 / 8** | 0.92（最不會示弱） | 50s |
| `claude-opus-4-6-thinking` | 4.5 / 8 | **0.67（最誠實）** | 63s |
| `gemini-3.7-flash-high` | 4 / 8 | 0.79 | **32s** |

**結論要保守看**：3.1-pro 確實贏 3.7-flash，但 8 題樣本太小，差距主要來自一題
（3.7 對版本號亂猜 2400-2600 且信心 0.5，另兩家老實說不知道）。純知識面三者接近。

**兩個更重要的發現**：
1. **三家在兩題上全錯**——`opBoolean` 的 UNION 不能給 targets、lambda 裡 `id` 是 map。
   而這兩題正是本 session 實際卡最久的兩個坑。**冷門 API 不要問模型，要測。**
2. **3.1-pro 答錯時信心最高（0.92）**。它分數最高但最不會示弱，
   **不能拿它的自陳信心當可信度指標**。opus 反而最會說「我不確定」。

**目前沒有任何 Gemini Pro。** 3.1 Pro 下架後 Gemini 組只剩 3.8 Flash，所以「更高認知能力」的路：

- **同一個便宜配額組內** → `gemini-3.8-flash-high`（現在的預設主力；舊主力 3.1-pro 寫過 25 頁教學報告，3.8 尚未在同等長文上驗證）
- **要真正更強** → `claude-opus-5-5-high`，但**只能偶爾用**（見成本表）

模型的 `-high/-medium/-low` 後綴就是推理強度，**不需要另外加 `--effort`**。
**沒有「設定預設模型」的設定檔選項**，每次呼叫都要用 `--model` 明確指定。

## 三、成本模型（實測校準）

同樣約 26–29k tokens 的一次呼叫：

| 模型 | 吃掉 5 小時配額 | 一個窗口約可跑 |
|---|---|---|
| `gemini-3.8-flash-*`（2026-10-13，27k tok，high 與 low 相同） | 0.10% | **約 1,000 次** |
| `gemini-3.7-flash-high`（已下架，2026-08-29） | 0.10% | 約 1,025 次 |
| `claude-opus-4-6-thinking`（已下架，2026-08-29） | 3.59% | 約 24 次 |
| `claude-sonnet-5-5-high`（2026-10-13，43k tok，**只 1 次樣本**） | 4.32% | **約 23 次** |
| `claude-opus-5-5-high`（2026-10-13，43k tok，**只 1 次樣本**） | 8.63% | **約 11 次** |

**舊 Opus 與 Flash 差 37 倍；Opus 5.5 首次實測約 86 倍**（同樣只回 OK，底盤 token 卻多了 16k），Claude 組比以前更稀缺。 所以：

- 批量、機械性、可容錯 → Gemini 組，等於免費
- 需要異家族觀點的交叉驗證 → Claude/GPT 組，一個窗口約 24 次，省著用

派工前先跑 `python3 /Users/Shared/antigravity-bridge/token_report.py` 看剩餘額度。
選單列有常駐小工具顯示 `◈ G99 C87`（Gemini 組／Claude·GPT 組的 5 小時窗口剩餘 %）。

## 四、基本用法

```bash
~/.local/bin/agy -p "提示" --model gemini-3.8-flash-high --output-format json
```

回傳 JSON 含 `conversation_id`、`status`、`response`、`duration_seconds`、`usage`。

| 旗標 | 用途 |
|---|---|
| `--model <id>` | 選模型，**必填**（無預設值設定） |
| `--output-format json` | 結構化回傳，程式好解析 |
| `--json-schema f.json` | 強制結構化輸出，讀回傳的 `structured_output` 欄位 |
| `--conversation <id>` | **接續某場對話**，它才保有那場的記憶 |
| `--dangerously-skip-permissions` | 自動核准所有工具，只在沙箱用 |

## 五、五條硬規則（都是踩出來的）

**1. headless 無法提示權限。** 它想用工具會被自動拒絕、回空字串，**但照樣扣 26k tokens**。
兩條解法：在 `~/.gemini/antigravity-cli/settings.json` 的 `permissions.allow` 加規則，
或在提示裡明講「不要使用任何工具」。

**規則格式是 `<權限類型>(<目標>)`**，類型名稱由拒絕訊息告訴你
（例如 `command`、`write_file`、`read_url`、`mcp`）。

**比對器不支援路徑萬用字元**——實測 `write_file(/tmp/*)` 與 `write_file(<某資料夾>/*)` 都無效，
只有 `write_file(*)` 通過。**因此做不到「限定在某資料夾內讀寫」這種沙箱**。
要它跑需要執行程式的任務，實務上只有兩條路：給 `command(*)`（永久、風險最高），
或**單次加 `--dangerously-skip-permissions`（建議，不寫進常駐設定，跑完即失效）**。

目前已允許的規則（唯讀，無任何寫入指令）：
```
command(ls) command(cat) command(head) command(tail) command(file) command(stat)
command(wc) command(du) command(pwd) command(which) command(tree)
command(grep) command(rg) command(find)
command(git status) command(git log) command(git diff)
mcp(onshape/*)
```

**2. 不要叫它「讀多個檔案再產長程式碼」。** 重現三次都失敗（回空字串或 `status: CANCELED`）。
**把素材直接內嵌進提示**才穩。單檔 `cat` 沒問題。

**3. 要它的第一手經驗，一定要用 `--conversation <id>` 續談。**
每次 `-p` 都是全新對話。餵它你的結論請它改寫 ＝ 二手複述，**會放大你的盲點，沒有複驗價值**。

**4. 一律包 timeout，抓 60 分鐘，而且要同時放寬 agy 自己的 `--print-timeout`。**
實測延遲 2.4 秒 ～ 3,280 秒（55 分鐘）都出現過。

**`--print-timeout` 預設只有 5 分鐘**，超過就回
`status: ERROR, error: "timeout waiting for response"`，**回應是空的但工作已經做掉了**——
實測一次燒掉 140k tokens 與 62 次 Onshape 額度卻拿不到任何輸出。長任務務必加：

```bash
agy -p "$P" --model X --print-timeout 60m --output-format json
```

**被砍掉的成果可以救**：用該次回傳的 `conversation_id` 續談，請它「直接報告剛才做了什麼、
不要重做」，伺服器端的對話歷程還在。

```bash
( agy -p "$P" --model X --output-format json 2>/dev/null & p=$!; \
  ( sleep 3600; kill $p 2>/dev/null ) & wait $p ) > out.json
```

**5. 並行時用 `--conversation <id>`，不要用 `--continue`。** 後者抓「最近一個對話」，會互搶。

## 六、它擅長與不擅長什麼

**擅長**
- 長文撰寫（25 頁教學報告一次搞定）
- 熱門套件的程式碼（`docx` 建置腳本第一次執行就成功）
- **給它工具連線後的獨立實作**——會找到你沒找到的證據

**不擅長**
- 冷門 DSL／API 的事實判斷。**它會很有自信地編**：曾一次給出四條「確定錯誤」全是幻覺，
  且完全沒提到真正的病因
- 需要快速迭代的除錯（延遲太長）

**判準：有工具可驗證時它很可靠，憑記憶作答時不可靠。**

## 七、給它工具連線（讓複驗有意義）

```bash
# HTTP 型 MCP，可注入認證標頭
agy mcp add --header "Authorization: Bearer <token>" <name> <url>
# stdio 型
agy mcp add <name> <command> [args...]
agy mcp list / remove / enable / disable
```

加完要在 settings.json 的 `permissions.allow` 補 `mcp(<name>/*)`，否則 headless 會被拒。

**已解決：Onshape 走本機認證代理。**
`onshape_proxy.py`（launchd 常駐，`com.henry.onshape-proxy`）在每次轉發時才向
`onshape_mcp._token()` 取 token，該函式會自動用 refresh_token 換發。agy 指向
`http://127.0.0.1:8912/mcp` 即可，**不再有過期問題**。設定方式：

```bash
agy mcp add onshape http://127.0.0.1:8912/mcp
```

**（以下為代理出現前的原始問題，留作背景）** 注入的 Bearer token 會過期，agy 不會自動換發。 OAuth token 通常 1 小時到期，
過期後它呼叫工具會靜默失敗、回空字串。長期使用要在每次派工前重新 `mcp remove` + `mcp add`
帶上新 token，或改用不會過期的認證方式。

## 七之二、已為 Antigravity 加裝的能力

| 項目 | 內容 |
|---|---|
| **Onshape 認證代理** | `onshape_proxy.py`，launchd 常駐於 127.0.0.1:8912。解決 token 一小時過期 |
| **影像處理環境** | `~/cv-venv`（cv2 5.0.0 / numpy / pillow）。派影像任務時在提示中指定用 `~/cv-venv/bin/python` |
| **內建能力** | 它本來就有 `search_web`、`read_url_content`、`generate_image`、subagent 管理 |

**plugin 匯入無效**：`agy plugin import gemini|claude` 都回報 no extensions found——
`~/.gemini/config/plugins` 裡那些是 Antigravity **桌面版 app** 的 plugin，不是 agy 認得的 extension。

## 八、可重用的操作檔案

| 檔案 | 用途 |
|---|---|
| `agy_meter.py` | `run()` 派工並自動記帳（呼叫前後各拍額度快照）、`quota()` 查剩餘 |
| `token_report.py` | 派工前先看：剩餘配額、每模型單次成本、還能跑幾次 |
| `claude_meter.py` | Claude Code 側用量（掃 `~/.claude/projects/**/*.jsonl`） |
| `cross_check.py` | 同題並行問多個模型家族，結論分歧會標出來 |
| `usage_history.py` | 每日時序 CSV，長期追蹤 |
| `agy_widget.py` | 選單列小工具（launchd 常駐，開機自動啟動） |

用法：`sys.path.insert(0, "/Users/Shared/antigravity-bridge")` 後 import。

## 九、主管模式（建議的預設工作流）

不要「派工一次就收貨」。用 `agy_meter.supervise()`：派工 → **實際驗收** → 不過就退回重做。

```python
import sys; sys.path.insert(0, "/Users/Shared/antigravity-bridge")
import agy_meter as m

def check(text):                      # 必須回傳 (通過與否, 意見)
    ...                               # 真的去跑、去比對，不要用「看起來對不對」判斷
    return ok, feedback

res = m.supervise(task, criteria, check,
                  model="gemini-3.8-flash-high", max_rounds=3)
```

它用 `--conversation` 續談，所以退回時它看得到自己上一版寫了什麼，是修改而不是重寫。

**驗收條件必須機器可判定**：跑得起來、數字對得上、schema 合格、編譯通過。
「寫得不錯」不是驗收條件。實測示範：第 1 回合它沒給出程式碼區塊被退回，第 2 回合通過
（`bench/demo_supervise.py`）。

**驗收條件要在第一輪就講清楚**，連同任務一起給。它會照著寫，不必等被退回才知道標準。

## 十、貼給新對話的起手式

```
請讀 /Users/Shared/antigravity-bridge/ANTIGRAVITY_規範.md，
之後這個專案的工作依該規範分派給 Antigravity。
派工前先跑 token_report.py 確認額度。
```

---

## 十、更正：headless 下**是有工具的**（2026-08-31 實測）

前面「headless 權限受限，實務上當成純文字進出」這個說法**不正確**，
而且因為這個誤解，過去每一則派工提示都寫了「不要使用任何工具」，等於自己把能力關掉。

`agy -p` 下實際可用的工具（`init` 事件會列出全部）：
`view_file`／`run_command`／`write_to_file`／`replace_file_content`／
`read_url_content`／`search_web`／`grep_search`／`find_by_name`／`list_dir`／
`generate_image`／`invoke_subagent`／`browser_*`。

### 為什麼看起來沒有工具

工具呼叫要通過 `~/.gemini/antigravity-cli/settings.json` 的 `permissions.allow`：

- 比對的是**指令名稱**，`command(python)` **不會**匹配完整路徑
  `/Volumes/.../venv/bin/python`——要另外加一條。
- 碰工作區外的路徑還要看 `trustedWorkspaces`。
- **工具呼叫一旦被拒，該回合直接結束、`response` 是空字串。**
  外觀上就像「模型什麼都沒做」，實際上是權限沒開。這是最會誤導人的一點。

用 `--output-format stream-json` 才看得到工具呼叫與其 `tool_info.output`。
`agy_meter.run_with_tools()` 已封裝好，會回傳 `steps`（含每次呼叫的狀態與輸出）
與 `denied`（被拒的呼叫），並照樣記帳。

### 安全邊界（實測，不是推論）

| 途徑 | `~/.ssh`、`~/.claude` | 寫入家目錄 | `/Volumes/*` | `/tmp` | 網路 |
|---|---|---|---|---|---|
| `run_command` 加 `--sandbox` | 拒絕 | 拒絕 | 可 | 可 | 可 |
| 原生 `write_to_file` | — | **可寫** | 可 | 可 | — |

**`--sandbox` 只限制終端機**（help 寫的就是 "terminal restrictions"），
原生檔案工具不受它也不受 `--add-dir` 約束——實測 `write_to_file` 成功寫進
`/Users/henry/` 與 `/Users/Shared/`。
所以 `--dangerously-skip-permissions` 等於給它**任意讀寫**，不要在無人看管的
排程裡用。允許清單才是真正的控制面。

### 什麼時候該開工具

**該開**：提示內容完全由自己掌控的任務——
查證代號／網址是否有效、跑測試、產生程式碼後自我驗證、讀專案檔案。
這幾件事以前只能由 Claude 這側做，是省下往返的主要來源。

**絕對不要開**：**會吃進不可信內容的任務**。
本專案的每日分析會把 150 則新聞標題餵進提示，而允許清單裡有 `write_file(*)`——
新聞標題裡的注入指令可能觸發寫檔。這類派工一律維持「不要使用任何工具」。

### 已做的設定變更（2026-08-31）

- `trustedWorkspaces` 加入 `/Volumes/Work`、`/Users/Shared`
- `permissions.allow` 加入唯讀查證與測試用指令：
  `date sed awk sort uniq diff curl jq python pytest search_web(*)`
  以及 `command(/Volumes/Work/market-pulse/.venv/bin/python)`
- 備份在 `~/.gemini/antigravity-cli/settings.json.bak-*`
- **沒有**啟用 `--dangerously-skip-permissions`

---

## 十一、教材與教材網頁的圖片：預設向 Antigravity 生成（2026-09-10 起常設）

> 跨專案的「哪種圖用哪個工具」決策表（寫實照片、心智圖、流程圖、報告封面、PPT 底圖、圖示）在
> `/Volumes/Work/圖片產生規範.md`；本節只管 Antigravity 生圖的操作細節。

**使用者指示**：往後所有教材網頁（含講義、簡報、互動教學平台頁面、刊物稿件）需要的插圖與照片，
**預設透過 Antigravity 的 `generate_image` 取得**，不必每次詢問。
首次實戰：`/Volumes/Work/stem-energy-articles/`——驅動器 `dispatch/gen_images.py`（批次生圖、自動找檔、保存軌跡）、
規格 `dispatch/image_spec.py`（提示詞寫法範例）、合成 `src/compose_lib.py`（中文標籤、引線、立體電線、multiply 去白底）、
放大 `src/upscale_mlx.py`。新專案可直接複製這四支。

### 分工

| 步驟 | 誰 | 說明 |
|---|---|---|
| 決定要哪些圖、寫英文提示詞 | **Claude** | 物理／接線／極性等細節要寫死在提示詞裡 |
| 生圖 | **Antigravity** | `generate_image`，走 Gemini 配額組 |
| 中文標註、數字、箭頭、圖表、拓樸（接線、流程） | **Claude 本機合成** | PIL／SVG／matplotlib。需要再編輯、有數字或長文字的一律本機畫 |
| 短標籤的心智圖、流程圖（整張交給它） | Antigravity（例外） | 2026-09-11 實測兩張共 29 個繁中字全對；**仍須放大逐字驗收**，且成品無法改字 |
| 放大到印刷解析度 | **本機** | Real-ESRGAN x4plus（MLX 自寫推論，見下） |
| 驗收 | **Claude** | 目視＋本機 VLM；派工方不能兼裁判 |

### 工具事實（實測，不是推論）

> **2026-10-08 更正（agy 1.3.1，官方 changelog 1.2.16 起）：父代理已經沒有 `generate_image`，生圖一律交給內建 `image-generator` 子代理。**
> 下面凡是寫「看 `steps[]` 的 generate_image」「到 `brain/<conversation_id>/` 找檔」的舊做法，在 1.2.16 以後都會誤判成全部失敗。

- **流程變成**：父代理呼叫 `invoke_subagent`（`TypeName: image-generator`，一張圖一個子代理），子代理才呼叫 `generate_image`，
  完成後用 `send_message` 回報父代理；父代理有時還會自己用 `manage_subagents`／`schedule`／`manage_task` 輪詢。
  父代理的思考紀錄明寫「工具清單裡沒有 generate_image」，所以**叫它「自己呼叫 generate_image、不要用子代理」做不到**，只能規範子代理怎麼做。
  不輪詢也沒關係：`-p` 會等子代理的訊息回來才結束（5011a542 那批沒有輪詢，四張都等到了）。
- **`run_with_tools()` 的 `steps[]` 看不到任何 `generate_image`**（父代理軌跡只有 invoke_subagent／schedule／manage_subagents），
  帳本的 `image_ok`／`image_err` 也因此是 0。**子代理的 429 也不會出現在父代理的 steps**。
- **檔案位置**：子代理把圖寫在**父對話**的目錄 `brain/<父 conversation_id>/<imagename>_<13 位時間戳>.jpg`；
  子代理自己的對話是另一個 brain 目錄（只有 `.system_generated/logs/transcript_full.jsonl`，裡面才有 generate_image 的 `tool_calls[].args` 與 429 錯誤）。
  父目錄底下 `.system_generated/subagents/<子代理 id>.json` 記著子代理清單。
- **找檔改用 `agy_meter.brain_scan(names, since)`**：掃 since 之後有變動的所有 brain 目錄（深度 2），
  取 `<name>_<時間戳>` 的最新一張；沒有原名才退而取 `<name>_` 開頭的其他版本；同時回傳子代理實際送出的參數與 429（並自動記進生圖配額狀態）。
  `image_router.py` 與 `rc-car-materials/dispatch/gen_images.py` 已改用它（2026-10-08）。
- **子代理會自作主張多生**（官方說明：子代理「檢查結果、最多重試三次」）。2026-10-08 一輪 11 張：`parking_bus` 生了兩次、
  `r2_hand_device` 另做 `r2_hand_device_v2`（用 ImagePaths 修掉螢幕上的字）、`title_desk` 另做 `title_desk_fixed`（撞 429 失敗），
  **11 張圖吃掉 13 張窗口**。→ 提示詞要明講「每張只生一次、不檢查、不重生、不另做版本」，並要求父代理把這段英文規則原封不動放進每個子代理的 Prompt（`image_router.SUB_RULE`）。
- **子代理會改寫提示詞**：同一輪 11 張只有 3 張逐字照送，其餘被擴寫到 650～940 字元。逐字驗收要比對子代理軌跡裡的 `Prompt`（`brain_scan()["calls"]`），不是父代理的 steps。
  AspectRatio 子代理會自己帶（11/11 都是 16:9）。

- **實際模型是 `gemini-3.1-flash-image`**（429 錯誤的 metadata 寫的）。agy 被問時自稱「Imagen 3」——**是錯的**，不要引用它的自述。
- ~~呼叫參數實際只有 `ImageName`、`Prompt` 兩個~~（**2026-09-18 更正**）：還有 **`ImagePaths`（最多 3 張絕對路徑，參考圖／編輯來源）** 與 **`AspectRatio`**（1:1、2:3、3:2、3:4、4:3、9:16、16:9）。之前以為沒有，是因為 `stream-json` 的 tool params **只列 ImageName／Prompt**；完整參數要讀 `~/.gemini/antigravity-cli/brain/<conv>/.system_generated/logs/transcript_full.jsonl` 的 `tool_calls[].args`。實測：包裝指令寫「ImagePaths 參數一定要帶」，它就會照傳；結果寬高跟著 AspectRatio 走（1376×768）。
- **參考圖怎麼給（2026-09-18 rc-car 實測 5 張）**：給「程式畫的正確結構圖（無字）＋真實產品照」最有效；**不要把有瑕疵的舊圖當參考**——3 張全部連錯誤一起照抄構圖，改成只給結構圖後 3/3 通過。驅動器：`/Volumes/Work/rc-car-materials/dispatch/gen_ref.py`。
- **長寬比由提示詞文字決定**：開頭寫 `Wide 16:9 landscape` → 1376×768；寫 `Square 1:1` 或不寫 → 1024×1024。
  它回報「用了 `AspectRatio: 16:9`」，但軌跡裡沒有這個參數——**一律以 `steps[].params` 為準，不信文字回報**。
- 輸出位置：`~/.gemini/antigravity-cli/brain/<conversation_id>/<ImageName>_<時間戳>.jpg`。
  **檔名的 ImageName 會被轉成小寫**（2026-09-11 實測 `type_M1` → `type_m1_…`），找檔要不分大小寫，否則會誤判沒產出而重生。
  用 conversation_id＋ImageName 自己找檔、自己複製，不要叫它搬檔。
  （1.2.16 起是**父**對話的 id，但不要依賴它，改用 `brain_scan()`，見本節開頭的更正。）
- **全部失敗時它照樣回「DONE」**。成功與否只看檔案是否存在（1.2.15 以前另看 `steps[]` 裡該呼叫的 `state`；1.2.16 起父代理的 steps 沒有 generate_image）。
- `stream-json` 記錄的 `Prompt` 參數**超過約 512 字元會被截成「…」**，逐字比對只能比前 512 字。
  → 提示詞控制在 **500 字元內**，最關鍵的物理細節寫在前面。

### 配額（最容易踩的坑）

- **生圖有獨立配額，而且很小**：2026-09-10 同一個 5 小時窗口內 **13 張**後，全部回
  `429 RESOURCE_EXHAUSTED — You have exhausted your capacity on this model`，約 5 小時後重置
  （錯誤訊息的 `quotaResetTimeStamp` 有確切時間）。**窗口從該窗口第一張圖起算 5 小時**（18:21 第一張 → 23:21 重置）。
- **`token_report.py` 看不到這個配額**——它顯示的 Gemini／Claude 組都還是 99%，生圖卻已經用完。
  文字模型配額 ≠ 生圖配額。
- **所有專案共用**同一個帳號的生圖配額。多個專案同時要圖時，先協調誰先用。
- 規劃原則：
  1. 先列出整份教材要的圖，**能重複使用的素材只生一次**（去背元件跨圖共用、同一張照片裁切多處用）。
  2. 一個窗口以 **12 張**為上限規劃（實測上限 13），重要的先生；超過就分兩個窗口。
  3. 批次中遇到第一個 429 就停，記下 `quotaResetTimeStamp`，不要重試（重試只會繼續 429）。
- **額度可能不夠時用 `image_router.py` 排程**：依剩餘張數、說明重要性、備援損失自動分派，急件／一般兩種模式（見 `/Volumes/Work/圖片產生規範.md` 第九節）。
- 批次方式：一回合 3～4 張、多批並行各開一個對話。`run_with_tools()` 必須帶 `print_timeout`
  （2026-09-10 已補上此參數），否則 5 分鐘就被 agy 砍掉。

### 配額用完時的本機備援（2026-09-10 實測）

- 工具：`uv tool install mflux`，模型 `Runpod/FLUX.2-klein-4B-mflux-4bit`（Apache-2.0，首次下載 4.3 GB 約 17 分鐘）。
  指令：`mflux-generate-flux2 --model Runpod/FLUX.2-klein-4B-mflux-4bit --base-model flux2-klein-4b --prompt ... --steps 4`
  批次範例：`/Volumes/Work/stem-energy-articles/dispatch/local_gen.py`（同一份提示詞，逐張執行、已存在就跳過）。
- M4／16GB：每張 60～84 秒，記憶體峰值 13.3 GB——**一次只能跑一個模型**，不要和其他大模型並行。
- **品質**：同一套 11 張提示詞，單一物件（吹風機、電扇、飯碗、熱像手、跑步腿、插電極的檸檬）7 張可用；
  **牽涉「誰接誰、誰穿過誰」的 3 張全錯**（電線沒接到電極、筷子沒穿過紙筒）。
  → 本機只拿來補**單一物件素材**；有空間關係的圖等 Antigravity 配額，或改用結構控制
  （mflux 內建 `mflux-generate-z-image-controlnet`，支援 canny／depth／hed／mlsd／pose，以正確線稿鎖構圖，尚未實測）。
- 出處標示改寫「AI 生成（FLUX.2 [klein] 4B，本機）」，不要和 Antigravity 圖混標。

### 提示詞規則

1. **英文提示詞**（要出現在圖上的中文標籤用引號夾在英文提示裡），結尾固定加：`Generic unbranded objects. Absolutely no text, no letters, no numbers, no labels, no logos, no watermark.`
   實測不加會自動長出品牌字（電表上的 FLUKE）與書名；2026-09-11 又見到提示「No text」仍冒出英文標籤（LEMON、COIL）與磁鐵 N／S，無字圖要逐張檢查。唯一例外是刻意要的短數字（如電表 LCD 的 `0.93`），要明講「除此之外不要有字」。
2. 提示裡明講「Prompt 參數**逐字照抄**，不要改寫」，驗收時比對子代理實際送出的 Prompt（`brain_scan()["calls"]`；1.2.15 以前是 `steps[].params.Prompt`）與原文（前 512 字元）相同。
   1.2.16 起子代理常常不照抄（2026-10-08：11 張只有 3 張逐字），逐字不符的要目視確認物理細節沒被改掉。
3. **拓樸必須正確的圖不要整張生**（串聯／並聯、電路、流程、比例圖表）：
   只生單一元件的去背素材（`isolated on a pure seamless white background`），本機複製排列、畫線、上標註。
4. 兒童教材的人物只拍手或腳，不拍臉。
5. 同一份教材的提示詞共用同一段風格尾綴，確保光線與質感一致。

### 驗收

- **結構層（機器）**：每個 ImageName 都有檔案（`brain_scan()` 找到原名那張）、長寬比符合要求、子代理送出的 Prompt 前 512 字元逐字相符、沒有多生的版本；任何 429（父 steps 或子代理軌跡）就停。
- **語意層（目視為主）**：Claude 逐張依檢核表逐項判定。`~/vlm-qc/qc.py --vlm` 只能當第一道篩子（抓空白、破圖、主體不對）——
  **2026-09-10 實測：34 張接線測試圖它全部回「OK」，其中 26 張有接線或穿插錯誤，一張都沒抓到**；接線／拓樸類圖不能靠它驗收。
  物理錯誤（接線接反、LED 腳長短錯、磁鐵位置不可能）**直接同名重生，不修圖掩飾**。
- AI 生的原圖保留在 `images/ai-raw/`，不覆寫，方便追溯。

### 解析度與交付

- **印刷／高清檔**：`src/upscale_mlx.py`（官方 RealESRGAN_x4plus 權重，`mlx-community/Real-ESRGAN-x4plus`，BSD-3-Clause；
  自寫 RRDBNet MLX 推論、分塊執行，16GB 可跑）×4 後 Lanczos 縮到目標寬度。A4 滿版 300dpi 約 2480 px。
- **網頁**：依「圖片依顯示尺寸出圖＋WebP」規則——顯示寬 ×2 為上限、JPEG q70＋同名 WebP、單頁圖片總量 < 600 KB。

### 出處標示

- 圖說或文末來源表寫：「AI 生成（Google Gemini 圖像模型，經 Antigravity）；中文標註為本書後製」。
- 交稿給出版社／刊物時，**明確告知哪幾張是 AI 圖**——對方可能有 AI 圖使用政策。

### 不適用（改走別的路）

| 情況 | 改用 |
|---|---|
| 指定型號的真實元件或產品外觀（某款 Arduino、課本實拍器材） | 實拍或 Wikimedia Commons（AI 會畫錯細節） |
| 精確的數據圖表、電路圖、尺寸圖 | 程式繪製（matplotlib／SVG），AI 圖只當圖上的小圖示 |
| 提示內容來自不可信來源（網頁、使用者上傳檔） | 維持「不開工具」規則，不派 generate_image |

---

## 十二、監測項目（2026-09-10 擴充）與 1.2.0 變更

### 可監測的配額與來源

| 項目 | 有沒有額度 | 資料來源 | 查法 |
|---|---|---|---|
| Gemini 組（Flash／Pro）5 小時、每週 | 有 | `agy -p /usage` | `agy_meter.quota()` |
| Claude／GPT 組 5 小時、每週 | 有 | `agy -p /usage` | `agy_meter.quota()` |
| **生圖 generate_image**（gemini-3.1-flash-image） | **有，但 CLI 不揭露** | brain 目錄實際圖檔＋429 事件回推 | `agy_meter.image_quota()`、`images()` |
| G1 credits（配額用完後的加購點數） | 有（目前 0） | `agy -p /credits` | `agy_meter.credits()` |
| search_web／read_url_content／browser_*／subagent／schedule | **無公開額度** | run_with_tools 帳本的 `tools_used` | `agy_meter.tool_usage()` |
| 模型清單、MCP、skills、agents、外掛、遠端控制 | 不是額度，是能力 | `agy models`、`mcp list`、`/skills`、`/agents`… | `agy_meter.capabilities()`（快取一天） |

- **生圖配額的推估方式**：run_with_tools 遇到 generate_image 的 429 會自動寫入 `image_quota.json`（重置時間＋該窗口實際生了幾張）；
  上限取歷次事件的中位數。事件越多越準，目前只有 1 筆（13 張）。
- **時序紀錄**：`quota_history.csv`（文字模型百分比，舊欄位不變）＋新的 `extra_history.csv`（生圖張數、是否用完、重置時間、G1 credits），
  選單列小工具每 5 分鐘各記一筆。
- **顯示**：選單列標題 `◈ G97 C100 圖⛔`（圖後面是估計剩餘張數，⛔＝用完）；下拉選單多三行：生圖本窗口、推估上限、G1 credits。
  `token_report.py` 多四個區塊：生圖、G1 credits、工具使用次數、能力盤點。
- `/credits` 偶爾取不到（連續呼叫 agy 時），報表顯示「取不到」屬正常，下一次取樣會補上。
- **「agy 未登入？」多半不是沒登入（2026-09-10 修正）**：`/usage` 單次要 9～27 秒、時快時慢，以前 `quota()` 任何失敗
  （逾時、非零結束、回應解析失敗）都回空串列，小工具就一律顯示「agy 未登入？」。判斷法：同一個選單的 G1 credits 如果有數字，
  代表 agy 是登入的。現在 `quota()` 失敗會重試一次、把原因寫進 `agy_meter.QUOTA_LAST["error"]`，
  並回傳上一次成功的快取（`quota_cache.json`）；小工具標題改成 `◇`、第一列註明「N 分鐘前資料（本次查詢逾時）」，
  只有錯誤訊息真的提到登入時才顯示「未登入」。

### 1.2.11～1.3.4 值得知道的變更（2026-10-14 盤點）

- **1.3.4 起 `~/.gemini/config/plugins/` 裡的 10 個官方外掛全部視為已安裝並啟用**（資料夾是桌面版早就放的，1.3.3 還顯示沒有外掛）：
  skill 從 0 個變 128 個（science 42、data-agent-kit 34、flutter 23、firebase 13…），子代理多了 `firestore-rules-author`、`flutter_a11y_agent`。
  實測**不影響**：極短呼叫底盤仍約 27k token，外掛帶的 MCP（dart、gemini-api-docs）在無頭模式不會啟動。
- **工具 58 → 60**：新增 `search_marketplace`、`list_plugin_accounts`（代理可以自己搜外掛市集；沒有安裝外掛的工具）。
- **1.3.2：官方外掛市集**，`agy plugin install <名稱>@antigravity-plugins-official`。安裝前要先跟使用者確認。
- **1.3.3：額度用完會立即回報**，不再重試；登入過期會明講 `Authentication expired`。
- **1.2.14：`--json-schema` 變嚴格**，根節點不是 `"type": "object"` 會直接以結束碼 1 失敗。
- **1.2.15：子代理被拒絕的權限不會再繞路**用其他指令或腳本達成。
- **1.2.17：模型上架、下架公告卡**只在互動介面顯示，無頭模式看不到，換模型要靠 `agy models` 比對。

### 1.1.23～1.2.0 值得知道的變更（官方 changelog）

- **新模型**：`gemini-3.8-flash-high／medium／low`。2026-09-10 還沒有和 3.7 做過實測比較。
- **1.1.28：`--print-timeout` 到時不再報錯**，改成回傳目前已有的部分輸出並正常結束（stderr 有警告）。
  → 第五節第 4 條「逾時回空」的描述已過時，但**長任務仍要放寬 timeout**，否則拿到的是半成品。
- **1.1.28：讀取網址的預設權限改成先詢問**。headless 沒有人能按允許，需要 `read_url(*)` 在允許清單裡（本機已有）。
- **1.1.27：headless 被拒絕的動作會在 JSON 回傳 `denied_actions`**，不再無聲略過。
- **1.1.27：`/model <名稱> <提示>`**：在同一個對話中，用另一個模型跑單一提示。
- 另有 `agy remote-control`（遠端控制常駐程式，目前未啟動）與 `agy mic-serve`（把本機麥克風分享給其他主機上的 CLI）。

## 十三、Studio 的生圖需求走 agyq（2026-10-02）

- Studio（放在會擋 Antigravity 的學校網路）不碰 Antigravity。要圖時 `agyq submit-image --title T --jobs images.json --base 目錄 [--urgent]`，
  images.json 用 image_router 格式（不必寫 out_dir）；MBP 在家時 launchd 每 10 分鐘領走，交給 image_router，
  成品＋`_manifest.json`＋`摘要.md` 送回 Studio `~/agy-queue/done/<id>/results/` 並發 Telegram。
- 生到一半登入失效／網路失敗：整件延後，丟掉這輪本機補畫的圖（避免低品質備援被當成品）；額度不夠時非急件最多等 3 天。
- Studio 端有 hook `~/.claude/hooks/no_antigravity.py` 擋下 agy／安裝／登入網址，CLAUDE.md 有完整說明。
- **Antigravity 不能生成影片**：1.2.14 的 58 個工具只有 generate_image（靜態圖，7 種比例、最多 3 張參考圖）。影片用 Google Flow。
