"""Onshape FeatureScript MCP 用戶端（HTTP + OAuth bearer）。

為什麼自己實作而不用 Claude Code 的 MCP 設定：該伺服器走 OAuth 動態註冊，
授權需要互動式瀏覽器流程，非互動 session 跑不了。自己實作就能在任何 session 直接用。

成本：**1 次工具呼叫 ≈ 1 次 Onshape API 呼叫**，而帳號一年只有 2500 次（用完硬停）。
所以每次呼叫都經過 journal 記錄，方便事後檢討哪些是浪費。
"""

import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://fs-mcp.labs.onshape.app"
LAB = pathlib.Path(__file__).resolve().parent / "onshape-lab"
TOKEN = LAB / ".token.json"
PKCE = LAB / ".pkce.json"
JOURNAL = LAB / "calls.jsonl"

_session_id = None


def _post(url, body, headers, form=False):
    data = urllib.parse.urlencode(body).encode() if form else body
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, r.read().decode(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), dict(e.headers)


def _token() -> str:
    """取 access token，過期就用 refresh token 換新的。"""
    d = json.loads(TOKEN.read_text())
    issued = d.get("_issued_at", 0)
    if issued and time.time() < issued + d.get("expires_in", 3599) - 120:
        return d["access_token"]
    if not issued:  # 舊格式，先當作有效並補上時間戳
        d["_issued_at"] = time.time()
        TOKEN.write_text(json.dumps(d))
        return d["access_token"]
    cid = json.loads(PKCE.read_text())["client_id"]
    st, body, _ = _post(f"{BASE}/token", {
        "grant_type": "refresh_token", "refresh_token": d["refresh_token"], "client_id": cid,
    }, {"Content-Type": "application/x-www-form-urlencoded"}, form=True)
    if st != 200:
        raise RuntimeError(f"refresh 失敗 HTTP {st}: {body[:200]}")
    new = json.loads(body)
    new["_issued_at"] = time.time()
    TOKEN.write_text(json.dumps(new))
    os.chmod(TOKEN, 0o600)
    return new["access_token"]


def _parse(body: str):
    body = body.strip()
    if not body:
        return {}
    if body.startswith("{"):
        return json.loads(body)
    for line in body.splitlines():           # SSE：data: {...}
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    return {"raw": body[:500]}


def rpc(method, params=None, notify=False):
    global _session_id
    h = {"Content-Type": "application/json",
         "Accept": "application/json, text/event-stream",
         "Authorization": f"Bearer {_token()}",
         "MCP-Protocol-Version": "2025-06-18"}
    if _session_id:
        h["Mcp-Session-Id"] = _session_id
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    if not notify:
        msg["id"] = 1
    st, body, hdrs = _post(f"{BASE}/mcp", json.dumps(msg).encode(), h)
    sid = hdrs.get("Mcp-Session-Id") or hdrs.get("mcp-session-id")
    if sid:
        _session_id = sid
    return st, _parse(body)


def connect():
    rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "antigravity-bridge", "version": "1.0"}})
    rpc("notifications/initialized", {}, notify=True)


def call(name, args=None, note=""):
    """呼叫一個工具，並把這次呼叫記進 journal（額度太珍貴，每一次都要留痕）。"""
    st, r = rpc("tools/call", {"name": name, "arguments": args or {}})
    res = r.get("result") or {}
    text = "\n".join(c["text"] for c in res.get("content", []) if c.get("type") == "text")
    # 完整輸出一律落地：額度太貴，同一份資訊不能因為沒存而付第二次
    stamp = time.strftime("%H%M%S")
    outdir = LAB / "out"
    outdir.mkdir(exist_ok=True)
    outfile = outdir / f"{stamp}_{name}.txt"
    outfile.write_text(text, encoding="utf-8")

    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "tool": name, "http": st,
             "out_file": str(outfile.relative_to(LAB)),
             "isError": bool(res.get("isError")), "note": note,
             "args_keys": sorted((args or {}).keys()),
             "out_head": text[:300]}
    with JOURNAL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return st, text, bool(res.get("isError"))


def usage() -> dict:
    _, txt, _ = call("get_api_usage", note="額度查詢")
    return json.loads(txt)
