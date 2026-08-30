# Onshape × 雙代理實驗歷程

**日期**：2026-08-29　**題目**：smartBoss 自訂特徵（選平面 → 長定位柱 → 布林聯集 → 根部圓角）
**分工**：Antigravity（Gemini）出題與寫程式，不吃 Onshape 額度；Claude 負責送驗、量測、除錯。

## 額度帳

| 項目 | 數字 |
|---|---|
| 起始 → 結束 | used 360 → **451**（限額 2,500，剩 2,049） |
| 本輪消耗 | **91 次**（第一階段 75 次＋第二階段幾何驗證 16 次；含 MCP 工具呼叫與直接 REST 呼叫） |
| 週期 | 2026-02-14 ~ 2027-02-14，`overageEnabled: false`（用完硬停） |

### 各工具的實際單價（實測，非文件記載）

| 工具 | 每次 API 呼叫數 |
|---|---|
| `test_featurescript`（跑 lambda） | 1 |
| `search_featurescript_documentation` | 1 |
| `get_api_usage` | 1 |
| `create_feature_studio` | 1 |
| **`test_feature`（寫進 Feature Studio 再評估）** | **4** |
| 自建探測器（REST：PUT 內容 + GET featurespecs） | 2 |

**結論：除錯迴圈不要用 `test_feature`。**自建的 REST 探測器只要一半成本，而且會回報「找到幾個特徵」，
比 `test_feature` 那句沒有行號的錯誤訊息更有定位價值。

## 逐輪紀錄

| 輪次 | 動作 | 結果 | 學到什麼 |
|---|---|---|---|
| 1 | Antigravity 產 v1，原樣送測 | `no features found` | 它宣告 `FeatureScript 2420`，但實際 libraryVersion 是 **3070** |
| 2 | 只改版本號 → v2 | 仍失敗 | 版本不是唯一病因，且此錯誤訊息**沒有行號** |
| 3 | 送最小空特徵當對照組 | ✅ 通過 | harness 與版本都正常，問題在我們的程式碼 |
| 4 | 語法探針（lambda 測 `+=`、`append`、結構欄位賦值） | ✅ 全部合法 | 排除三個假嫌疑 |
| 5 | 請 Antigravity 診斷 | 給了 4 條「確定錯誤」 | **全部是幻覺**（見下） |
| 6 | 用官方文件查證 | `opFillet` 確實存在 | 不可採信單一模型對 std API 的記憶 |
| 7 | `put_featurescript` 取編譯錯誤 | 回傳空字串 | 疑似無錯 → **但這是假訊號** |
| 8 | **工具校驗**：故意送壞碼給 `put_featurescript` | **仍回傳空字串** | 該工具說明宣稱「return errors, if any」，**實際不回報**；第 7 輪結論作廢 |
| 9 | 自建 REST 探測器（featurespecs 數量當訊號） | 可用 | 特徵數 0 = 沒編譯成功 |
| 10 | 二分：本體清空 / 只留迴圈 | 清空✅、只留迴圈❌ | precondition 完全正常，**`if` 與 `Query` 參數都合法** |
| 11 | 迴圈內逐項切 | `evaluateQuery`✅ `evPlane`✅ **`evBox3d`❌** | 找到真兇 |
| 12 | `evBox3d` 加 `tight` 參數 | 仍❌ | 不是參數問題，是**符號在 `geometry.fs` 下不可見** |
| 13 | 改 `evFaceTangentPlane` | ✅ | 確定替代方案 |
| 14 | 寫 v4（含 `newSketchOnPlane` 修正） | ✅ **編譯通過，找到特徵** | 完成第一階段 |

## Antigravity 的 4 條診斷 vs 事實

| 它的主張 | 事實 |
|---|---|
| `precondition` 內不能用 `if`，會語法錯誤 | ❌ 錯。第 10 輪證明含 `if` 的 precondition 正常編譯 |
| `opFillet` 不存在，應改用 `opBlend` | ❌ 錯。官方文件有 `opFillet` 及其 `allowEdgeOverflow`/`smoothCorners` 參數 |
| 圓角半徑鍵名應為 `blendRadius` | ❌ 錯，衍生自上一條 |
| `opBoolean` 的鍵名應為 `bOperationType` | ❌ 錯。且錯誤根本不在 boolean 區塊（第 10 輪已排除） |
| （真正的病因：`evBox3d`） | 它完全沒提到 |

**這是本次最重要的一課**：LLM 對冷門 DSL 的標準函式庫記憶不可靠，而且**錯得很有自信**
（四條都寫成「確定錯誤」並附上言之成理的編譯期原理）。有效的做法是**二分實驗**，不是問模型。

諷刺的是，Antigravity 自己在出題時點名「應該用 `evFaceTangentPlane`」，
實作時卻改用了 `evPlane + evBox3d`——**它知道正確做法，但寫程式時沒有照做**。

## 第二階段：幾何驗證

改用 `test_featurescript` 跑「建模 + 量測」合一的 lambda——**一次呼叫 1 次額度**，
比 `create_geometry` 造出實體再另外量測便宜得多。基體 100×100×20 mm，柱體 ⌀20×15 mm。

| 輪次 | 動作 | 結果 | 學到什麼 |
|---|---|---|---|
| 15 | 完整流程（含 opBoolean） | `@opBoolean: BOOLEAN_BAD_INPUT` | 編譯過了，改成建模層級錯誤 |
| 16 | 印出布林前的中間狀態 | 6 面／法線含 (0,0,1)／頂面 1／extrude 產 1 body／共 2 body | 輸入完全正確，問題在 opBoolean 本身 |
| 17 | 假設「僅面接觸」→ 柱體下沉 1mm 製造干涉 | 仍 `BOOLEAN_BAD_INPUT` | 假設被推翻 |
| 18 | **UNION 時不給 `targets`，全放 `tools`** | ✅ 成功 | **真因**：`targets` 只用於 SUBTRACTION／INTERSECTION |
| 19 | 加圓角，量交界邊與面數 | 交界邊 1、面數 8→9 | `qEntityFilter(qCreatedBy(booleanId), EntityType.EDGE)` 能正確追蹤新邊 |
| 20 | 把修正寫回特徵 → v5 | ✅ 編譯通過 | 完成 |

### 驗收結果（全數通過）

| 標準 | 預期 | 實測 | |
|---|---|---|---|
| 體積（關圓角） | `100·100·20 + π·10²·15` = 204712.389 mm³ | 204712.389 mm³ | ✅ 誤差 0.00000% |
| 面數（關圓角） | 6 + 2N = 8 | 8 | ✅ |
| 面數（開圓角） | 6 + 3N = 9 | 9 | ✅ |
| Part 數 | 1 | 1 | ✅ |

## 總帳

- 額度：**360 → 451，共 91 次**，剩 2,049
- 兩個真正的病因都**不是**模型診斷出來的，是二分實驗找到的：
  1. `evBox3d` 在 `geometry.fs` 下編譯不過 → 改 `evFaceTangentPlane`
  2. `opBoolean` 做 UNION 時給了 `targets` → 移除，全放 `tools`
- 產出：`rounds/v5.fs`（可用的 smartBoss 特徵）、`probe.py`（每次 2 呼叫的編譯探測器）
- 暫存文件：`FS-MCP Lab (agent scratch)`，Feature Studio `SmartBossLab`

## 給後來者的操作準則

1. **版本標頭用 `test_featurescript` 回傳的 `libraryVersion`**（目前 3070），不要相信模型寫的版本號。
2. **除錯迴圈用自建 REST 探測器（2 呼叫），不要用 `test_feature`（4 呼叫且無行號）。**
3. **不要相信 `put_featurescript` 的空輸出**——它對壞碼也回空。
4. **幾何驗證用 `test_featurescript` 跑「建模+量測」合一的 lambda**，1 次呼叫拿到客觀數字。
5. **標準函式庫的事實去查文件或做實驗，不要問模型。**兩次關鍵病因模型都沒說中，
   而且第一次還給了 4 條言之鑿鑿但全錯的診斷。
6. 模型真正划算的用途：出題、寫初稿、產生假設清單——這些都不吃 Onshape 額度。

---

## 第三階段：補上驗證設計（2026-08-29 覆核後）

覆核指出初版有三個**結構性**缺陷——不是寫錯，是驗證方式留了洞：

| 缺陷 | 為什麼危險 | 修正 |
|---|---|---|
| 記憶體建模，沒有產物 | 所有數字只能靠轉述，沒人能查 | 以 REST 在自有文件建 Part Studio 並加入特徵，附可打開的網址 |
| 量測只有單一通道 | 量測方式與被量測對象共用同一段錯誤時，錯了也看不出來 | 三通道交叉驗證 |
| 讓另一個代理複述我的結論 | 它的資訊全來自我，結構上不可能反駁 → 放大盲點 | 給它自己的 MCP 連線，讓它自己動手 |

### 取得持久模型的三次嘗試

| 方法 | 結果 |
|---|---|
| `create_geometry` | 會建分支工作區，但**事後自我清理**；實測三個工作區全數被刪，網址失效 |
| `test_feature` | 只做求值，不留幾何 |
| **自行以 REST 在自有文件建 Part Studio + 加入特徵** | **成功且永久保留**，featureStatus: OK |

另一個坑：**API 加入特徵時 `parameters` 是空陣列**，definition 沒有任何鍵，
自訂 `LengthBoundSpec` 的預設值只在 UI 建立特徵時生效 → 示範特徵必須把尺寸寫死。

### 三通道交叉驗證結果

| 通道 | 執行者 | 建構方式 | 量測管道 | 體積 (mm³) |
|---|---|---|---|---|
| A | Claude | 草圖 + opExtrude | FeatureScript lambda 內 evVolume | 204712.389 |
| B | Claude | 同上加圓角、持久化 | REST massproperties | 204841.875 |
| C | **Antigravity** | **fCylinder 直造** | **自行連 MCP、獨立作業** | **204712.389** |

- A 與 C **不同代理、不同建構方式，數字完全相同**
- B − A = 129.486 mm³，等於 Pappus 定理算出的圓角體積解析解 129.486 mm³，**誤差 0.0000%**

模型網址（可直接打開）：
`https://cad.onshape.com/documents/1674ae64c50f46714b4101f1/w/06f6a9cd7bd466a776a9cd52/e/70920e24320830591d8f8b79`

### Antigravity 獨立作業的收穫

給它 `agy mcp add --header "Authorization: Bearer <token>" onshape <url>` 之後，它自己完成同一題，
撞到的坑與我**完全不同**（因為走不同路徑），且找到我沒找到的證據：

- 基元函式是 `f` 前綴（`fCuboid`／`fCylinder`），不是 `op` 前綴
- `test_featurescript` 的 lambda 裡 `id` **是 map 不是 Id**
- 它在官方文件裡直接找到 **`Target bodies are not used by UNION.`**——
  我是靠推翻假設才發現的，它有白紙黑字

### 額度

360 → **562**（本輪合計 202 次，剩 1,938）。第三階段 111 次，其中 Antigravity 獨立跑一輪佔大部分。
