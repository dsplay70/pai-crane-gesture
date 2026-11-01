"""/gesture_plan (JSON String) を検証し、アームとグリッパのコントローラに軌道を送る.

AI の出力はここで必ず gesture.validate を通す（可動域・速度・時間の制約）。
実行中に届いたプランは捨てる（動作の途中で割り込まない）。
"""

import json
import math

from builtin_interfaces.msg import Duration
from control_msgs.action import FollowJointTrajectory
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import String
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

from crane_gesture.gesture import ARM_JOINTS, HAND_JOINT, LIMITS_DEG, validate

ARM_ACTION = '/crane_plus_arm_controller/follow_joint_trajectory'
HAND_ACTION = '/crane_plus_gripper_controller/follow_joint_trajectory'


def to_duration(sec):
    return Duration(sec=int(sec), nanosec=int((sec % 1) * 1e9))


def make_goal(joint_names, times, positions):
    traj = JointTrajectory(joint_names=joint_names)
    for t, p in zip(times, positions):
        traj.points.append(JointTrajectoryPoint(positions=list(p), time_from_start=to_duration(t)))
    return FollowJointTrajectory.Goal(trajectory=traj)


class ExecutorNode(Node):
    def __init__(self):
        super().__init__('gesture_executor')
        self.arm = ActionClient(self, FollowJointTrajectory, ARM_ACTION)
        self.hand = ActionClient(self, FollowJointTrajectory, HAND_ACTION)
        self.status = self.create_publisher(String, 'gesture_status', 10)
        self.create_subscription(String, 'gesture_plan', self.on_plan, 10)
        self.create_subscription(JointState, 'joint_states', self.on_joint_states, 10)
        self.current = None  # 名前 -> 度
        self.pending = 0     # 結果待ちのゴール数

    def on_joint_states(self, msg):
        ros_to_name = {v: k for k, v in ARM_JOINTS.items()}
        ros_to_name[HAND_JOINT[1]] = HAND_JOINT[0]
        cur = {}
        for n, p in zip(msg.name, msg.position):
            if n in ros_to_name:
                cur[ros_to_name[n]] = math.degrees(p)
        if len(cur) == len(LIMITS_DEG):
            self.current = cur

    def report(self, text):
        self.get_logger().info(text)
        self.status.publish(String(data=text))

    def on_plan(self, msg):
        if self.pending:
            self.report('busy: plan dropped')
            return
        plan = json.loads(msg.data)
        try:
            g = validate(plan['keyframes'], start=self.current)
        except (ValueError, KeyError, TypeError) as e:
            self.report(f'rejected: {e}')
            return
        for w in g.warnings:
            self.get_logger().warn(f'validator: {w}')
            self.status.publish(String(data=f'validator: {w}'))
        if not (self.arm.wait_for_server(2.0) and self.hand.wait_for_server(2.0)):
            self.report('controllers not available')
            return

        self.report(f'executing "{plan.get("reply", "")}" ({plan.get("emotion")}) '
                    f'{len(g.times)} points / {g.duration:.1f}s')
        arm_goal = make_goal(list(ARM_JOINTS.values()), g.times, g.arm_rad)
        hand_goal = make_goal([HAND_JOINT[1]], g.times, [[h] for h in g.hand_rad])
        self.pending = 2
        for client, goal in ((self.arm, arm_goal), (self.hand, hand_goal)):
            client.send_goal_async(goal).add_done_callback(self.on_goal_response)

    def on_goal_response(self, future):
        handle = future.result()
        if not handle.accepted:
            self.report('goal rejected by controller')
            self.pending -= 1
            return
        handle.get_result_async().add_done_callback(self.on_result)

    def on_result(self, future):
        self.pending -= 1
        if self.pending == 0:
            self.report('done')


def main():
    rclpy.init()
    node = ExecutorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
