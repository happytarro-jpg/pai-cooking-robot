#!/usr/bin/env python3
"""お料理ロボット（crane_plus + Ignition Gazebo + MoveIt）

材料 3 つをフライパンへ入れて、最後に混ぜる。

把持の扱い:
  把持中は、手先の軌道と同じ時間で対象の姿勢を補間して更新する（20Hz）。
  対象はグリッパに貼り付いたまま運ばれ、離すとその場から重力でフライパンへ落ちる。
  瞬間移動はさせない。

    python3 cooking_robot.py
"""
import json
import math
import os
import re
import subprocess
import sys
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

R = math.pi / 180
GRIPPER_OPEN = -40.62 * R + 0.001
GRIPPER_CLOSE = 38.27 * R - 0.001
JOINTS = ['crane_plus_joint1', 'crane_plus_joint2', 'crane_plus_joint3', 'crane_plus_joint4']
GRIPPER_JOINT = ['crane_plus_joint_hand']
HOME_Q = [0.0, -1.16, -2.01, -0.73]

Z_ABOVE = float(os.environ.get('Z_ABOVE', 0.155))
Z_GRASP = float(os.environ.get('Z_GRASP', 0.045))
Z_PLACE = float(os.environ.get('Z_PLACE', 0.072))
Z_STIR = float(os.environ.get('Z_STIR', 0.110))
GRASP_DZ = 0.018
BASE_Z = 1.015
HERE = os.path.dirname(os.path.abspath(__file__))


def log(msg):
    print(f'[cooking] {msg}', flush=True)


def set_obj_pose(name, x, y, z_world):
    req = (f'name: "{name}" position {{ x: {x:.4f} y: {y:.4f} z: {z_world:.4f} }} '
           f'orientation {{ w: 1 }}')
    subprocess.run('ign service -s /world/default/set_pose --reqtype ignition.msgs.Pose '
                   '--reptype ignition.msgs.Boolean --timeout 200 --req \'' + req + '\'',
                   shell=True, capture_output=True, text=True, timeout=6)


def world_poses():
    try:
        out = subprocess.run('timeout 6 ign topic -e -t /world/default/pose/info -n 1',
                             shell=True, capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return {}
    poses = {}
    for m in re.finditer(r'name:\s*"([^"]+)"\s*\n\s*id:[^\n]*\n\s*position\s*\{\s*x:\s*([-\d.e]+)\s*y:\s*([-\d.e]+)\s*z:\s*([-\d.e]+)', out):
        poses[m.group(1)] = [float(m.group(2)), float(m.group(3)), float(m.group(4))]
    return poses


class Follower(threading.Thread):
    """対象を手先の軌道に合わせて動かす（2 点間を等速で補間）"""

    def __init__(self, name, p0, p1, sec):
        super().__init__(daemon=True)
        self.name, self.p0, self.p1, self.sec = name, p0, p1, sec
        self.stop_flag = threading.Event()
        self.n = 0

    def run(self):
        t0 = time.time()
        while not self.stop_flag.is_set():
            u = min(1.0, (time.time() - t0) / max(self.sec, 0.1))
            x = self.p0[0] + (self.p1[0] - self.p0[0]) * u
            y = self.p0[1] + (self.p1[1] - self.p0[1]) * u
            z = self.p0[2] + (self.p1[2] - self.p0[2]) * u
            set_obj_pose(self.name, x, y, BASE_Z + z - GRASP_DZ)
            self.n += 1
            time.sleep(0.05)

    def stop(self):
        self.stop_flag.set()
        self.join(timeout=1.0)


class CookingRobot(Node):
    def __init__(self):
        super().__init__('cooking_robot')
        self.arm = ActionClient(self, FollowJointTrajectory,
                                '/crane_plus_arm_controller/follow_joint_trajectory')
        self.grip_cli = ActionClient(self, FollowJointTrajectory,
                                     '/crane_plus_gripper_controller/follow_joint_trajectory')
        self.ik_cli = self.create_client(GetPositionIK, '/compute_ik')
        self.n_moves = 0

    # ---- IK ----
    def ik(self, x, y, z, yaw=None):
        yaw = (math.atan2(y, x) + math.pi) if yaw is None else yaw
        q = quaternion_from_euler(math.pi, math.pi / 2, yaw)
        req = GetPositionIK.Request()
        ik = PositionIKRequest()
        ik.group_name = 'arm'
        ik.ik_link_name = 'crane_plus_link_endtip'
        ik.robot_state = RobotState()
        ik.robot_state.joint_state = JointState()
        ik.robot_state.joint_state.name = JOINTS
        ik.robot_state.joint_state.position = [float(v) for v in HOME_Q]
        ik.avoid_collisions = False
        ik.timeout.sec = 0
        ik.timeout.nanosec = 200_000_000
        ps = PoseStamped()
        ps.header.frame_id = 'crane_plus_base'
        ps.pose.position.x = float(x)
        ps.pose.position.y = float(y)
        ps.pose.position.z = float(z)
        ps.pose.orientation.x = q[0]
        ps.pose.orientation.y = q[1]
        ps.pose.orientation.z = q[2]
        ps.pose.orientation.w = q[3]
        ik.pose_stamped = ps
        req.ik_request = ik
        fut = self.ik_cli.call_async(req)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=4.0)
        res = fut.result()
        if res is None or res.error_code.val != 1:
            return None
        return list(res.solution.joint_state.position)[:4]

    # ---- 実行 ----
    def send(self, client, names, positions, sec):
        client.wait_for_server(timeout_sec=8.0)
        goal = FollowJointTrajectory.Goal()
        tr = JointTrajectory()
        tr.joint_names = list(names)
        pt = JointTrajectoryPoint()
        pt.positions = [float(v) for v in positions]
        pt.velocities = [0.0] * len(names)
        pt.time_from_start = Duration(sec=int(sec), nanosec=int((sec % 1) * 1e9))
        tr.points = [pt]
        goal.trajectory = tr
        fut = client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=6.0)
        gh = fut.result()
        ok = gh is not None and gh.accepted
        end = time.time() + sec
        while time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.02)
        return ok

    def move_q(self, q, label='', sec=2.2, name=None, frm=None, to=None):
        if q is None:
            log(f'{label}: IK 失敗')
            return False
        client = self.arm
        client.wait_for_server(timeout_sec=8.0)
        goal = FollowJointTrajectory.Goal()
        tr = JointTrajectory()
        tr.joint_names = JOINTS
        pt = JointTrajectoryPoint()
        pt.positions = [float(v) for v in q]
        pt.velocities = [0.0] * len(JOINTS)
        pt.time_from_start = Duration(sec=int(sec), nanosec=int((sec % 1) * 1e9))
        tr.points = [pt]
        goal.trajectory = tr
        fut = client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=6.0)
        gh = fut.result()
        ok = gh is not None and gh.accepted
        follower = None
        if name and frm and to:
            follower = Follower(name, frm, to, sec)
            follower.start()
        end = time.time() + sec
        while time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.02)
        if follower:
            follower.stop()
            log(f'  （{name} を {follower.n} 回追従）')
        self.n_moves += 1
        log(f'{label}: {"ok" if ok else "NG"}')
        return ok

    def move_xyz(self, x, y, z, label='', sec=2.2, name=None, frm=None):
        return self.move_q(self.ik(x, y, z), f'{label} ({x:+.3f},{y:+.3f},{z:+.3f})', sec,
                           name, frm, (x, y, z))

    def grip(self, closed, label=''):
        ok = self.send(self.grip_cli, GRIPPER_JOINT,
                       [GRIPPER_CLOSE if closed else GRIPPER_OPEN], 1.2)
        log(f'{"close" if closed else "open "} グリッパ {label}: {"ok" if ok else "NG"}')
        time.sleep(0.3)
        return ok


def main():
    rclpy.init()
    node = CookingRobot()
    scene = json.load(open(os.path.join(HERE, 'scene.json')))
    names = ['carrot', 'tomato', 'broccoli']
    px, py, _ = scene['pan']['base']
    log(f'材料: {[(n, scene[n]["base"][:2]) for n in names]}  フライパン: ({px:+.3f},{py:+.3f})')

    t0 = time.time()
    log('=== 開始 ===')
    node.move_q(HOME_Q, 'home')
    node.grip(False, 'init')

    # フライパン内の落下位置（縁の内側に散らす）
    drop = {'carrot': (0.000, 0.000), 'tomato': (0.000, 0.000), 'broccoli': (0.000, 0.000)}
    for name in names:
        x, y, _ = scene[name]['base']
        dx, dy = drop[name]
        tx, ty = px + dx, py + dy
        log(f'--- {name} をフライパンへ（落下点 {tx:+.3f},{ty:+.3f}） ---')
        node.move_xyz(x, y, Z_ABOVE, f'{name}_above', 2.2)
        node.move_xyz(x, y, Z_GRASP, f'{name}_down', 1.8, name=name, frm=(x, y, Z_ABOVE))
        node.grip(True, name)
        node.move_xyz(x, y, Z_ABOVE, f'{name}_lift', 2.0, name=name, frm=(x, y, Z_GRASP))
        node.move_xyz(tx, ty, Z_ABOVE, f'{name}_to_pan', 2.6, name=name, frm=(x, y, Z_ABOVE))
        node.move_xyz(tx, ty, Z_PLACE, f'{name}_in_pan', 1.8, name=name, frm=(tx, ty, Z_ABOVE))
        node.grip(False, name)          # その場で離す → 重力でフライパンへ落ちる
        time.sleep(1.4)                 # 落下・整定を待つ
        p = world_poses().get(name)
        if p:
            log(f'  落下後 {name}: base_z={p[2] - BASE_Z:+.3f}')
        node.move_xyz(tx, ty, Z_ABOVE, f'{name}_retreat', 1.6)

    log('--- 混ぜる ---')
    for i in range(10):
        a = 2 * math.pi * i / 10
        node.move_xyz(px + 0.020 * math.cos(a), py + 0.020 * math.sin(a), Z_STIR, f'stir{i}', 1.3)
    node.move_q(HOME_Q, 'home_final')

    poses = world_poses()
    log(f'=== 完了  動作 {node.n_moves} 回 / 実時間 {time.time() - t0:.1f} 秒 ===')
    for name in names:
        if name in poses:
            log(f'  {name}: base=({poses[name][0]:+.3f},{poses[name][1]:+.3f},{poses[name][2] - BASE_Z:+.3f})')
    log('=== END ===')
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
