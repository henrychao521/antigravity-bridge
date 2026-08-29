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
        self.needs_ui_update = False
        self.fetch_lock = threading.Lock()
        self.is_fetching = False

        # 初始化四筆配額資訊項目
        self.quota_items = [rumps.MenuItem(title="載入中...") for _ in range(4)]
        for item in self.quota_items:
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

        # 啟動時立即於背景更新一次
        self.start_fetch_thread()

    def start_fetch_thread(self):
        """啟動背景工作執行緒，避免阻塞選單列主執行緒。"""
        if self.is_fetching:
            return

        thread = threading.Thread(target=self._fetch_quota_worker, daemon=True)
        thread.start()

    def _fetch_quota_worker(self):
        """背景擷取配額資料，並妥善處理所有例外以確保不會崩潰。"""
        with self.fetch_lock:
            self.is_fetching = True
            try:
                if agy_meter is None:
                    data = []
                else:
                    data = agy_meter.quota() or []
            except Exception:
                data = []
            finally:
                self.is_fetching = False

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

    def update_ui(self):
        """更新選單列標題與選單項目文字。"""
        data = self.cached_data

        # 降級狀態：取不到資料或為空 list
        if not data:
            self.title = "◈ --"
            self.quota_items[0].title = "取不到額度（agy 未登入？）"
            for i in range(1, 4):
                self.quota_items[i].title = "—"
            return

        # 建立 bucket_id 索引對應表
        data_by_bucket = {item.get("bucket_id"): item for item in data if isinstance(item, dict) and "bucket_id" in item}

        # 1. 選單列標題計算 (G 取 gemini-5h, C 取 3p-5h)
        g_item = data_by_bucket.get("gemini-5h")
        c_item = data_by_bucket.get("3p-5h")

        g_pct = int(round(g_item["remaining_fraction"] * 100)) if g_item and "remaining_fraction" in g_item else None
        c_pct = int(round(c_item["remaining_fraction"] * 100)) if c_item and "remaining_fraction" in c_item else None

        if g_pct is not None and c_pct is not None:
            prefix = "⚠︎" if (g_pct < 25 or c_pct < 25) else "◈"
            self.title = f"{prefix} G{g_pct} C{c_pct}"
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
