#!/bin/bash
# 動画用にウィンドウを並べる: デモ用 RViz を全画面（F11: メニュー類が消える）にし、
# 字幕パネルを画面下部に常に手前で重ねる。講義用の RViz は最小化する
# 画面サイズは noVNC のブラウザサイズで変わるので、実行時に取得して割り付ける
#   CLEAN=1 のとき: 上下の MATE パネルを自動で隠し、字幕パネルのタイトルバーも消す（録画用）
#   CLEAN=0 で元に戻す
export DISPLAY=${DISPLAY:-:0}
CAPTION_H=${CAPTION_H:-260}
CLEAN=${CLEAN:-}
# docker exec から実行するとデスクトップのセッションバスが無く gsettings が効かないので、パネルの環境から借りる
if [ -z "$DBUS_SESSION_BUS_ADDRESS" ] && pid=$(pgrep -x mate-panel | head -1); then
  export "$(tr '\0' '\n' < /proc/$pid/environ | grep ^DBUS_SESSION_BUS_ADDRESS=)"
fi
# スクリーンセーバー（ロゴが流れる・画面ロック）を止める。撮影中に出ると困るため
gsettings set org.mate.screensaver idle-activation-enabled false 2>/dev/null
gsettings set org.mate.screensaver lock-enabled false 2>/dev/null
pgrep -f mate-screensaver | xargs -r kill 2>/dev/null
xset s off 2>/dev/null
for _ in $(seq 60); do  # 両ウィンドウが出るまで最大60秒待つ
  wmctrl -l | grep -q 'crane_gesture caption' && wmctrl -l | grep -q 'demo.rviz' && break
  sleep 1
done
sleep 2

if [ -n "$CLEAN" ]; then
  [ "$CLEAN" = 1 ] && hide=true || hide=false
  for p in top bottom; do
    gsettings set "org.mate.panel.toplevel:/org/mate/panel/toplevels/$p/" auto-hide "$hide" 2>/dev/null
    gsettings set "org.mate.panel.toplevel:/org/mate/panel/toplevels/$p/" auto-hide-size 0 2>/dev/null
  done
  sleep 1
fi

read -r W H < <(xdpyinfo | awk '/dimensions/{split($2,a,"x"); print a[1], a[2]}')
wmctrl -l | grep 'run_move_group.rviz' | awk '{print $1}' | xargs -r -n1 xdotool windowminimize
RVIZ=$(wmctrl -l | grep 'demo.rviz' | awk '{print $1}' | head -1)
# F11 は切り替えなので、まだ全画面でないときだけ押す
if ! xprop -id "$RVIZ" _NET_WM_STATE | grep -q FULLSCREEN; then
  xdotool windowactivate --sync "$RVIZ" key F11
  sleep 1
fi

CAP=$(wmctrl -l | grep 'crane_gesture caption' | awk '{print $1}' | head -1)
if [ "$CLEAN" = 1 ]; then  # タイトルバーを消す（Motif ヒント）
  xprop -id "$CAP" -f _MOTIF_WM_HINTS 32c -set _MOTIF_WM_HINTS "2, 0, 0, 0, 0"
elif [ "$CLEAN" = 0 ]; then
  xprop -id "$CAP" -remove _MOTIF_WM_HINTS
fi
wmctrl -i -r "$CAP" -b add,above
wmctrl -i -r "$CAP" -e "0,0,$((H - CAPTION_H)),$W,$CAPTION_H"
wmctrl -i -a "$CAP"
echo "arranged: screen ${W}x${H}, caption ${W}x${CAPTION_H}, clean=${CLEAN:-unchanged}"
