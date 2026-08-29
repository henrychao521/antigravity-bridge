#!/bin/zsh
# 停止小工具。必須走 launchctl，直接 kill 會被 KeepAlive 拉回來。
launchctl unload ~/Library/LaunchAgents/com.henry.agy-widget.plist 2>/dev/null && echo "已停止（下次開機也不會啟動，要恢復請跑 agy_widget.sh）"
