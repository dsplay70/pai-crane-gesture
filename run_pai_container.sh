#!/bin/bash
# 第4・5回講義の演習環境（ROS 2 Humble + Gazebo + CRANE+ V2）を起動する
# 初回: ./run_pai_container.sh   2回目以降: docker start pai_ros2
# ブラウザで http://localhost:6080/ を開いて操作する
# このフォルダはコンテナ内の /workspace にマウントされる
export PATH="$PATH:/Applications/Docker.app/Contents/Resources/bin"
cd "$(dirname "$0")"
docker run -d --name pai_ros2 \
  --platform linux/amd64 \
  -p 6080:80 --shm-size=512m \
  -p 9090:9090 -p 9876:9876 \
  -v "$(pwd)":/workspace \
  airobotbook/ros2-desktop-ai-robot-book-humble:latest
