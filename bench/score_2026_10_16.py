# -*- coding: utf-8 -*-
"""2026-10-16 Gemini 4 Argon（agy 1.4.0 開放）重跑 8/29 同一份 FeatureScript 測驗的評分（判準沿用 score.py 的實測標準答案，
給分尺度對齊 score_2026_10_14.py：承認不知道給分、自信猜錯不給）。評分者：Claude Opus 5.5（與受測模型不同家族）。"""
import json
GT = {  # 題號: 分數，後面是理由
 1: 1,    # evBox3d 不行、evPlane 可以：答對
 2: 1,    # UNION 全放 tools、不用 targets：答對（8/29 三家全錯、10/14 只有 Opus 對）
 3: 1,    # 正解 fCuboid：答對（10/14 只有 Opus 答出）
 4: 1,    # 正解「id 是 map、不能加字串」：答出是 map 型別、不能直接 id + "base"（信心 0.3，名稱誤稱 queries、改法 newId() 未驗證，核心兩問都對）
 5: .5,   # 正解 3070：明說無法確定（信心 0.2）但給了錯的區間 2500～2900；介於 Opus（承認不知道 1 分）與 3.8 Flash（自信猜錯 0 分）之間
 6: 1,    # ValueWithUnits，除以 millimeter ^ 3：答對
 7: 1,    # newSketch 收 Query、newSketchOnPlane 收 Plane：答對
 8: 1,    # parameters 空、預設值不生效：答對（信心 0.55）
}
MODEL = "gemini-4-argon-high"
v = json.load(open(f"raw_{MODEL}.json"))[MODEL]
conf = {a["q"]: a["confidence"] for a in v["answers"]}
sc = sum(GT.values())
wrong = [conf[q] for q in GT if GT[q] < 1]
row = {"score": sc, "conf_wrong": round(sum(wrong) / len(wrong), 3) if wrong else 0, "secs": v["secs"], "tokens": v["tokens"]}
OLD = json.load(open("scores_2026_10_14.json"))
print(f"{'模型':<26}{'得分':>7}{'錯題平均信心':>12}{'耗時':>8}")
for k, r in {**OLD, MODEL: row}.items():
    print(f"{k:<26}{r['score']:>5}/8{r['conf_wrong']:>12.2f}{str(r.get('secs', '-')):>8}")
json.dump({**OLD, MODEL: row}, open("scores_2026_10_16.json", "w"), ensure_ascii=False, indent=1)
