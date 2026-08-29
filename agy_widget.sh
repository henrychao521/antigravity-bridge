#!/bin/zsh
# 啟動配額選單列小工具（由 launchd 管理，開機自動啟動）
launchctl load ~/Library/LaunchAgents/com.henry.agy-widget.plist 2>/dev/null
launchctl list | grep -q agy-widget \
  && echo "執行中，請看選單列右上角的「◈ G.. C..」　log: /tmp/agy-widget.log" \
  || echo "啟動失敗，看 /tmp/agy-widget.log"
