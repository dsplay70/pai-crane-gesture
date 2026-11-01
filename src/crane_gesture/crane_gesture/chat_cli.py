"""ターミナルで入力した文を /user_message に送る簡易チャット.

使い方: ros2 run crane_gesture chat                        （対話モード）
        ros2 run crane_gesture chat -- "テストで100点だった！"  （1回だけ送る）
        ros2 run crane_gesture chat --file demo_lines.txt     （台本モード: Enter で次の行を送る）

コンテナ内では日本語入力（Mozc）が使えないため、撮影時は Mac のターミナルから
docker exec -it で台本モードを使う。
"""

import sys
import threading
import time

import rclpy
from std_msgs.msg import String


def wait_for_subscriber(node, pub, timeout=10.0):
    deadline = time.monotonic() + timeout  # 購読者（planner）が見つかるまで待つ
    while pub.get_subscription_count() == 0 and time.monotonic() < deadline:
        time.sleep(0.1)


def read_lines(path):
    with open(path, encoding='utf-8') as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith('#')]


def main():
    rclpy.init()
    node = rclpy.create_node('gesture_chat')
    pub = node.create_publisher(String, 'user_message', 10)
    node.create_subscription(String, 'gesture_status', lambda m: print(f'  [robot] {m.data}'), 10)
    threading.Thread(target=rclpy.spin, args=(node,), daemon=True).start()

    args = [a for a in sys.argv[1:] if not a.startswith('--ros-args')]
    try:
        if args[:1] == ['--file'] and len(args) == 2:
            lines = read_lines(args[1])
            wait_for_subscriber(node, pub)
            for i, text in enumerate(lines, 1):
                input(f'[{i}/{len(lines)}] Enter で送信 → {text}')
                pub.publish(String(data=text))
            input('台本はここまで。Enter で終了')
        elif args:
            wait_for_subscriber(node, pub)
            pub.publish(String(data=' '.join(args)))
            time.sleep(0.5)
        else:
            print('話しかけてください（終了: Ctrl+D）')
            while True:
                text = input('> ').strip()
                if text:
                    pub.publish(String(data=text))
    except (EOFError, KeyboardInterrupt):
        pass
    node.destroy_node()
    rclpy.try_shutdown()
