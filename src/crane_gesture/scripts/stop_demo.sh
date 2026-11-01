#!/bin/bash
# crane_gesture のノード（demo/gesture launch、字幕、デモ用 RViz）を止める。Gazebo は止めない
# ※ `bash -c "pkill -f パターン"` は自分自身のシェルにもマッチして死ぬので、スクリプトにしてある
PATTERN='lib/crane_gesture/|crane_gesture (demo|gesture)\.launch|crane_gesture/rviz/demo\.rviz'
pids=$(pgrep -f "$PATTERN")
[ -n "$pids" ] && kill $pids 2>/dev/null && sleep 2
pids=$(pgrep -f "$PATTERN")
[ -n "$pids" ] && kill -9 $pids 2>/dev/null
echo "stopped"
