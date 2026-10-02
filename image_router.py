#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""圖片自動調度：依 Antigravity 生圖剩餘張數與「急不急」，把每張圖分派給合適、而且現在跑得動的工具。

規範：/Volumes/Work/圖片產生規範.md 第一節決策表、第九節調度規則（2026-09-11 實測＋使用者指定優先順序）。

  image_router.py plan jobs.json [--urgent] [--assume-remaining N] [--reserve N]         只排程、不生圖
  image_router.py run  jobs.json [--urgent] [--reserve N] [--no-wait] [--force]          照排程生圖

核心概念「備援損失 loss」：這張圖若改用備援工具，品質會掉多少（由 2026-09-11 實測分數換算，見 LOSS）。
  loss＝0 的圖（封面、底圖、可用程式畫的圖）改走備援沒有損失，額度緊張時不該拿去搶。

兩種模式（jobs.json 也可寫 "urgent": true）：
  一般（預設）：Antigravity 為主。額度足夠→全部送 Antigravity。額度不足→
      第一輪只分給「換成備援品質真的會掉」的圖（loss≥20），依說明重要性 importance（1＝最需要把概念講清楚）排序，
      同重要性再比 loss；有剩才分給只差美觀或沒差的圖（loss<20）。其餘轉本機／程式繪製；
      沒有結構圖的接線照片本機畫不對，不硬畫，延後到額度重置。預留 1 張給驗收不過時重生。
  急件 --urgent：全部圖片這次都做完為第一考量。不預留、不延後、Antigravity 各批並行且與本機同時開跑；
      額度先給「換掉就一定錯」的圖（loss 高者優先，重要性次之）。本機硬畫的高風險圖列入 _redo_after_reset，
      額度重置後改用 Antigravity 重生。

jobs.json：
  {"out_dir": "相對 jobs.json 或絕對路徑", "urgent": false,
   "jobs": [{"name": "檔名（不含副檔名）", "kind": "見 KINDS", "prompt": "英文提示（≤500 字元）",
             "importance": 1～3, "size": [1024, 1024], "seed": 42, "editable": false（true＝交付後還要改→一律程式繪製）,
             "control": "結構圖路徑（photo_topology 可選）", "mermaid": ".mmd 路徑（diagram_text 可選）"}]}
其他：已存在的輸出直接跳過（--force 才重做，避免重複花額度）；額度推估不出來時照常送 Antigravity、遇 429 再改派；
      執行中遇到 429 剩下的自動改走備援、不重試；本機一次只跑一個 mflux（16GB）會等其他 mflux 結束（--no-wait 略過）；
      每張圖實際用的工具與出處寫進 _manifest.json。
"""
import concurrent.futures as cf, glob, json, os, shutil, subprocess, sys, tempfile, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agy_meter as m

BRAIN = os.path.expanduser("~/.gemini/antigravity-cli/brain")
BIN = os.path.expanduser("~/.local/bin/")
FLUX2 = ["--model", "Runpod/FLUX.2-klein-4B-mflux-4bit", "--base-model", "flux2-klein-4b"]
ZIMG = ["--model", "filipstrand/Z-Image-Turbo-mflux-4bit", "--base-model", "z-image-turbo"]
EDIT_PREFIX = "Turn this flat illustration into a realistic photograph. Keep exactly the same objects, positions and wire connections. "
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# 種類：(中文名稱, 備援工具, 備援品質依據)
KINDS = {
    "photo_topology": ("寫實照片（接線／穿插）", "flux2_edit", "有結構圖→本機 FLUX.2 參考圖編輯（逐項 93%）"),
    "photo_object":   ("寫實照片（單一物件／情境）", "flux2_t2i", "本機 FLUX.2（單一物件 11 張 7 張可用）"),
    "mindmap_blank":  ("心智圖底圖（無字）", "flux2_t2i", "本機 FLUX.2（4/5，節點數量要數）"),
    "icon_set":       ("圖示組", "zimage_t2i", "本機 Z-Image（4/5，與 Antigravity 同分、配色較不一致）"),
    "diagram_text":   ("含中文字的心智圖／流程圖", "program", "程式繪製，文字必然正確、可再修改"),
    "cover":          ("報告封面／章節插圖（無字）", "flux2_t2i", "本機 FLUX.2（5/5，不輸 Antigravity 的 4/5）"),
    "background":     ("PPT／網頁底圖（無字）", "flux2_t2i", "本機 FLUX.2（5/5，與 Antigravity 同分）"),
    "chart":          ("精確圖表／電路圖／尺寸圖", "program", "一律程式繪製，不用 AI"),
}


def loss(j):
    """改走備援的品質損失（0～100），由實測分數換算。"""
    k = j["kind"]
    if k == "photo_topology":
        return 30 if j.get("control") else 100      # 參考圖編輯 93%／本機文生圖接線題 0/8 全對
    return {"photo_object": 50,                     # 本機單一物件 7/11 可用
            "mindmap_blank": 20,                    # 5/5 → 4/5
            "icon_set": 10,                         # 4/5 → 4/5，只差美觀
            "diagram_text": 5,                      # 程式繪製文字更可靠，只差美觀
            "cover": 0, "background": 0, "chart": 0}[k]


MATTERS = 20    # 備援損失 ≥20 才算「品質真的會掉」；低於此（只差美觀）的圖不和它們搶額度


TOOL_NAME = {"agy": "Antigravity", "flux2_t2i": "本機 FLUX.2-klein", "flux2_edit": "本機 FLUX.2 參考圖編輯",
             "zimage_t2i": "本機 Z-Image-Turbo", "program": "程式繪製", "defer": "延後（等額度重置）", "skip": "略過（已存在）"}
CREDIT = {"agy": "AI 生成（Google Gemini 圖像模型，經 Antigravity）",
          "flux2_t2i": "AI 生成（FLUX.2-klein 本機生成，Apache-2.0）", "flux2_edit": "AI 生成（FLUX.2-klein 本機生成，Apache-2.0）",
          "zimage_t2i": "AI 生成（Z-Image-Turbo 本機生成，Apache-2.0）", "program": "本文繪製"}
LOCAL_TOOLS = ("flux2_t2i", "zimage_t2i", "flux2_edit")


def load(path):
    d = json.load(open(path, encoding="utf-8"))
    out = d.get("out_dir", ".")
    out = out if os.path.isabs(out) else os.path.join(os.path.dirname(os.path.abspath(path)), out)
    for j in d["jobs"]:
        if j["kind"] not in KINDS:
            sys.exit(f"{j['name']}：未知種類 {j['kind']}，可用：{', '.join(KINDS)}")
    return os.path.abspath(out), d["jobs"], bool(d.get("urgent"))


def importance(j):
    return j.get("importance", j.get("priority", 2))


def existing(j, out_dir):
    return [f for f in glob.glob(os.path.join(out_dir, j["name"] + ".*")) if not f.endswith(".json")]


def fallback(j, urgent):
    k = j["kind"]
    if k == "photo_topology" and not j.get("control"):
        if urgent:
            return ("flux2_t2i", "急件：額度不足又沒有結構圖，本機先出一張——接線必須逐項驗收，額度重置後改用 Antigravity 重生")
        return ("defer", "一般件：額度不足又沒有結構圖，本機畫不對接線→延後到額度重置")
    if k in ("diagram_text", "chart"):
        return ("program", KINDS[k][2] + ("（Mermaid 自動）" if j.get("mermaid") else "（需另寫 SVG／matplotlib）"))
    return (KINDS[k][1], "改走備援；" + KINDS[k][2])


def plan(jobs, remaining, reserve, urgent, out_dir, force=False):
    n = len(jobs); routes = [None] * n
    unknown = remaining is None
    slots = n if unknown else max(remaining - reserve, 0)
    cand = []
    for i, j in enumerate(jobs):
        if not force and existing(j, out_dir):
            routes[i] = ("skip", "輸出已存在（--force 才重做）")
        elif j["kind"] == "chart":
            routes[i] = ("program", KINDS["chart"][2])
        elif j.get("editable"):
            routes[i] = ("program", "交付後還要修改→程式繪製" + ("（Mermaid 自動）" if j.get("mermaid") else "（需另寫 SVG／matplotlib）"))
        else:
            cand.append(i)
    if urgent:       # 做完為先：先保住「換掉就一定錯」的圖
        passes = [sorted(cand, key=lambda i: (-loss(jobs[i]), importance(jobs[i]), i))]
    else:            # 一般：品質真的會掉的圖先依說明重要性分額度；只差美觀的圖有剩才分
        passes = [sorted([i for i in cand if loss(jobs[i]) >= MATTERS], key=lambda i: (importance(jobs[i]), -loss(jobs[i]), i)),
                  sorted([i for i in cand if loss(jobs[i]) < MATTERS], key=lambda i: (importance(jobs[i]), -loss(jobs[i]), i))]
    for p in passes:
        for i in p:
            if slots > 0:
                routes[i] = ("agy", f"額度內（重要性 {importance(jobs[i])}、備援損失 {loss(jobs[i])}）"); slots -= 1
    for i in cand:
        if routes[i] is None:
            routes[i] = fallback(jobs[i], urgent)
    return routes, unknown


def warnings(j):
    w = []
    if len(j.get("prompt", "")) > 500:
        w.append("提示超過 500 字元")
    size = j.get("size", [1024, 1024])
    if size[0] > size[1] and "16:9" not in j.get("prompt", ""):
        w.append("寬圖但提示沒寫 Wide 16:9")
    return w


def show(jobs, routes, q, remaining, reserve, urgent, unknown):
    print(f"模式：{'急件（全部做完為先、不延後、並行）' if urgent else '一般（Antigravity 為主，額度不足時依說明重要性分配，只差美觀的圖不搶額度）'}")
    rem = "推估不出（照常送 Antigravity，遇 429 再改派）" if unknown else f"推估剩 {remaining} 張、預留 {reserve} 張"
    print(f"Antigravity 生圖：本窗口已用 {q.get('used_in_window')} 張、{rem}、{'目前 429 中，' if q.get('exhausted') else ''}窗口重置 {q.get('window_reset')}")
    print(f"{'名稱':<18}{'重要性':<4}{'損失':<5}{'種類':<20}{'分派':<22}理由")
    for j, (tool, why) in zip(jobs, routes):
        extra = "；".join(warnings(j)) if tool == "agy" else ""
        print(f"{j['name']:<18}{importance(j):<7}{loss(j):<6}{KINDS[j['kind']][0]:<20}{TOOL_NAME[tool]:<22}{why}{('　⚠ ' + extra) if extra else ''}")
    counts = {}
    for t, _ in routes:
        counts[TOOL_NAME[t]] = counts.get(TOOL_NAME[t], 0) + 1
    print("小計：", "、".join(f"{k} {v} 張" for k, v in counts.items()))


def unique(p):
    if not os.path.exists(p):
        return p
    b, e = os.path.splitext(p)
    return f"{b}_{time.strftime('%H%M%S')}{e}"


def prompt_for(items):
    lines = [f"請依序呼叫 generate_image 工具，每一項呼叫一次，共 {len(items)} 次。",
             "規則：ImageName 參數用我給的名稱；Prompt 參數**逐字照抄**下面的英文提示詞，不要改寫、不要增刪。",
             "除了 generate_image 之外不要使用任何其他工具。全部完成後只回覆一行：DONE", ""]
    for j in items:
        lines += [f"### ImageName: {j['name']}", j["prompt"], ""]
    return "\n".join(lines)


def run_agy(items, out_dir):
    r = m.run_with_tools(prompt_for(items), model="gemini-3.7-flash-high", timeout=2700, print_timeout="40m",
                         note="image_router " + ",".join(j["name"] for j in items))
    conv = r.get("conversation_id") or ""
    final = {}
    for s in r.get("steps", []):
        if s.get("tool") == "generate_image" and s.get("state") in ("DONE", "ERROR"):
            final[((s.get("params") or {}).get("ImageName") or "").lower()] = s     # 去重：只留最終狀態
    done, hit, why = {}, None, {}
    for j in items:
        n = j["name"]; s = final.get(n.lower())
        err = str((s or {}).get("error") or "")
        if s and s["state"] == "ERROR" and ("429" in err or "RESOURCE_EXHAUSTED" in err):
            hit = err[:300]; why[n] = "429 額度用完"; continue
        if not s or s["state"] != "DONE":
            why[n] = "沒有成功的 generate_image 呼叫" + (f"：{err[:120]}" if err else ""); continue
        fs = sorted([f for f in glob.glob(os.path.join(BRAIN, conv, "*"))
                     if os.path.basename(f).lower().startswith(n.lower() + "_")], key=os.path.getmtime)   # agy 會把檔名轉小寫
        if not fs:
            why[n] = "state=DONE 但找不到檔案"; continue
        dst = unique(os.path.join(out_dir, n + os.path.splitext(fs[-1])[1])); shutil.copy2(fs[-1], dst); done[n] = dst
    return done, hit, why, conv


def busy():
    return subprocess.run(["pgrep", "-f", "mflux-generate"], capture_output=True).returncode == 0


LOCAL_LOCK = threading.Lock()


def run_local(j, tool, out_dir, wait):
    with LOCAL_LOCK:
        if busy():
            if not wait:
                return None, "本機另有 mflux 在跑（--no-wait）"
            print(f"  {j['name']}：本機另有 mflux 在跑，等它結束…", flush=True)
            while busy():
                time.sleep(30)
        w, h = j.get("size", [1024, 1024]); out = unique(os.path.join(out_dir, j["name"] + ".png"))
        prompt = j.get("local_prompt", j["prompt"])
        if tool == "flux2_t2i":
            cmd = [BIN + "mflux-generate-flux2", *FLUX2, "--prompt", prompt, "--steps", "4"]
        elif tool == "zimage_t2i":
            cmd = [BIN + "mflux-generate-z-image-turbo", *ZIMG, "--prompt", prompt, "--steps", "9"]
        else:
            cmd = [BIN + "mflux-generate-flux2-edit", *FLUX2, "--image-paths", j["control"], "--prompt", EDIT_PREFIX + prompt, "--steps", "4"]
        cmd += ["--width", str(w), "--height", str(h), "--seed", str(j.get("seed", 42)), "--output", out]
        t = time.time(); p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode == 0 and os.path.exists(out):
            return out, f"{round(time.time() - t)} 秒"
        return None, (p.stderr or "")[-200:]


def run_program(j, out_dir):
    if not j.get("mermaid"):
        with open(os.path.join(out_dir, "_program_todo.md"), "a", encoding="utf-8") as f:
            f.write(f"- {j['name']}（{KINDS[j['kind']][0]}）：{j.get('prompt', '')}\n")
        return None, "已列入 _program_todo.md，需另寫 SVG／matplotlib"
    cfg = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump({"executablePath": CHROME, "args": ["--no-sandbox"]}, cfg); cfg.close()
    out = unique(os.path.join(out_dir, j["name"] + ".png"))
    cmd = ["mmdc", "-i", j["mermaid"], "-o", out, "-p", cfg.name, "-b", "white", "-s", "3"] + (["-c", j["mermaid_config"]] if j.get("mermaid_config") else [])
    p = subprocess.run(cmd, capture_output=True, text=True)
    return (out, "Mermaid") if p.returncode == 0 and os.path.exists(out) else (None, (p.stderr or "")[-200:])


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("plan", "run"):
        sys.exit(__doc__)
    mode, path = sys.argv[1], sys.argv[2]
    opt = lambda k, d: type(d)(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
    out_dir, jobs, urgent_file = load(path)
    urgent = urgent_file or "--urgent" in sys.argv
    reserve = opt("--reserve", 0 if urgent else 1)
    force = "--force" in sys.argv
    q = m.image_quota()
    remaining = opt("--assume-remaining", -1)
    remaining = q.get("estimated_remaining") if remaining < 0 else remaining
    routes, unknown = plan(jobs, remaining, reserve, urgent, out_dir, force)
    show(jobs, routes, q, remaining, reserve, urgent, unknown)
    if mode == "plan":
        return
    os.makedirs(out_dir, exist_ok=True)
    wait = "--no-wait" not in sys.argv
    manifest, lock = {}, threading.Lock()

    def record(name, entry):
        with lock:
            manifest[name] = entry

    def do_other(items):
        for j, tool, why in items:
            if tool in LOCAL_TOOLS:
                f, note = run_local(j, tool, out_dir, wait)
            elif tool == "program":
                f, note = run_program(j, out_dir)
            else:
                f, note = None, f"延後到 {q.get('window_reset')} 之後再跑"
            redo = bool(f) and tool != "agy" and loss(j) >= 50
            record(j["name"], {"tool": tool if f else "defer", "file": f, "credit": CREDIT.get(tool) if f else None,
                               "reason": why, "note": note, "redo_after_reset": redo,
                               "must_check_wiring": j["kind"] == "photo_topology"})
            print(f"  {j['name']}：{TOOL_NAME.get(tool, tool)} {'完成' if f else '未產出'}　{note}", flush=True)

    def do_agy(chunk):
        done, hit, why, conv = run_agy(chunk, out_dir)
        back = []
        for j in chunk:
            if j["name"] in done:
                record(j["name"], {"tool": "agy", "file": done[j["name"]], "credit": CREDIT["agy"], "conversation": conv,
                                   "must_check_wiring": j["kind"] == "photo_topology"})
                print(f"  {j['name']}：Antigravity 完成", flush=True)
            else:
                t, r = fallback(j, urgent); back.append((j, t, f"Antigravity 失敗（{why.get(j['name'])}）→ {r}"))
        return back, hit

    other = [(j, r[0], r[1]) for j, r in zip(jobs, routes) if r[0] not in ("agy", "skip")]
    agy = [j for j, r in zip(jobs, routes) if r[0] == "agy"]
    chunks = [agy[b:b + 4] for b in range(0, len(agy), 4)]
    rerouted = []
    if urgent:       # 急件：本機工作與各批 Antigravity 同時開跑
        with cf.ThreadPoolExecutor(max_workers=1 + max(len(chunks), 1)) as ex:
            fo = ex.submit(do_other, other)
            for back, hit in ex.map(do_agy, chunks):
                rerouted += back
                if hit:
                    print("⚠ 有批次遇到 429，失敗的圖改走備援。", flush=True)
            fo.result()
        do_other(rerouted)
    else:            # 一般：逐批送，遇到 429 就不再送，剩下的直接改走備援
        hit_any = False
        for c in chunks:
            if hit_any:
                rerouted += [(j, *fallback(j, urgent)) for j in c]; continue
            back, hit = do_agy(c); rerouted += back
            if hit:
                hit_any = True; print("⚠ 遇到 429，剩下的 Antigravity 工作改走備援、不重試。", flush=True)
        do_other(rerouted + other)
    mp = os.path.join(out_dir, "_manifest.json")
    old = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
    old.update(manifest); json.dump(old, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    redo = [n for n, v in manifest.items() if v.get("redo_after_reset")]
    if redo:
        json.dump({"after": str(q.get("window_reset")), "names": redo}, open(os.path.join(out_dir, "_redo_after_reset.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n結果：")
    for n, v in manifest.items():
        flags = ("　⚠ 接線必須逐項驗收" if v.get("must_check_wiring") and v.get("file") else "") + ("　↻ 額度重置後改用 Antigravity 重生" if v.get("redo_after_reset") else "")
        print(f"  {n:<18}{TOOL_NAME.get(v['tool'], v['tool']):<22}{os.path.basename(v['file']) if v.get('file') else '（未產出）'}{flags}")
    print("清單：", mp)


if __name__ == "__main__":
    main()
