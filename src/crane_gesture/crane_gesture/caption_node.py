"""動画用の字幕パネル（tkinter）.

- /user_message, /gesture_plan, /gesture_status を購読して
  「ユーザの言葉」「ロボットの返事」「状態（考え中・動作中）」を大きく表示する
- 下部の入力欄から /user_message を送れる（パラメータ show_entry:=true のとき。
  コンテナ内は日本語入力が使えないので既定では隠し、台本は chat --file で送る）
- RViz 用にテーブルのマーカー（/demo_markers）を出す

tkinter はメインスレッドで動かす必要があるため、ROS の spin は別スレッドで回し、
キュー経由で画面を更新する。
"""

import json
import queue
import threading
import tkinter as tk

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import String
from visualization_msgs.msg import Marker

FONT = 'Noto Sans CJK JP'
BG = '#16181d'
FG = '#f2f2f2'
SUB = '#9aa3b2'
ACCENT = {'thinking': '#e0b84f', 'executing': '#5ec2a0', 'done': '#7f8796', 'error': '#e06c6c'}
EMOTION_COLOR = {
    'joy': '#f2c14e', 'happiness': '#f2c14e', 'excitement': '#f29e4e', 'sadness': '#6c9be0',
    'tiredness': '#8c8fd9', 'surprise': '#e07bd0', 'anger': '#e06c6c', 'fear': '#9b7be0',
    'gratitude': '#5ec2a0', 'love': '#f27e9e', 'agree': '#5ec2a0',
}


class CaptionNode(Node):
    def __init__(self, events):
        super().__init__('gesture_caption')
        self.events = events
        self.show_entry = self.declare_parameter('show_entry', False).value
        self.pub = self.create_publisher(String, 'user_message', 10)
        self.create_subscription(String, 'user_message', lambda m: events.put(('user', m.data)), 10)
        self.create_subscription(String, 'gesture_plan', self.on_plan, 10)
        self.create_subscription(String, 'gesture_status', lambda m: events.put(('status', m.data)), 10)
        latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.marker_pub = self.create_publisher(Marker, 'demo_markers', latched)
        self.publish_table()

    def on_plan(self, msg):
        try:
            self.events.put(('plan', json.loads(msg.data)))
        except json.JSONDecodeError:
            pass

    def publish_table(self):
        m = Marker(type=Marker.CUBE, action=Marker.ADD, ns='table', id=0)
        m.header.frame_id = 'world'
        m.pose.position.x, m.pose.position.z = 0.12, -0.011
        m.pose.orientation.w = 1.0
        m.scale.x, m.scale.y, m.scale.z = 0.36, 0.48, 0.02
        m.color.r, m.color.g, m.color.b, m.color.a = 0.72, 0.56, 0.38, 1.0
        self.marker_pub.publish(m)

    def send(self, text):
        self.pub.publish(String(data=text))


class CaptionWindow:
    def __init__(self, root, node, events):
        self.root, self.node, self.events = root, node, events
        root.title('crane_gesture caption')
        root.configure(bg=BG)

        self.user = tk.Label(root, text='', font=(FONT, 26), fg=FG, bg=BG, anchor='w', justify='left')
        self.reply = tk.Label(root, text='', font=(FONT, 30, 'bold'), fg=FG, bg=BG, anchor='w', justify='left')
        meta = tk.Frame(root, bg=BG)
        self.emotion = tk.Label(meta, text='', font=(FONT, 16, 'bold'), fg=BG, bg=BG, padx=10)
        self.status = tk.Label(meta, text='話しかけてください', font=(FONT, 16), fg=SUB, bg=BG)
        self.entry = tk.Entry(root, font=(FONT, 18), bg='#262a33', fg=FG, insertbackground=FG,
                              relief='flat')
        self.entry.bind('<Return>', self.on_enter)

        self.user.pack(fill='x', padx=28, pady=(14, 0))
        self.reply.pack(fill='x', padx=28, pady=(4, 0))
        meta.pack(fill='x', padx=28, pady=(6, 0))
        self.emotion.pack(side='left')
        self.status.pack(side='left', padx=12)
        if node.show_entry:
            self.entry.pack(fill='x', side='bottom', padx=28, pady=(0, 12), ipady=4)
        root.bind('<Configure>', self.on_resize)
        self.entry.focus_set()
        root.after(50, self.poll)

    def on_resize(self, _):
        wrap = max(self.root.winfo_width() - 60, 200)
        self.user.configure(wraplength=wrap)
        self.reply.configure(wraplength=wrap)

    def on_enter(self, _):
        text = self.entry.get().strip()
        if text:
            self.node.send(text)
            self.entry.delete(0, 'end')

    def set_status(self, text, kind):
        self.status.configure(text=text, fg=ACCENT.get(kind, SUB))

    def poll(self):
        while not self.events.empty():
            kind, data = self.events.get()
            if kind == 'user':
                self.user.configure(text=f'あなた：「{data}」')
                self.reply.configure(text='')
                self.emotion.configure(text='', bg=BG)
                self.set_status('Gemini が気持ちを読み取り中…', 'thinking')
            elif kind == 'plan':
                # 字幕ノードの購読が間に合わず /user_message を取りこぼした場合に備え、プランの元発話でも表示
                if data.get('message'):
                    self.user.configure(text=f'あなた：「{data["message"]}」')
                if data.get('reply'):
                    self.reply.configure(text=f'ロボット：「{data["reply"]}」')
                emo = str(data.get('emotion', ''))
                self.emotion.configure(text=emo, bg=EMOTION_COLOR.get(emo.lower(), '#b0b6c2'))
                src = data.get('source', '')
                self.set_status(f'{data.get("intent", "")}　（{src} / {data.get("latency_s", "?")}s）',
                                'thinking')
            elif kind == 'status':
                if data == 'reset':  # 録画開始時に前の字幕を消す（record_demo が送る）
                    self.user.configure(text='')
                    self.reply.configure(text='')
                    self.emotion.configure(text='', bg=BG)
                    self.set_status('話しかけてください', '')
                elif data.startswith('executing'):
                    self.set_status(self.status.cget('text').split('　▶')[0] + '　▶ 動作中', 'executing')
                elif data == 'done':
                    self.set_status(self.status.cget('text').replace('▶ 動作中', '✓ 完了'), 'done')
                elif data.startswith(('rejected', 'controllers', 'goal rejected')):
                    self.set_status(data, 'error')
        self.root.after(50, self.poll)


def main():
    rclpy.init()
    events = queue.Queue()
    node = CaptionNode(events)
    threading.Thread(target=rclpy.spin, args=(node,), daemon=True).start()
    root = tk.Tk()
    CaptionWindow(root, node, events)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
