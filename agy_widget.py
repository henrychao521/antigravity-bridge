import sys
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

# 載入 bridge 模組路徑（以自身位置推導，搬家後不必改程式）
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

try:
    import agy_meter
except ImportError:
    agy_meter = None

try:
    import agy_guard
except ImportError:
    agy_guard = None

import rumps


# 定義支援的配額項目順序與顯示名稱
BUCKET_CONFIG = {
    "gemini-5h": {"name": "Gemini", "window": "5小時"},
    "gemini-weekly": {"name": "Gemini", "window": "每週"},
    "3p-5h": {"name": "Claude/GPT", "window": "5小時"},
    "3p-weekly": {"name": "Claude/GPT", "window": "每週"},
}
ORDERED_BUCKETS = ["gemini-5h", "gemini-weekly", "3p-5h", "3p-weekly"]


class AgyQuotaWidget(rumps.App):
    """
    Antigravity 配額選單列小工具。

    【更新機制說明】
    本小工具採用雙定時器（rumps.Timer）架構：
    1. 300 秒定時器（慢速）：負責在背景執行緒中呼叫 agy_meter.quota() 更新真實配額數據。
       因為 quota() 內部會啟動子行程進行查詢，耗時約需 2~4 秒，若在 UI 主執行緒執行會造成選單列卡頓，
       且過於頻繁呼叫會造成系統資源浪費，因此設定為 300 秒定期查詢。
    2. 30 秒定時器（快速）：僅使用快取中的 reset_time 與當前時間重新計算剩餘倒數，
       完全不呼叫 quota()，藉此確保倒數計時看起來即時流暢，又不會阻塞 UI 或引發效能負擔。
    """

    def __init__(self):
        super().__init__(name="AgyWidget", title="◈ --", quit_button=None)

        self.cached_data: list[dict] = []
        self.quota_meta: dict = {}
        self.needs_ui_update = False
        self.fetch_lock = threading.Lock()
        self.is_fetching = False

        # 2026-09-30：所在網路區域（agy_guard.network_zone），放在選單最上面。
        # 在封鎖網路（例如學校網域）時完全不查額度，避免反覆啟動 agy。
        self.zone: dict = {}
        self.net_item = rumps.MenuItem(title="網路　偵測中...")
        self.net_detail_item = rumps.MenuItem(title="")
        self.net_agy_item = rumps.MenuItem(title="")
        for item in (self.net_item, self.net_detail_item, self.net_agy_item):
            self.menu.add(item)
        self.menu.add(rumps.separator)

        # 初始化四筆配額資訊項目
        self.quota_items = [rumps.MenuItem(title="載入中...") for _ in range(4)]
        for item in self.quota_items:
            self.menu.add(item)

        # 2026-09-10：生圖（獨立配額）與 G1 credits
        self.cached_extra: dict = {}
        self.menu.add(rumps.separator)
        self.image_item = rumps.MenuItem(title="生圖　載入中...")
        self.image_limit_item = rumps.MenuItem(title="")
        self.credit_item = rumps.MenuItem(title="G1 credits　載入中...")
        for item in (self.image_item, self.image_limit_item, self.credit_item):
            self.menu.add(item)

        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("立即重新整理", callback=self.on_refresh_clicked))
        self.menu.add(rumps.MenuItem("開啟用量報表", callback=self.on_open_report_clicked))
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("結束", callback=self.on_quit_clicked))

        # 定時器 1：每 2 秒跑一次。倒數本身每 30 秒才需要重畫，但這個定時器同時
        # 負責把背景執行緒抓回來的新資料套上 UI（見 _fetch_quota_worker），
        # 所以週期要短，否則剛啟動時要等半分鐘才看得到數字。
        self._tick = 0
        self.timer_countdown = rumps.Timer(self.tick_countdown, 2)
        self.timer_countdown.start()

        # 定時器 2：每 300 秒於背景向 agy_meter 抓取最新配額
        self.timer_fetch = rumps.Timer(self.tick_fetch, 300)
        self.timer_fetch.start()

        # 定時器 3：每 30 秒偵測一次網路區域（只看本機訊號，不連外）
        self.timer_zone = rumps.Timer(self.tick_zone, 30)
        self.timer_zone.start()

        # 啟動時立即於背景更新一次
        self.start_fetch_thread()

    def _refresh_zone(self) -> dict:
        """重新判斷網路區域；區域或可用狀態改變時舉旗更新 UI。"""
        if agy_guard is None:
            return {}
        try:
            z = agy_guard.network_zone()
        except Exception as e:
            z = {"id": "unknown", "name": f"判斷失敗（{type(e).__name__}）", "short": "?", "why": "", "blocked": None}
        old = self.zone
        self.zone = z
        key = lambda d: (d.get("id"), d.get("ip"), bool(d.get("blocked")), d.get("bridge"))
        if not old or key(old) != key(z):
            self.needs_ui_update = True
            # 從封鎖網路回到可用網路（例如放學回家）：馬上重新查一次額度
            if old and old.get("blocked") and not z.get("blocked"):
                self.start_fetch_thread()
        return z

    def tick_zone(self, _):
        threading.Thread(target=self._refresh_zone, daemon=True).start()

    def start_fetch_thread(self):
        """啟動背景工作執行緒，避免阻塞選單列主執行緒。"""
        if self.is_fetching:
            return

        thread = threading.Thread(target=self._fetch_quota_worker, daemon=True)
        thread.start()

    def _fetch_quota_worker(self):
        """背景擷取配額資料，並妥善處理所有例外以確保不會崩潰。"""
        # 封鎖網路（封鎖網域或黑名單）：完全不啟動 agy，保留上次資料並標註暫停。
        zone = self._refresh_zone()
        if zone.get("blocked"):
            self.quota_meta = {"paused": True, "error": f"{zone.get('name', '封鎖網路')}，暫停查詢（不嘗試連線）",
                               "from_cache": False, "fetched_at": None}
            # 還沒有資料（例如在學校剛開機）：讀 agy_meter 的額度快取檔，不啟動 agy
            try:
                if agy_meter is not None:
                    import json
                    cache = json.loads(agy_meter.QUOTA_CACHE_PATH.read_text(encoding="utf-8"))
                    self.quota_meta["fetched_at"] = datetime.fromisoformat(cache["fetched_at"])
                    if not self.cached_data:
                        self.cached_data = [
                            {**b, "reset_time": datetime.fromisoformat(b["reset_time"]) if b.get("reset_time") else None}
                            for b in cache.get("buckets", [])]
            except Exception:
                pass
            try:
                if agy_meter is not None:   # 生圖統計是掃本機檔案，不碰 agy
                    self.cached_extra = {**(self.cached_extra or {}),
                                         "image": agy_meter.image_quota(), "images": agy_meter.images()}
            except Exception:
                pass
            self.needs_ui_update = True
            return

        with self.fetch_lock:
            self.is_fetching = True
            try:
                if agy_meter is None:
                    data = []
                else:
                    data = agy_meter.quota() or []
                    self.quota_meta = dict(agy_meter.QUOTA_LAST)
            except Exception as e:
                data = []
                self.quota_meta = {"error": f"小工具例外（{type(e).__name__}）", "from_cache": False, "fetched_at": None}
            finally:
                self.is_fetching = False

        # 生圖狀態（掃 brain 目錄＋429 事件，不耗配額）與 G1 credits（slash 指令，不耗 token）
        extra = {}
        try:
            if agy_meter is not None:
                extra = {"image": agy_meter.image_quota(), "images": agy_meter.images(),
                         "credits": agy_meter.credits()}
                agy_meter.log_extra_sample(extra["image"], extra["credits"])
        except Exception:
            extra = {}
        self.cached_extra = extra

        # 每次抓到新資料就追加一筆時序樣本（5 分鐘一次）。
        # 額度百分比是瞬時值，不當場記下來事後就補不回來了。
        try:
            if data and agy_meter is not None:
                agy_meter.log_quota_sample(data)
        except Exception:
            pass

        # AppKit 規定 UI 只能在主執行緒更新，所以這裡不直接呼叫 update_ui()，
        # 只把資料放進快取並舉旗，交給主執行緒上的 tick_countdown 套用。
        self.cached_data = data
        self.needs_ui_update = True

    def _format_countdown(self, reset_time: Optional[datetime]) -> str:
        """依據 reset_time 計算剩餘倒數時間字串。"""
        if not reset_time:
            return "即將重置"

        now = datetime.now().astimezone()
        diff = reset_time - now
        total_seconds = diff.total_seconds()

        if total_seconds <= 0:
            return "即將重置"

        total_minutes = int(total_seconds // 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"{hours}h{minutes:02d}m 後重置"

    def _render_zone(self):
        """選單最上面三行：所在區域、IP／閘道／網域、Antigravity 是否可用。"""
        z = self.zone or {}
        if not z:
            self.net_item.title = "網路　偵測中..." if agy_guard else "網路　無法判斷（找不到 agy_guard）"
            self.net_detail_item.title = ""
            self.net_agy_item.title = ""
            return
        why = f"（依 {z['why']}）" if z.get("why") else ""
        cable = "　雷電線已接" if z.get("bridge") else ""
        self.net_item.title = f"網路：{z.get('name', '?')}{why}{cable}"
        dom = "、".join(z.get("domains") or []) or "無"
        self.net_detail_item.title = f"　IP {z.get('ip') or '—'}　閘道 {z.get('gw') or '—'}　網域 {dom}"
        self.net_agy_item.title = ("　Antigravity：🚫 停用（此網路不嘗試連線，額度暫停查詢）"
                                   if z.get("blocked") else "　Antigravity：✅ 可用")

    def update_ui(self):
        """更新選單列標題與選單項目文字：網路區域＋額度。"""
        self._render_zone()
        self._update_quota_ui()
        z = self.zone or {}
        tag = z.get("short") or ""
        if z.get("blocked"):
            self.title = f"{tag} ⛔" if tag else "⛔"
            if self.cached_data:
                ts = (self.quota_meta or {}).get("fetched_at")
                when = f"（{ts:%m/%d %H:%M} 查詢）" if ts else ""
                self.quota_items[0].title += f"　⏸ 暫停查詢，以下為上次資料{when}"
        elif tag:
            self.title = f"{tag} {self.title}"

    def _update_quota_ui(self):
        """更新額度相關的標題與選單項目文字。"""
        data = self.cached_data

        # 降級狀態：取不到資料或為空 list
        meta = self.quota_meta or {}
        if not data:
            reason = meta.get("error") or "尚未取得"
            self.title = "◈ --"
            self.quota_items[0].title = f"取不到額度：{reason}"
            self.quota_items[1].title = "　（未登入時才會寫「未登入」；逾時或暫時錯誤請按立即重新整理）"
            for i in range(2, 4):
                self.quota_items[i].title = "—"
            return

        # 建立 bucket_id 索引對應表
        data_by_bucket = {item.get("bucket_id"): item for item in data if isinstance(item, dict) and "bucket_id" in item}

        # 1. 選單列標題計算 (G 取 gemini-5h, C 取 3p-5h)
        g_item = data_by_bucket.get("gemini-5h")
        c_item = data_by_bucket.get("3p-5h")

        g_pct = int(round(g_item["remaining_fraction"] * 100)) if g_item and "remaining_fraction" in g_item else None
        c_pct = int(round(c_item["remaining_fraction"] * 100)) if c_item and "remaining_fraction" in c_item else None

        iq = (self.cached_extra or {}).get("image") or {}
        img_tag = ""
        if iq:
            if iq.get("exhausted"):
                img_tag = " 圖⛔"
            elif iq.get("estimated_remaining") is not None:
                img_tag = f" 圖{iq['estimated_remaining']}"
            else:
                img_tag = f" 圖{iq.get('used_in_window', 0)}用"
        if g_pct is not None and c_pct is not None:
            prefix = "⚠︎" if (g_pct < 25 or c_pct < 25 or iq.get("exhausted")) else "◈"
            self.title = f"{prefix} G{g_pct} C{c_pct}{img_tag}"
        else:
            self.title = "◈ --"

        # 2. 下拉選單項目更新（依指定順序：gemini-5h, gemini-weekly, 3p-5h, 3p-weekly）
        for idx, bucket_id in enumerate(ORDERED_BUCKETS):
            config = BUCKET_CONFIG.get(bucket_id, {"name": bucket_id, "window": ""})
            item_data = data_by_bucket.get(bucket_id)

            if item_data:
                rem_pct = item_data.get("remaining_fraction", 0.0) * 100
                reset_time = item_data.get("reset_time")
                countdown_str = self._format_countdown(reset_time)
                # 格式：Gemini · 5小時　剩 99.5%　4h37m 後重置
                self.quota_items[idx].title = (
                    f"{config['name']} · {config['window']}　剩 {rem_pct:.1f}%　{countdown_str}"
                )
            else:
                self.quota_items[idx].title = f"{config['name']} · {config['window']}　無資料"
        if meta.get("from_cache") and meta.get("fetched_at"):
            age = int((datetime.now().astimezone() - meta["fetched_at"]).total_seconds() // 60)
            self.quota_items[0].title += f"　⟲ {age} 分鐘前資料（本次{meta.get('error') or '查詢失敗'}）"
            self.title = self.title.replace("◈", "◇", 1)

        # 3. 生圖與 credits
        ex = self.cached_extra or {}
        iq, im, cr = ex.get("image") or {}, ex.get("images") or {}, ex.get("credits")
        if iq:
            cd = self._format_countdown(iq.get("window_reset")) if iq.get("window_reset") else "窗口未開始"
            if iq.get("exhausted"):
                self.image_item.title = f"生圖 · 已用完（本窗口 {iq.get('used_in_window', 0)} 張）　{cd}"
            else:
                rem = f"估計還能生 {iq['estimated_remaining']} 張" if iq.get("estimated_remaining") is not None else "剩餘未知"
                self.image_item.title = f"生圖 · 本窗口 {iq.get('used_in_window', 0)} 張　{rem}　{cd}"
            lim = f"約 {iq['estimated_limit']} 張／5小時" if iq.get("estimated_limit") else "尚未推估"
            self.image_limit_item.title = f"　推估上限 {lim}｜近24小時 {im.get('last_24h', 0)} 張｜歷來 {im.get('total', 0)} 張"
        else:
            self.image_item.title = "生圖　無資料"
            self.image_limit_item.title = ""
        self.credit_item.title = f"G1 credits　剩 {cr['remaining_credits']}" if cr else "G1 credits　取不到"

    def tick_countdown(self, _):
        """主執行緒定時器：套用背景抓回的新資料，並每 30 秒重算一次倒數。"""
        self._tick += 1
        if self.needs_ui_update:
            self.needs_ui_update = False
            self.update_ui()
        elif self.cached_data and self._tick % 15 == 0:  # 2 秒 × 15 = 30 秒
            self.update_ui()

    def tick_fetch(self, _):
        """300 秒慢定時器：背景重新呼叫 quota()。"""
        self.start_fetch_thread()

    def on_refresh_clicked(self, _):
        """立即重新整理選單事件。"""
        self.start_fetch_thread()

    def on_open_report_clicked(self, _):
        """開啟用量報表（使用 Terminal 執行報告腳本）。"""
        report = BASE / "token_report.py"
        script = f'tell application "Terminal" to do script "python3 {report}"'
        try:
            subprocess.Popen(["osascript", "-e", script])
        except Exception:
            pass

    def on_quit_clicked(self, _):
        """結束選單列應用程式。"""
        rumps.quit_application()


if __name__ == "__main__":
    AgyQuotaWidget().run()
