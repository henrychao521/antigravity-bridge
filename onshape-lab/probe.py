#!/usr/bin/env python3
"""FeatureScript 編譯探測器：寫入 Feature Studio 再取 featurespecs。

為什麼不用 MCP 的 put_featurescript：它的說明宣稱會回報錯誤，
實測對故意寫壞的程式碼也回傳空字串（2026-08-29 驗證），不可信。
走 REST 的 featurespecs：特徵數 0 就代表模組沒編譯成功。
成本：每次探測 2 次 API 呼叫（PUT + GET）。
"""
import base64, json, os, pathlib, sys, urllib.request

LAB = pathlib.Path(__file__).resolve().parent
IDS = json.loads((LAB / "doc.json").read_text())
_c = json.load(open(os.path.expanduser("~/.claude.json")))["mcpServers"]["jarvis-onshape-mcp"]["env"]
_AUTH = "Basic " + base64.b64encode(
    f"{_c['ONSHAPE_API_KEY']}:{_c['ONSHAPE_API_SECRET']}".encode()).decode()
BASE = (f"https://cad.onshape.com/api/v6/featurestudios/d/{IDS['did']}"
        f"/w/{IDS['wid']}/e/{IDS['eid']}")


def _req(url, data=None):
    r = urllib.request.Request(url, data=data,
        headers={"Authorization": _AUTH, "Accept": "application/json",
                 "Content-Type": "application/json"},
        method="POST" if data else "GET")
    with urllib.request.urlopen(r, timeout=120) as resp:
        return json.loads(resp.read().decode())


def probe(code: str, label: str = "") -> dict:
    _req(BASE, json.dumps({"contents": code}).encode())
    d = _req(BASE + "/featurespecs")
    specs = d.get("featureSpecs") or []
    out = {"label": label, "n_specs": len(specs),
           "types": [s.get("featureType") for s in specs],
           "notices": [(n.get("message"), (n.get("stackTrace") or [{}])[-1].get("line"))
                       for n in (d.get("notices") or [])]}
    print(f"{'✅' if specs else '❌'} {label}: 特徵 {len(specs)} 個 {out['types']}")
    for m, ln in out["notices"][:5]:
        print(f"     line {ln}: {m}")
    return out


if __name__ == "__main__":
    print(probe(pathlib.Path(sys.argv[1]).read_text(), sys.argv[1]))
