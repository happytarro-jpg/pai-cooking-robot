#!/usr/bin/env python3
"""DetachableJoint の単体テスト: 把持位置で attach → 持ち上げ → 食材が付いてくるか"""
import math
import re
import subprocess
import threading
import time

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration
from moveit_msgs.srv import GetPositionIK
from moveit_msgs.msg import PositionIKRequest, RobotState
from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import JointState
from tf_transformations import quaternion_from_euler

JOINTS = ['crane_plus_joint1', 'crane_plus_joint2', 'crane_plus_joint3', 'crane_plus_joint4']
HOME_Q = [0.0, -1.16, -2.01, -0.73]


def log(m):
    print(f'[dj] {m}', flush=True)


def pose_of(name):
    try:
        out = subprocess.run('timeout 6 ign topic -e -t /world/default/pose/info -n 1',
                             shell=True, capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return None
    m = re.search(r'name:\s*"' + name + r'"\s*\n\s*id:[^\n]*\n\s*position\s*\{\s*x:\s*([-\d.e]+)\s*y:\s*([-\d.e]+)\s*z:\s*([-\d.e]+)', out)
    return None if not m else [float(m.group(1)), float(m.group(2)), float(m.group(3))]


def send_empty(topic):
    r = subprocess.run(f'ign topic -t {topic} -m ignition.msgs.Empty -p "unused: true"',
                       shell=True, capture_output=True, text=True, timeout=8)
    log(f'{topic} -> rc={r.returncode}')


class T(Node):
    def __init__(self):
        super().__init__('dj_t')
        self.arm = ActionClient(self, FollowJointTrajectory,
                                '/crane_plus_arm_controller/follow_joint_trajectory')
        self.ik_cli = self.create_client(GetPositionIK, '/compute_ik')

    def ik(self, x, y, z):
        yaw = math.atan2(y, x) + math.pi
        q = quaternion_from_euler(math.pi, math.pi / 2, yaw)
        req = GetPositionIK.Request()
        ik = PositionIKRequest()
        ik.group_name = 'arm'
        ik.ik_link_name = 'crane_plus_link_endtip'
        ik.robot_state = RobotState()
        ik.robot_state.joint_state = JointState()
        ik.robot_state.joint_state.name = JOINTS
        ik.robot_state.joint_state.position = HOME_Q
        ik.avoid_collisions = False
        ik.timeout.nanosec = 200_000_000
        ps = PoseStamped()
        ps.header.frame_id = 'crane_plus_base'
        ps.pose.position.x, ps.pose.position.y, ps.pose.position.z = x, y, z
        ps.pose.orientation.x, ps.pose.orientation.y = q[0], q[1]
        ps.pose.orientation.z, ps.pose.orientation.w = q[2], q[3]
        ik.pose_stamped = ps
        req.ik_request = ik
        fut = self.ik_cli.call_async(req)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=4.0)
        res = fut.result()
        return None if (res is None or res.error_code.val != 1) else list(res.solution.joint_state.position)[:4]

    def move(self, q, sec=2.0):
        if q is None:
            log('IK failed')
            return False
        self.arm.wait_for_server(timeout_sec=10)
        g = FollowJointTrajectory.Goal()
        tr = JointTrajectory()
        tr.joint_names = JOINTS
        pt = JointTrajectoryPoint()
        pt.positions = [float(v) for v in q]
        pt.time_from_start = Duration(sec=int(sec))
        tr.points = [pt]
        g.trajectory = tr
        fut = self.arm.send_goal_async(g)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=6)
        end = time.time() + sec
        while time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.02)
        return True


def main():
    rclpy.init()
    n = T()
    log('初期: carrot=' + str(pose_of('carrot')))
    for nm in ['carrot', 'tomato', 'broccoli']:
        send_empty(f'/cooking/{nm}/detach')
    time.sleep(2)
    log('detach 後: carrot=' + str(pose_of('carrot')))

    x, y = 0.0, -0.075
    n.move(n.ik(x, y, 0.15), 2.0)
    n.move(n.ik(x, y, 0.045), 1.8)
    log('降下後: carrot=' + str(pose_of('carrot')))
    send_empty('/cooking/carrot/attach')
    time.sleep(1.0)
    log('attach 後: carrot=' + str(pose_of('carrot')))
    n.move(n.ik(x, y, 0.15), 2.0)
    time.sleep(1.0)
    log('持ち上げ後: carrot=' + str(pose_of('carrot')))
    send_empty('/cooking/carrot/detach')
    time.sleep(2.0)
    log('離した後: carrot=' + str(pose_of('carrot')))
    n.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
