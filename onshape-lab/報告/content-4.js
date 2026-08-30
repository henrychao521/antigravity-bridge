// 陸、驗收結果　柒、操作準則　附錄
const L = require('./lib');
const { docx, P, H1, H2, H3, LI, Box, T, Caption, Cite } = L;
const { Fig } = require('./imgs');
const fs = require('fs'), path = require('path');

const ch9 = [
  H1('玖、給後來者的操作準則'),

  P('以下十條是本次實驗壓縮後的結論，可直接照做。前七條關於 FeatureScript 與成本，後三條關於驗證設計——後者更重要，因為它們決定你會不會在不知情的狀況下寫出錯的東西。'),

  ...Box('一、版本標頭以實測為準', [
    [{ t: '先跑一次 test_featurescript，看回傳的 libraryVersion（本次為 3070），標頭與 import 版本都用它。' },
     { t: '不要相信模型寫的版本號', b: true },
     { t: '——初稿寫的是 2420，直接導致 no features found。' }],
  ]),

  ...Box('二、除錯迴圈用自建探測器，不要用 test_feature', [
    [{ t: '寫入 Feature Studio 後取 featurespecs，看找到幾個特徵。每次兩呼叫，是 test_feature 的一半，且訊號明確。' }],
  ]),

  ...Box('三、不要相信空輸出', [
    [{ t: 'put_featurescript 的說明宣稱會回報錯誤，實測對壞碼也回空字串。' },
     { t: '任何工具在你依賴它之前，先餵一個確知會失敗的輸入試它會不會叫。', b: true }],
  ]),

  ...Box('四、幾何驗證用「建模與量測合一」的 lambda', [
    [{ t: '以 test_featurescript 在單次呼叫內建模、量測、回傳數字，一次只花一次額度。lambda 內沒有 id，用 ' },
     { t: '["名字"] as Id', mono: true }, { t: ' 自建。' }],
  ]),

  ...Box('五、標準函式庫的事實去查文件或做實驗', [
    [{ t: '兩次關鍵病因模型都沒說中，第一次還給了四條言之鑿鑿但全錯的診斷。' },
     { t: '定位病因請用二分法：先把本體清空確認 precondition 無誤，再逐段加回。', b: true }],
  ]),

  ...Box('六、把不吃額度的工作全部外包', [
    [{ t: '出題、寫初稿、產生假設清單、改寫重構、文件草擬——這些交給訂閱制的代理，額度不用會過期。真正稀缺的是 Onshape 的年度呼叫次數。' }],
  ]),

  ...Box('七、每次呼叫都要留痕', [
    [{ t: '記錄工具名稱、參數、完整輸出。本次曾因為只存了前 300 字元，被迫重跑一次四呼叫的測試——' },
     { t: '同一份資訊付了兩次錢。', b: true }],
  ]),

  ...Box('八、要有可打開的產物', [
    [{ t: '記憶體中算完就丟的驗證等於沒有驗證。務必留下' },
     { t: '任何人都能打開的網址', b: true },
     { t: '，並且自己先打開一次——工具回報「已建立」與「它還在」是兩件事。' }],
  ]),

  ...Box('九、量測要有第二條獨立通道', [
    [{ t: '同一支程式量測自己產生的東西，錯了也看不出來。本案的做法是：FeatureScript 內量一次、REST 端點量一次，兩者差值再用解析解對證。' }],
  ]),

  ...Box('十、複驗要讓對方自己動手', [
    [{ t: '把結論交給另一個模型改寫，得到的是同一個盲點的第二種寫法。' },
     { t: '要它自己連線、自己操作、自己撞牆', b: true },
     { t: '，它的結論才有獨立性，也才可能給出比你更好的證據。' }],
  ]),

  H2('一、適用邊界'),

  P('本報告的實驗對象是單一自訂特徵，規模不大。若要處理需要跨多個 Feature Studio、或涉及大量幾何反覆試誤的題目，2,500 次的年度額度會相當吃緊——建議先以本文的方法量測該類題目的實際單價，再決定是否升級方案。'),

  P('另需說明：本次全部驗證都在一個專為此建立的暫存文件內進行，未觸及既有設計檔。以代理式 AI 操作 CAD 時，這是最基本的防護——不論權杖的權限範圍為何，把工作區隔離開來都是應該的。'),
];

// 附錄：v5 原始碼
const codeLines = fs.readFileSync(
  path.join(__dirname, '..', 'rounds', 'v5.fs'), 'utf8').split('\n');
const appendix = [
  H1('附錄　smartBoss 完整原始碼'),
  P('以下為通過全部驗收的版本（v5）。兩處關鍵修正已在程式碼中以註解標示。'),
  ...codeLines.map((line) => new (require('./lib').docx.Paragraph)({
    children: [new (require('./lib').docx.TextRun)({
      text: line || ' ', size: 17, font: L.font(L.F_MONO), color: L.C_INK })],
    spacing: { line: 240, after: 0 },
  })),
  Caption('程式碼另存於 github.com/henrychao521/antigravity-bridge 的 onshape-lab/rounds/v5.fs'),
];
module.exports = { ch9, appendix };
