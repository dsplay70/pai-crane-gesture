#!/bin/bash
# コンテナ内で実行: 依存ライブラリの導入とビルド（コンテナを作り直したら再実行）
#   docker exec -it -u ubuntu pai_ros2 bash /workspace/setup_container.sh
set -e
source /opt/ros/humble/setup.bash
source ~/airobot_ws/install/setup.bash
pip3 install --user -q google-genai
# 動画用のウィンドウ配置ツール（ROS の apt 鍵が期限切れのため Ubuntu 公式リポジトリのみ参照）
if ! command -v wmctrl >/dev/null || ! command -v xdotool >/dev/null; then
  sudo apt-get update -qq -o Dir::Etc::sourceparts=/dev/null || true
  sudo apt-get install -y -qq -o Dir::Etc::sourceparts=/dev/null wmctrl xdotool
fi
cd /workspace
colcon build --symlink-install
grep -q '/workspace/install/setup.bash' ~/.bashrc || echo 'source /workspace/install/setup.bash' >> ~/.bashrc
echo "ビルド完了。新しいターミナルで: ros2 launch crane_gesture demo.launch.py（動画用）または gesture.launch.py"
