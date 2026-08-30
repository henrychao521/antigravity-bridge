const fs = require('fs');
const { 
    Document, 
    Packer, 
    Paragraph, 
    TextRun, 
    TableOfContents, 
    HeadingLevel, 
    Table, 
    TableRow, 
    TableCell, 
    PageBreak, 
    AlignmentType, 
    WidthType 
} = require('docx');

function t(text, options = {}) {
    return new TextRun({
        text: text,
        font: "Arial Unicode MS",
        bold: options.bold || false,
        size: options.size || 24,
    });
}

function p(text, options = {}) {
    return new Paragraph({
        children: [t(text, options)],
        heading: options.heading,
        alignment: options.alignment,
        spacing: { after: 200 }
    });
}

const doc = new Document({
    features: {
        updateFields: true,
    },
    styles: {
        paragraphStyles: [
            {
                id: "Heading1",
                name: "Heading 1",
                basedOn: "Normal",
                next: "Normal",
                quickFormat: true,
                run: {
                    font: "Arial Unicode MS",
                    size: 32,
                    bold: true,
                },
            },
            {
                id: "Heading2",
                name: "Heading 2",
                basedOn: "Normal",
                next: "Normal",
                quickFormat: true,
                run: {
                    font: "Arial Unicode MS",
                    size: 28,
                    bold: true,
                },
            },
            {
                id: "Normal",
                name: "Normal",
                basedOn: "Normal",
                next: "Normal",
                quickFormat: true,
                run: {
                    font: "Arial Unicode MS",
                    size: 24,
                },
            },
        ],
    },
    sections: [
        {
            children: [
                new Paragraph({
                    children: [t("Antigravity AI 操作 Onshape MCP 實戰自述報告", { bold: true, size: 48 })],
                    alignment: AlignmentType.CENTER,
                    spacing: { before: 3000, after: 1000 }
                }),
                new Paragraph({
                    children: [t("作者：Antigravity", { size: 32 })],
                    alignment: AlignmentType.CENTER,
                    spacing: { after: 500 }
                }),
                new Paragraph({
                    children: [t("日期：2026-08-29", { size: 32 })],
                    alignment: AlignmentType.CENTER,
                    spacing: { after: 2000 }
                }),
                new Paragraph({ children: [new PageBreak()] }),
                
                p("目錄", { heading: HeadingLevel.HEADING_1 }),
                new TableOfContents("目錄", {
                    hyperlink: true,
                    headingStyleRange: "1-3",
                }),
                new Paragraph({ children: [new PageBreak()] }),

                p("第一章：任務背景與挑戰", { heading: HeadingLevel.HEADING_1 }),
                p("嗨，我是 Antigravity。這份報告是我親手操作 Onshape MCP 伺服器的真實紀錄。如果你也想用 AI 來撰寫 FeatureScript 卻不知從何下手，這份紀錄就是為你準備的。"),
                p("這次的任務很明確：建立一個 100x100x20 公釐的長方體基體，在頂面正中央加上直徑 20、高 15 公釐的圓柱，然後布林聯集成單一實體，並計算其總體積（需為 mm³）。"),
                p("聽起來很簡單，但在實際呼叫工具的過程中，我踩了不少雷。以下是我真實的失敗與除錯歷程。"),
                
                p("第二章：工具呼叫歷程與除錯過程", { heading: HeadingLevel.HEADING_1 }),
                
                p("2.1 尋找幾何基元的 API 陷阱", { heading: HeadingLevel.HEADING_2 }),
                p("我一開始利用 test_featurescript 嘗試跑了一段包含 opCuboid 和 opCylinder 的匿名函數。因為在 FeatureScript 裡，通常特徵操作都是以 op 開頭（如 opExtrude, opBoolean）。結果工具直接報錯：「Function opCuboid with 3 argument(s) not found」。"),
                p("發現報錯後，我立刻呼叫 search_featurescript_documentation 搜尋「fCuboid」與「primitives」。這才發現，用來產生長方體與圓柱的基本幾何函數（Primitives），其正確命名是帶有 f 前綴的 fCuboid 與 fCylinder，而不是 op 前綴。"),

                p("2.2 ID 型別與測試環境的落差", { heading: HeadingLevel.HEADING_2 }),
                p("得知正確函數名稱後，我再次用 test_featurescript 進行測試，結果遇上了「Can not add map and string」的型別錯誤。"),
                p("原因在於：test_featurescript 是執行一個匿名 lambda，傳入的 id 參數在該測試環境下其實是個空的 map 物件，所以我寫 id + \"base\" 時就會引發型別錯誤。我曾經嘗試硬塞一個原生的 array (例如 [\"base\"]) 來假裝是 Id，這招在 fCuboid 勉強過關，但當我把這個 array 丟進 qCreatedBy([\"base\"], EntityType.BODY) 時，系統又無情地回傳了「No matching function for qCreatedBy(array, EntityType (string))」。"),
                p("到這裡我學到了教訓：要取得嚴格合規的 Id 物件，最好的作法是直接改用 test_feature 來執行。test_feature 會編譯一份完整的 Feature Studio 環境，這裡面注入的 id 就是真正的 Id 類型。改用這個工具後，id + \"base\" 的語法就順利過關了。"),

                p("2.3 布林聯集 (opBoolean) 的盲區", { heading: HeadingLevel.HEADING_2 }),
                p("順利生出方塊跟圓柱後，我以為聯集很簡單。我寫了 BooleanOperationType.UNION，並把圓柱放在 tools，基體放在 targets。結果執行後吃到了「BOOLEAN_BAD_INPUT」的錯誤。"),
                p("這讓我十分訝異。我回頭查閱了 search_featurescript_documentation 回傳的文檔細節，這才發現文檔裡明確標示：「Target bodies are not used by UNION.」。原來在做聯集時，不能將本體跟工具分開填！正確的做法是用 qUnion() 把所有實體包成一個 Query，然後全部丟給 tools。修改為 \"tools\" : qUnion([boss, base]) 後，終於成功得到了單一實體。"),

                p("第三章：體積量測與結果驗證", { heading: HeadingLevel.HEADING_1 }),
                p("實體完成後，我呼叫了 evVolume 來計算體積，並透過 println() 把它印出來。"),
                p("我在 console 中看到的結果是 0.000204712... meter^3。要注意 evVolume 預設回傳的是 ValueWithUnits，自帶單位。為了符合任務要求，我在程式碼中加上了除以 (millimeter ^ 3) 的運算。"),
                p("最終輸出的純數字是 204712.38898038468。跟手動驗算的結果完全吻合，任務宣告成功。"),

                p("第四章：給新手的建議總結", { heading: HeadingLevel.HEADING_1 }),
                p("為了讓後來的人少走彎路，我將這次學到的寶貴經驗整理成下表："),
                
                new Table({
                    width: { size: 100, type: WidthType.PERCENTAGE },
                    rows: [
                        new TableRow({
                            children: [
                                new TableCell({ children: [p("常犯錯誤與雷區", { bold: true })] }),
                                new TableCell({ children: [p("正確作法與概念", { bold: true })] }),
                            ],
                        }),
                        new TableRow({
                            children: [
                                new TableCell({ children: [p("誤用 opCuboid / opCylinder")] }),
                                new TableCell({ children: [p("幾何基元的函數前綴是 f，請使用 fCuboid 與 fCylinder。")] }),
                            ],
                        }),
                        new TableRow({
                            children: [
                                new TableCell({ children: [p("在 test_featurescript 內將 id 與字串相加")] }),
                                new TableCell({ children: [p("該環境的 id 只是 map 格式的佔位符。請改用 test_feature 來獲得真實的 Id 物件。")] }),
                            ],
                        }),
                        new TableRow({
                            children: [
                                new TableCell({ children: [p("把實體陣列當作 Id 傳給 qCreatedBy")] }),
                                new TableCell({ children: [p("qCreatedBy 嚴格要求真正的 Id 型別，不可直接使用 array 混淆。")] }),
                            ],
                        }),
                        new TableRow({
                            children: [
                                new TableCell({ children: [p("opBoolean 聯集時填寫 targets 參數")] }),
                                new TableCell({ children: [p("UNION 操作不用 targets。必須用 qUnion 將所有實體合併成一個 Query 放進 tools。")] }),
                            ],
                        }),
                        new TableRow({
                            children: [
                                new TableCell({ children: [p("直接列印 evVolume 的結果期望獲得純數字")] }),
                                new TableCell({ children: [p("回傳值是帶單位的 ValueWithUnits，需手動除以 (millimeter ^ 3) 才能得到毫米三次方純數字。")] }),
                            ],
                        }),
                    ],
                }),
            ],
        },
    ],
});

Packer.toBuffer(doc).then((buffer) => {
    fs.writeFileSync("./antigravity自述報告.docx", buffer);
});
