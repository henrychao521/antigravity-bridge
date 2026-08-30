# Antigravity 派工規範

> 貼給新對話視窗用。搭配 `/Users/Shared/antigravity-bridge/` 底下的操作檔案。
> 最後更新：2026-08-29

## 一、這是什麼

Antigravity 是 Google 的代理式 AI CLI（`agy`），**走 Google AI Pro 訂閱額度，不另外計費**。
它可以被 Claude Code 當成第二個 LLM 使喚：分攤工作、或做多方交叉驗證。

執行檔：`~/.local/bin/agy`（v1.1.22）　憑證：沿用 Antigravity app 的 Google 登入，機器層級 keyring

## 二、模型選擇

`agy models` 實測可用清單（2026-08-29）：

| 模型 id | 配額組 | 定位 |
|---|---|---|
| `gemini-3.7-flash-high` / `-medium` / `-low` | Gemini | **最新世代 Flash**，快、便宜 |
| `gemini-3.6-flash-*`、`gemini-3.5-flash-*` | Gemini | 舊世代 Flash |
| `gemini-3.1-pro-high` / `-low` | Gemini | **Pro 推理層**，長文與複雜任務用這個 |
| `claude-sonnet-4-6` | Claude/GPT | 異家族觀點 |
| `claude-opus-4-6-thinking` | Claude/GPT | **最高能力**，但配額成本 37 倍 |
| `gpt-oss-120b-medium` | Claude/GPT | 第三家族觀點 |

### 實測比較（2026-08-29，8 題有標準答案的 FeatureScript 知識測驗）

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

**沒有 gemini-3.7-pro。** 3.7 只出到 Flash；Pro 最新是 3.1。所以「更高認知能力」有兩條路：

- **同一個便宜配額組內** → `gemini-3.1-pro-high`（本規範的預設主力，25 頁教學報告就是它寫的）
- **要真正更強** → `claude-opus-4-6-thinking`，但**只能偶爾用**（見成本表）

模型的 `-high/-medium/-low` 後綴就是推理強度，**不需要另外加 `--effort`**。
**沒有「設定預設模型」的設定檔選項**，每次呼叫都要用 `--model` 明確指定。

## 三、成本模型（實測校準）

同樣約 26–29k tokens 的一次呼叫：

| 模型 | 吃掉 5 小時配額 | 一個窗口約可跑 |
|---|---|---|
| `gemini-3.7-flash-high` | 0.10% | **約 1,025 次** |
| `claude-opus-4-6-thinking` | 3.59% | **約 24 次** |

**差 37 倍。** 所以：

- 批量、機械性、可容錯 → Gemini 組，等於免費
- 需要異家族觀點的交叉驗證 → Claude/GPT 組，一個窗口約 24 次，省著用

派工前先跑 `python3 /Users/Shared/antigravity-bridge/token_report.py` 看剩餘額度。
選單列有常駐小工具顯示 `◈ G99 C87`（Gemini 組／Claude·GPT 組的 5 小時窗口剩餘 %）。

## 四、基本用法

```bash
~/.local/bin/agy -p "提示" --model gemini-3.1-pro-high --output-format json
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

**4. 一律包 timeout，抓 60 分鐘。** 實測延遲 2.4 秒 ～ 3,280 秒（55 分鐘）都出現過。

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
                  model="gemini-3.1-pro-high", max_rounds=3)
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
