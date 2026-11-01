"""台本を順に送りながら画面を録画し、編集用のイベント記録（JSON）を残す.

使い方（コンテナ内）:
  ros2 run crane_gesture record_demo --lines /workspace/demo_lines.txt --out /workspace/videos/take1.mp4

録画は ffmpeg の x11grab（DISPLAY の画面全体）。各行について
  送信時刻 / プラン受信時刻 / 動作開始 / 動作完了 / 感情・返事・応答時間 / 安全チェックの補正
を録画開始からの秒数で <out>.json に書く。編集スクリプトはこれを使って自動でカットする。
"""

import argparse
import json
import os
import subprocess
import threading
import time

import rclpy
from std_msgs.msg import String

from crane_gesture.chat_cli import read_lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lines', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--size', default='1920x1080')
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--gap', type=float, default=2.5, help='動作完了から次の送信までの秒数')
    args, _ = ap.parse_known_args()

    rclpy.init()
    node = rclpy.create_node('demo_recorder')
    pub = node.create_publisher(String, 'user_message', 10)
    cond = threading.Condition()
    state = {'plan': None, 'status': []}

    def on_plan(m):
        with cond:
            state['plan'] = (time.monotonic(), json.loads(m.data))
            cond.notify_all()

    def on_status(m):
        with cond:
            state['status'].append((time.monotonic(), m.data))
            cond.notify_all()

    status_pub = node.create_publisher(String, 'gesture_status', 10)
    node.create_subscription(String, 'gesture_plan', on_plan, 10)
    node.create_subscription(String, 'gesture_status', on_status, 10)
    threading.Thread(target=rclpy.spin, args=(node,), daemon=True).start()
    while pub.get_subscription_count() == 0:
        time.sleep(0.1)

    status_pub.publish(String(data='reset'))  # 字幕パネルの前回の表示を消す
    time.sleep(0.5)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    ff = subprocess.Popen(
        ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'x11grab', '-draw_mouse', '0',
         '-framerate', str(args.fps), '-video_size', args.size, '-i', os.environ.get('DISPLAY', ':0') + '.0',
         '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '16', '-pix_fmt', 'yuv420p', args.out],
        stdin=subprocess.PIPE)
    t0 = time.monotonic()
    rel = lambda t: round(t - t0, 2)  # noqa: E731
    time.sleep(3.0)  # 冒頭の静止（タイトルの背景に使える）

    events = []
    for text in read_lines(args.lines):
        with cond:
            state['plan'], state['status'] = None, []
        t_send = time.monotonic()
        pub.publish(String(data=text))
        ev = {'text': text, 'send': rel(t_send)}
        with cond:
            done = cond.wait_for(lambda: any(s == 'done' or s.startswith(('rejected', 'controllers'))
                                             for _, s in state['status']), timeout=40)
            plan_t, plan = state['plan'] or (None, {})
            status = list(state['status'])
        ev.update({
            'plan': rel(plan_t) if plan_t else None,
            'start': next((rel(t) for t, s in status if s.startswith('executing')), None),
            'done': next((rel(t) for t, s in status if s == 'done'), None),
            'ok': bool(done) and any(s == 'done' for _, s in status),
            'emotion': plan.get('emotion'), 'reply': plan.get('reply'), 'intent': plan.get('intent'),
            'latency_s': plan.get('latency_s'), 'source': plan.get('source'),
            'validator': [s[len('validator: '):] for _, s in status if s.startswith('validator: ')],
        })
        events.append(ev)
        print(f"[{ev['send']:6.1f}s] {text} -> {ev['emotion']} 「{ev['reply']}」 ok={ev['ok']}", flush=True)
        time.sleep(args.gap)

    ff.communicate(b'q')
    meta = {'video': os.path.basename(args.out), 'size': args.size, 'fps': args.fps,
            'duration': rel(time.monotonic()), 'events': events}
    with open(os.path.splitext(args.out)[0] + '.json', 'w') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print('saved', args.out)
    node.destroy_node()
    rclpy.try_shutdown()
