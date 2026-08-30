# -*- coding: utf-8 -*-
"""Antigravity 自述教學報告配圖。依它自己開的規格製作。
視覺語言刻意與 Claude 那份不同：操作手冊風——粗框步驟塊、等寬字體標識、暖色強調。"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, patches
FP = "/Library/Fonts/Arial Unicode.ttf"
font_manager.fontManager.addfont(FP)
plt.rcParams.update({"font.family": font_manager.FontProperties(fname=FP).get_name(),
                     "axes.unicode_minus": False})
INK, LINE, WARM, BAD, OK, MUTE, PAPER = "#221E1B", "#B9AFA3", "#C2681B", "#B3261E", "#2E7D46", "#7A7168", "#FBF7F1"
def save(fig, n):
    fig.savefig(f"figs/{n}", dpi=200, bbox_inches="tight", facecolor="white"); plt.close(fig); print("✓", n)
def blk(ax, x, y, w, h, text, fc=PAPER, ec=INK, lw=1.6, fs=11.5, tc=INK, bold=False):
    ax.add_patch(patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                                        fc=fc, ec=ec, lw=lw))
    ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=fs, color=tc,
            weight="bold" if bold else "normal", linespacing=1.5)

# 圖 1-1 架構圖
fig, ax = plt.subplots(figsize=(9.6, 3.4)); ax.axis("off"); ax.set_xlim(0,10); ax.set_ylim(0,3.4)
for x, t in [(0.2,"使用者\n（自然語言指令）"), (3.55,"AI 代理\nMCP Client"), (6.9,"Onshape 雲端平台\nFeatureScript 引擎")]:
    blk(ax, x, 1.05, 2.9, 1.35, t, fs=12)
for x0, x1, y, lab in [(3.15,3.5,2.05,"指令"), (6.5,6.85,2.05,"FeatureScript / MCP API")]:
    ax.annotate("", xy=(x1,y), xytext=(x0,y), arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.6))
    ax.text((x0+x1)/2, y+0.16, lab, ha="center", fontsize=9.5, color=INK)
for x0, x1, y, lab in [(6.85,6.5,1.45,"運算結果 / 報錯"), (3.5,3.15,1.45,"結果回報")]:
    ax.annotate("", xy=(x1,y), xytext=(x0,y), arrowprops=dict(arrowstyle="-|>", color=WARM, lw=1.6))
    ax.text((x0+x1)/2, y-0.32, lab, ha="center", fontsize=9.5, color=WARM)
save(fig, "fig1_1_arch.png")

# 圖 2-1 OAuth 流程
fig, ax = plt.subplots(figsize=(6.4, 6.4)); ax.axis("off"); ax.set_xlim(0,6); ax.set_ylim(0,6.4)
steps = ["1. 訂閱 App Store", "2. 動態註冊取得 Client ID", "3. 使用者同意授權",
         "4. 取得 Access Token", "5. 連線 MCP 伺服器"]
y = 5.5
for i, s in enumerate(steps):
    blk(ax, 0.6, y, 4.8, 0.72, s, fc=(PAPER if i < 4 else "#EAF3EC"),
        ec=(INK if i < 4 else OK), fs=12.5, bold=(i == 4))
    if i < len(steps)-1:
        ax.annotate("", xy=(3.0, y-0.30), xytext=(3.0, y-0.02),
                    arrowprops=dict(arrowstyle="-|>", color=MUTE, lw=1.5))
    y -= 1.06
save(fig, "fig2_1_oauth.png")

# 圖 3-1 工具消耗對照
fig, ax = plt.subplots(figsize=(9.2, 3.6))
tools = ["search_..._documentation\n文件檢索", "test_featurescript\n匿名程式碼驗證",
         "自建 REST 探測器\n編譯檢查", "test_feature\n完整特徵編譯"]
vals = [1, 1, 2, 4]; cols = [OK, OK, WARM, BAD]
b = ax.barh(tools, vals, color=cols, height=0.55)
for r, v in zip(b, vals):
    ax.text(v+0.09, r.get_y()+r.get_height()/2, f"{v}", va="center", fontsize=13, color=INK, weight="bold")
ax.set_xlim(0, 4.8); ax.set_xlabel("每次呼叫消耗的 Onshape API 次數", fontsize=11.5)
ax.tick_params(labelsize=10.5); ax.spines[["top","right"]].set_visible(False)
ax.spines[["left","bottom"]].set_color(LINE); ax.grid(axis="x", color=LINE, lw=.6, alpha=.6); ax.set_axisbelow(True)
save(fig, "fig3_1_tools.png")

# 圖 4-1 id 型別差異
fig, ax = plt.subplots(figsize=(9.4, 3.6)); ax.axis("off"); ax.set_xlim(0,10); ax.set_ylim(0,3.6)
for x, title, code, res, c, mark in [
    (0.3, "test_featurescript 環境", 'id  →  {}  ← 空 Map', 'id + "base"\n✗ Can not add map and string', BAD, "✗"),
    (5.2, "test_feature 環境", 'id  →  Id', 'id + "base"\n✓ 產生唯一識別碼', OK, "✓")]:
    ax.add_patch(patches.Rectangle((x, 0.25), 4.5, 3.0, fc="white", ec=c, lw=2))
    ax.text(x+2.25, 2.92, f"{mark}  {title}", ha="center", fontsize=12.5, weight="bold", color=c)
    ax.text(x+2.25, 2.25, code, ha="center", fontsize=12, color=INK)
    ax.plot([x+0.35, x+4.15], [1.85, 1.85], color=LINE, lw=.9)
    ax.text(x+2.25, 1.1, res, ha="center", fontsize=11.5, color=c, linespacing=1.7)
save(fig, "fig4_1_idtype.png")

# 圖 5-1 座標標註
import numpy as np
fig, ax = plt.subplots(figsize=(8.6, 4.8)); ax.axis("off"); ax.set_aspect("equal")
def iso(x, y, z): return (0.866*(x - y), 0.5*(x + y) + z)
B = [(0,0,0),(100,0,0),(100,100,0),(0,100,0)]
T = [(0,0,20),(100,0,20),(100,100,20),(0,100,20)]
# 畫家演算法：先側面，再頂面，最後圓柱
# 投影自 -x-y 方向觀看，故可見側面為 y=0 與 x=0 兩面
for quad, fc in [([B[0],B[1],T[1],T[0]], "#B9CEDD"),      # y=0 側面
                 ([B[0],B[3],T[3],T[0]], "#9FB9CB"),      # x=0 側面
                 (T, "#DCE9F2")]:                          # 頂面
    ax.add_patch(patches.Polygon([iso(*p) for p in quad], fc=fc, ec=INK, lw=1.3, zorder=2))
th = np.linspace(0, 2*np.pi, 90)
# 可見側面＝投影後較低的那半圈（x+y 較小），即 θ 由 3π/4 掃到 7π/4
arc = np.linspace(0.75*np.pi, 1.75*np.pi, 60)
side = ([iso(50+10*np.cos(t), 50+10*np.sin(t), 20) for t in arc] +
        [iso(50+10*np.cos(t), 50+10*np.sin(t), 35) for t in arc][::-1])
ax.add_patch(patches.Polygon(side, fc="#9FB9CB", ec=INK, lw=1.2, zorder=3))
ax.add_patch(patches.Polygon([iso(50+10*np.cos(t), 50+10*np.sin(t), 35) for t in th],
                             fc="#DCE9F2", ec=INK, lw=1.2, zorder=4))
for p, lab, dx, dy in [((0,0,0),"corner1 (0,0,0)",-52,-22), ((100,100,20),"corner2 (100,100,20)",10,16),
                       ((50,50,20),"bottomCenter (50,50,20)",52,-26), ((50,50,35),"topCenter (50,50,35)",44,20)]:
    X,Y = iso(*p); ax.plot([X],[Y], "o", color=WARM, ms=5, zorder=6)
    ax.annotate(lab, xy=(X,Y), xytext=(X+dx, Y+dy), fontsize=10.5, color=WARM, zorder=6,
                arrowprops=dict(arrowstyle="-", color=WARM, lw=1))
ax.text(0, -48, "基體 100 × 100 × 20　定位柱 ⌀20 × 15（單位：mm）", fontsize=11, color=MUTE, ha="center")
ax.set_xlim(-135, 145); ax.set_ylim(-58, 150)
save(fig, "fig5_1_coords.png")

# 圖 5-2 opBoolean 樹狀
fig, ax = plt.subplots(figsize=(9.6, 4.2)); ax.axis("off"); ax.set_xlim(0,10); ax.set_ylim(0,4.2)
blk(ax, 3.9, 3.35, 2.2, 0.62, "opBoolean", fs=13, bold=True)
for x, c, head, lines, note in [
    (0.35, BAD, "✗ 錯誤寫法", ['"tools"   : [ Boss ]', '"targets" : [ Base ]'], "BOOLEAN_BAD_INPUT"),
    (5.35, OK, "✓ 正確寫法", ['"tools" : qUnion([Boss, Base])', 'no targets'], "聯集成功，單一實體")]:
    ax.annotate("", xy=(x+2.1, 2.62), xytext=(5.0, 3.3), arrowprops=dict(arrowstyle="-|>", color=c, lw=1.5))
    ax.add_patch(patches.Rectangle((x, 0.75), 4.3, 1.85, fc="white", ec=c, lw=2))
    ax.text(x+2.15, 2.3, head, ha="center", fontsize=12.5, color=c, weight="bold")
    for i, l in enumerate(lines):
        ax.text(x+2.15, 1.78-i*0.36, l, ha="center", fontsize=11, color=INK, family="monospace")
    ax.text(x+2.15, 0.98, note, ha="center", fontsize=11, color=c, weight="bold")
save(fig, "fig5_2_boolean.png")

# 圖 6-1 單位換算
fig, ax = plt.subplots(figsize=(9.4, 2.2)); ax.axis("off"); ax.set_xlim(0,10); ax.set_ylim(0,2.2)
blk(ax, 0.3, 0.5, 3.5, 1.2, "evVolume 原始回傳\n0.0002047… meter³", fs=12)
blk(ax, 6.2, 0.5, 3.5, 1.2, "純數字輸出\n204712.3889…", fc="#EAF3EC", ec=OK, fs=12, bold=True)
ax.annotate("", xy=(6.15,1.1), xytext=(3.85,1.1), arrowprops=dict(arrowstyle="-|>", color=WARM, lw=2))
ax.text(5.0, 1.32, "/ (millimeter ^ 3)", ha="center", fontsize=12, color=WARM, family="monospace")
ax.text(5.0, 0.72, "ValueWithUnits 自帶單位，不除不會變成純數字", ha="center", fontsize=10, color=MUTE)
save(fig, "fig6_1_units.png")

# 圖 7-1 開發階段消耗
fig, ax = plt.subplots(figsize=(7.4, 3.8))
stages = ["查閱文檔", "局部邏輯測試", "完整特徵生成"]
vals = [1, 1, 4]; cols = [OK, "#C9A227", BAD]
b = ax.bar(stages, vals, color=cols, width=0.5)
for r, v in zip(b, vals):
    ax.text(r.get_x()+r.get_width()/2, v+0.1, f"{v} 次/回", ha="center", fontsize=12, color=INK, weight="bold")
ax.set_ylim(0, 5); ax.set_ylabel("每次操作消耗的 API 額度", fontsize=11.5)
ax.tick_params(labelsize=11.5); ax.spines[["top","right"]].set_visible(False)
ax.spines[["left","bottom"]].set_color(LINE); ax.grid(axis="y", color=LINE, lw=.6, alpha=.6); ax.set_axisbelow(True)
ax.text(1, 4.5, "策略：先用便宜工具把邏輯測到有把握，最後才用最貴的做整合驗證",
        ha="center", fontsize=10.5, color=MUTE)
save(fig, "fig7_1_budget.png")
