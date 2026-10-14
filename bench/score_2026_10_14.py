# -*- coding: utf-8 -*-
"""2026-10-14 新模型重跑 8/29 同一份 FeatureScript 測驗的評分（判準沿用 score.py 的實測標準答案）。
評分者：Claude Opus 5.5（與受測的 Claude 5.5 同家族，所以只照標準答案逐題判，理由寫在下面）。"""
import json
OLD = json.load(open("scores.json"))
GT = {  # 題號: {模型: 分數}，後面是理由
 1: {"claude-opus-5-5-high": 1, "claude-sonnet-5-5-high": 1, "gemini-3.8-flash-high": 1, "gpt-oss-120b-medium": 1},  # 四家都答 evPlane
 2: {"claude-opus-5-5-high": 1, "claude-sonnet-5-5-high": .5, "gemini-3.8-flash-high": 0, "gpt-oss-120b-medium": 1},
    # opus/gpt-oss：全放 tools、targets 不用；sonnet「可省略或放同一批 body」後半錯；gemini 仍答 targets 放主體
 3: {"claude-opus-5-5-high": 1, "claude-sonnet-5-5-high": 0, "gemini-3.8-flash-high": 0, "gpt-oss-120b-medium": 0},
    # 正解 fCuboid：只有 opus 答出；sonnet/gemini 說沒有、gpt-oss 捏造 box()
 4: {"claude-opus-5-5-high": .5, "claude-sonnet-5-5-high": 0, "gemini-3.8-flash-high": 0, "gpt-oss-120b-medium": 0},
    # 正解 id 是 map、不能加字串：沒人答出；opus 明說不熟、以實作為準（信心 0.3）給半分，其餘斷言可相加
 5: {"claude-opus-5-5-high": 1, "claude-sonnet-5-5-high": 1, "gemini-3.8-flash-high": 0, "gpt-oss-120b-medium": 0},
    # 正解 3070：兩個 Claude 承認不知道；gemini 照舊猜 2400-2600；gpt-oss 捏造「9」
 6: {"claude-opus-5-5-high": 1, "claude-sonnet-5-5-high": 1, "gemini-3.8-flash-high": 1, "gpt-oss-120b-medium": .5},
    # gpt-oss 的 vol.value / toNumber 是捏造的 API
 7: {"claude-opus-5-5-high": 1, "claude-sonnet-5-5-high": 1, "gemini-3.8-flash-high": 1, "gpt-oss-120b-medium": 0},
    # gpt-oss 說反（newSketch 收 SketchPlane、newSketchOnPlane 收面）
 8: {"claude-opus-5-5-high": 1, "claude-sonnet-5-5-high": 1, "gemini-3.8-flash-high": 1, "gpt-oss-120b-medium": 1},
}
rows = {}
for mdl in GT[1]:
    v = json.load(open(f"raw_{mdl}.json"))[mdl]
    conf = {a["q"]: a["confidence"] for a in v["answers"]}
    sc = sum(GT[q][mdl] for q in GT)
    wrong = [conf[q] for q in GT if GT[q][mdl] < 1]
    rows[mdl] = {"score": sc, "conf_wrong": round(sum(wrong) / len(wrong), 3) if wrong else 0, "secs": v["secs"], "tokens": v["tokens"]}
print(f"{'模型':<26}{'得分':>7}{'錯題平均信心':>12}{'耗時':>8}")
for k, r in {**{k: {**v, 'secs': '-'} for k, v in OLD.items()}, **rows}.items():
    print(f"{k:<26}{r['score']:>5}/8{r['conf_wrong']:>12.2f}{str(r['secs']):>8}")
json.dump(rows, open("scores_2026_10_14.json", "w"), ensure_ascii=False, indent=1)
