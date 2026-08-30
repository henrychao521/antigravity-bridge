# -*- coding: utf-8 -*-
"""報告配圖：工程製圖語彙（細線、標註、單色強調），避免 AI 卡片風。"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, patches
import numpy as np

FP = "/Library/Fonts/Arial Unicode.ttf"
font_manager.fontManager.addfont(FP)
CJK = font_manager.FontProperties(fname=FP).get_name()
plt.rcParams.update({"font.family": CJK, "axes.unicode_minus": False})

INK, RULE, ACC, BAD, OK, MUTE = "#1b1f24", "#c8ced6", "#1f5fa8", "#b03a2e", "#1e7a46", "#6b7684"
DPI = 200

def save(fig, name):
    fig.savefig(f"figs/{name}", dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig); print("✓", name)

# ── 圖1：兩個代理的分工與成本邊界 ──────────────────────────
fig, ax = plt.subplots(figsize=(9.2, 4.6)); ax.axis("off")
ax.set_xlim(0, 10); ax.set_ylim(0, 5)
ax.add_patch(patches.Rectangle((0.15, 0.3), 4.4, 4.4, fill=False, ec=RULE, lw=1.1))
ax.add_patch(patches.Rectangle((5.45, 0.3), 4.4, 4.4, fill=False, ec=ACC, lw=1.6))
ax.text(2.35, 4.42, "不消耗 Onshape 額度", ha="center", fontsize=11.5, color=MUTE)
ax.text(7.65, 4.42, "每次呼叫都扣年度額度", ha="center", fontsize=11.5, color=ACC, weight="bold")
ax.text(2.35, 3.92, "Antigravity（Gemini）", ha="center", fontsize=13.5, weight="bold", color=INK)
ax.text(7.65, 3.92, "Claude + Onshape MCP", ha="center", fontsize=13.5, weight="bold", color=INK)
left = ["出題與驗收標準設計", "撰寫 FeatureScript 初稿", "產生假設清單", "改寫與重構", "文件草擬"]
right = ["送進 Onshape 編譯", "二分法定位病因", "幾何量測與驗收", "查官方文件查證", "額度記帳"]
for i, t in enumerate(left):
    ax.text(0.55, 3.35 - i * 0.55, "·", fontsize=15, color=MUTE)
    ax.text(0.85, 3.35 - i * 0.55, t, fontsize=11.5, color=INK, va="center")
for i, t in enumerate(right):
    ax.text(5.85, 3.35 - i * 0.55, "·", fontsize=15, color=ACC)
    ax.text(6.15, 3.35 - i * 0.55, t, fontsize=11.5, color=INK, va="center")
ax.annotate("", xy=(5.4, 2.5), xytext=(4.6, 2.5),
            arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.3))
ax.text(5.0, 2.68, "程式碼", ha="center", fontsize=10, color=INK)
ax.annotate("", xy=(4.6, 2.0), xytext=(5.4, 2.0),
            arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.3))
ax.text(5.0, 1.66, "錯誤訊息", ha="center", fontsize=10, color=INK)
save(fig, "fig1_arch.png")

# ── 圖2：各工具的實際 API 單價 ──────────────────────────────
fig, ax = plt.subplots(figsize=(8.6, 3.8))
names = ["test_featurescript\n(跑 lambda)", "查文件 /\nget_api_usage", "自建 REST\n探測器", "test_feature\n(寫入+評估)"]
vals = [1, 1, 2, 4]
cols = [OK, OK, ACC, BAD]
b = ax.barh(names, vals, color=cols, height=0.58)
for r, v in zip(b, vals):
    ax.text(v + 0.08, r.get_y() + r.get_height()/2, f"{v} 次", va="center", fontsize=12,
            color=INK, weight="bold")
ax.set_xlim(0, 4.9); ax.set_xlabel("每次呼叫消耗的 Onshape API 次數（實測）", fontsize=11.5)
ax.tick_params(labelsize=11); ax.spines[["top", "right"]].set_visible(False)
ax.spines[["left", "bottom"]].set_color(RULE); ax.grid(axis="x", color=RULE, lw=0.6, alpha=.6)
ax.set_axisbelow(True)
save(fig, "fig2_cost.png")

# ── 圖3：二分法定位過程 ────────────────────────────────────
fig, ax = plt.subplots(figsize=(9.0, 4.3)); ax.axis("off")
ax.set_xlim(0, 10); ax.set_ylim(0, 5.2)
steps = [("整支 v3", False), ("本體清空", True), ("只留迴圈", False),
         ("evaluateQuery + 空迴圈", True), ("+ evPlane", True), ("+ evBox3d", False)]
y = 4.6
for i, (label, ok) in enumerate(steps):
    mark, c = ("通過", OK) if ok else ("失敗", BAD)
    ax.add_patch(patches.Rectangle((0.5, y - 0.3), 6.2, 0.56, fill=False, ec=RULE, lw=1))
    ax.text(0.75, y - 0.02, label, fontsize=12, va="center", color=INK)
    ax.text(7.0, y - 0.02, mark, fontsize=12, va="center", color=c, weight="bold")
    if i < len(steps) - 1:
        ax.annotate("", xy=(3.6, y - 0.36), xytext=(3.6, y - 0.62),
                    arrowprops=dict(arrowstyle="-|>", color=MUTE, lw=1))
    y -= 0.72
ax.add_patch(patches.Rectangle((7.6, 0.42), 2.2, 0.62, fc="#FBEEEC", ec=BAD, lw=1.4))
ax.text(8.7, 0.73, "真兇 evBox3d", ha="center", va="center", fontsize=12,
        color=BAD, weight="bold")
ax.annotate("", xy=(7.55, 0.73), xytext=(7.15, 0.73),
            arrowprops=dict(arrowstyle="-|>", color=BAD, lw=1.4))
save(fig, "fig3_bisect.png")

# ── 圖4：驗收幾何（正視圖＋數據） ──────────────────────────
fig, (axg, axt) = plt.subplots(1, 2, figsize=(9.4, 3.9),
                               gridspec_kw={"width_ratios": [1.05, 1]})
axg.set_aspect("equal"); axg.axis("off")
axg.add_patch(patches.Rectangle((0, 0), 100, 20, fc="#EDF3FA", ec=INK, lw=1.4))
axg.add_patch(patches.Rectangle((40, 20), 20, 15, fc="#DCE7F4", ec=INK, lw=1.4))
axg.plot([37, 40], [20, 20], color=INK, lw=1.4)
axg.plot([60, 63], [20, 20], color=INK, lw=1.4)
for x0, x1, yv, lab in [(0, 100, -9, "100"), (40, 60, 41, "⌀20")]:
    axg.annotate("", xy=(x0, yv), xytext=(x1, yv),
                 arrowprops=dict(arrowstyle="<|-|>", color=MUTE, lw=1))
    axg.text((x0 + x1) / 2, yv + 2, lab, ha="center", fontsize=10.5, color=MUTE)
axg.annotate("", xy=(108, 0), xytext=(108, 20), arrowprops=dict(arrowstyle="<|-|>", color=MUTE, lw=1))
axg.text(111, 10, "20", fontsize=10.5, color=MUTE, va="center")
axg.annotate("", xy=(70, 20), xytext=(70, 35), arrowprops=dict(arrowstyle="<|-|>", color=MUTE, lw=1))
axg.text(73, 27.5, "15", fontsize=10.5, color=MUTE, va="center")
axg.set_xlim(-14, 124); axg.set_ylim(-24, 46)
axg.text(50, -20, "基體 100×100×20　定位柱 ⌀20×15（mm）", ha="center", fontsize=10.5, color=MUTE)

axt.axis("off"); axt.set_xlim(0, 10); axt.set_ylim(0, 10)
rows = [("體積", "204712.389 mm³", "誤差 0.00000%"),
        ("面數（關圓角）", "8", "＝ 6 + 2N"),
        ("面數（開圓角）", "9", "＝ 6 + 3N"),
        ("Part 數", "1", "布林聯集成功")]
axt.text(0.2, 9.3, "驗收結果", fontsize=13, weight="bold", color=INK)
axt.plot([0.2, 9.8], [8.9, 8.9], color=INK, lw=1.2)
for i, (k, v, note) in enumerate(rows):
    yy = 8.0 - i * 1.75
    axt.text(0.2, yy, k, fontsize=11.5, color=MUTE)
    axt.text(0.2, yy - 0.72, v, fontsize=14, color=INK, weight="bold")
    axt.text(5.6, yy - 0.72, note, fontsize=11, color=OK)
    axt.plot([0.2, 9.8], [yy - 1.18, yy - 1.18], color=RULE, lw=0.7)
save(fig, "fig4_geometry.png")

# ── 圖5：額度消耗 ──────────────────────────────────────────
fig, ax = plt.subplots(figsize=(8.6, 2.5))
ax.barh([0], [360], color=MUTE, height=0.5)
ax.barh([0], [91], left=[360], color=BAD, height=0.5)
ax.barh([0], [111], left=[451], color="#7A5195", height=0.5)
ax.barh([0], [1938], left=[562], color="#E8ECF1", height=0.5)
ax.set_xlim(0, 2500); ax.set_yticks([])
ax.set_xlabel("年度額度 2,500 次（2026-02-14 ～ 2027-02-14，用完硬停）", fontsize=11.5)
for x, t, c in [(180, "先前 360", "white"), (405, "除錯 91", "white"),
                (506, "驗證 111", "white"), (1530, "剩餘 1,938", INK)]:
    ax.text(x, 0, t, ha="center", va="center", fontsize=10.5, color=c, weight="bold")
ax.spines[["top", "right", "left"]].set_visible(False); ax.spines["bottom"].set_color(RULE)
ax.tick_params(labelsize=10.5)
save(fig, "fig5_budget.png")

# ── 圖6：三通道交叉驗證 ────────────────────────────────────
fig, ax = plt.subplots(figsize=(9.4, 4.0)); ax.axis("off")
ax.set_xlim(0, 10); ax.set_ylim(0, 5.4)
lanes = [
    (0.2, "通道 A", "Claude：草圖＋擠出", "test_featurescript lambda", "204712.389", ACC),
    (3.55, "通道 B", "Claude：REST massProperties", "持久模型（含圓角）", "204841.875", ACC),
    (6.9, "通道 C", "Antigravity：fCylinder 直造", "自己連 MCP、獨立作業", "204712.389", "#7A5195"),
]
for x, tag, who, how, val, c in lanes:
    ax.add_patch(patches.Rectangle((x, 1.5), 2.9, 3.5, fill=False, ec=c, lw=1.5))
    ax.text(x + 1.45, 4.6, tag, ha="center", fontsize=13, weight="bold", color=c)
    ax.text(x + 1.45, 4.05, who, ha="center", fontsize=10.5, color=INK)
    ax.text(x + 1.45, 3.6, how, ha="center", fontsize=9.5, color=MUTE)
    ax.plot([x + 0.25, x + 2.65], [3.25, 3.25], color=RULE, lw=0.8)
    ax.text(x + 1.45, 2.55, val, ha="center", fontsize=15, weight="bold", color=INK)
    ax.text(x + 1.45, 2.0, "mm³", ha="center", fontsize=10, color=MUTE)
ax.text(5.0, 1.02, "A 與 C 完全相同（不同建構方式、不同代理）　·　B − A = 129.486 = Pappus 定理算出的圓角體積",
        ha="center", fontsize=11, color=OK)
ax.text(5.0, 0.42, "三條路徑各自獨立；要靠幻覺同時湊出這三個數字，機率為零",
        ha="center", fontsize=11.5, color=INK, weight="bold")
save(fig, "fig6_triangulate.png")
