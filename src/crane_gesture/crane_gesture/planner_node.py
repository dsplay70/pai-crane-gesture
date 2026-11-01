"""/user_message (String) を受け取り、Gemini でジェスチャを生成して /gesture_plan (JSON String) に出す.

LLM 呼び出しは数秒かかるため、購読コールバックではキューに積むだけにし、
別スレッドのワーカで処理する（コールバックをブロックしない）。
"""

import json
import queue
import threading
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from crane_gesture.llm import GesturePlanner, load_dotenv


class PlannerNode(Node):
    def __init__(self):
        super().__init__('gesture_planner')
        env_file = self.declare_parameter('env_file', '/workspace/.env').value
        load_dotenv(env_file)
        model = self.declare_parameter('model', '').value or None
        self.planner = GesturePlanner(model=model)
        self.get_logger().info(
            f'model={self.planner.model} api={"ON" if self.planner.client else "OFF (presets only)"}')

        self.pub = self.create_publisher(String, 'gesture_plan', 10)
        self.create_subscription(String, 'user_message', self.on_message, 10)
        self.jobs = queue.Queue()
        threading.Thread(target=self.worker, daemon=True).start()

    def on_message(self, msg):
        self.get_logger().info(f'user: {msg.data}')
        self.jobs.put(msg.data)

    def worker(self):
        while rclpy.ok():
            text = self.jobs.get()
            t0 = time.monotonic()
            plan = self.planner.plan(text)
            plan['message'] = text
            plan['latency_s'] = round(time.monotonic() - t0, 2)
            self.get_logger().info(
                f'[{plan["source"]}] {plan["latency_s"]}s emotion={plan["emotion"]} '
                f'reply="{plan["reply"]}" keyframes={len(plan["keyframes"])}')
            self.pub.publish(String(data=json.dumps(plan, ensure_ascii=False)))


def main():
    rclpy.init()
    node = PlannerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
