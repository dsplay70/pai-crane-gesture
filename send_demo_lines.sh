#!/bin/bash
# Mac のターミナルから実行: 台本（既定 demo_lines.txt）を Enter ごとに1行ずつロボットに送る
#   ./send_demo_lines.sh [台本ファイル]
# コンテナ内は日本語入力が使えないため、撮影時はこれを使う
export PATH="$PATH:/Applications/Docker.app/Contents/Resources/bin"
FILE=${1:-demo_lines.txt}
docker exec -it -u ubuntu pai_ros2 bash -c "source /opt/ros/humble/setup.bash && source /workspace/install/setup.bash && ros2 run crane_gesture chat --file /workspace/$FILE"
