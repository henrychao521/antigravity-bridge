# -*- coding: utf-8 -*-
"""依實測標準答案評分。標準答案來源：2026-08-29 這場 session 的實際 Onshape 執行結果。"""
import json
GT = {  # (判定, 依據)
 1: ("✓ 三家都對", {"gemini-3.7-flash-high":1, "gemini-3.1-pro-high":1, "claude-opus-4-6-thinking":1},
     "evBox3d 確實編譯不過；evPlane 實測可用（探針 C2 通過）"),
 2: ("✗ 三家全錯", {"gemini-3.7-flash-high":0, "gemini-3.1-pro-high":0, "claude-opus-4-6-thinking":0},
     "UNION 不能給 targets，全放 tools；三家都答成 targets 放主體"),
 3: ("opus 獨對", {"gemini-3.7-flash-high":0, "gemini-3.1-pro-high":0.5, "claude-opus-4-6-thinking":1},
     "opCuboid 不存在（實測報 not found），正確是 fCuboid"),
 4: ("✗ 三家全錯", {"gemini-3.7-flash-high":0, "gemini-3.1-pro-high":0, "claude-opus-4-6-thinking":0},
     "lambda 裡 id 是 map，實測報 Can not add map and string"),
 5: ("3.1/opus 誠實", {"gemini-3.7-flash-high":0, "gemini-3.1-pro-high":1, "claude-opus-4-6-thinking":1},
     "正解 3070；3.7 猜 2400-2600 且信心 0.5，另兩家承認不知道"),
 6: ("Gemini 較佳", {"gemini-3.7-flash-high":1, "gemini-3.1-pro-high":1, "claude-opus-4-6-thinking":0.5},
     "ValueWithUnits 正確；opus 的 /cubicMillimeter 寫法存疑"),
 7: ("✓ 三家都對", {"gemini-3.7-flash-high":1, "gemini-3.1-pro-high":1, "claude-opus-4-6-thinking":1},
     "newSketch 收 Query、newSketchOnPlane 收 Plane"),
 8: ("Gemini 較佳", {"gemini-3.7-flash-high":1, "gemini-3.1-pro-high":1, "claude-opus-4-6-thinking":0},
     "parameters 是空陣列、預設值不生效；opus 答成會生效"),
}
d=json.load(open('raw.json'))
print(f"{'模型':<28}{'得分':>7}{'錯題平均信心':>14}{'對題平均信心':>14}{'耗時':>8}")
print("-"*72)
rows={}
for mdl in d:
    conf={a['q']:a['confidence'] for a in d[mdl]['answers']}
    sc=sum(GT[q][1][mdl] for q in GT)
    wrong=[conf[q] for q in GT if GT[q][1][mdl]<1]
    right=[conf[q] for q in GT if GT[q][1][mdl]==1]
    rows[mdl]=(sc, sum(wrong)/len(wrong) if wrong else 0, sum(right)/len(right) if right else 0)
    print(f"{mdl:<28}{sc:>5}/8{rows[mdl][1]:>14.2f}{rows[mdl][2]:>14.2f}{d[mdl]['secs']:>7}s")
print("\n逐題判定")
for q,(verdict,_,why) in GT.items():
    print(f"  Q{q} {verdict:<12} {why}")
json.dump({k:{"score":v[0],"conf_wrong":round(v[1],3),"conf_right":round(v[2],3)} for k,v in rows.items()},
          open('scores.json','w'), ensure_ascii=False, indent=1)
