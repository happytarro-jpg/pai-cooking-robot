#!/usr/bin/env python3
"""GUI カメラの視点を設定する（見やすい構図にする）"""
import math
import subprocess
import sys


def look_at(eye, target, up=(0, 0, 1)):
    fx, fy, fz = (target[0] - eye[0], target[1] - eye[1], target[2] - eye[2])
    n = math.sqrt(fx * fx + fy * fy + fz * fz)
    fx, fy, fz = fx / n, fy / n, fz / n
    # right = forward x up
    rx, ry, rz = (fy * up[2] - fz * up[1], fz * up[0] - fx * up[2], fx * up[1] - fy * up[0])
    rn = math.sqrt(rx * rx + ry * ry + rz * rz)
    rx, ry, rz = rx / rn, ry / rn, rz / rn
    # up' = right x forward
    ux, uy, uz = (ry * fz - rz * fy, rz * fx - rx * fz, rx * fy - ry * fx)
    # 回転行列 (列: right, up', forward) → クォータニオン
    m00, m01, m02 = rx, ux, fx
    m10, m11, m12 = ry, uy, fy
    m20, m21, m22 = rz, uz, fz
    tr = m00 + m11 + m22
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        w = 0.25 * s
        x = (m21 - m12) / s
        y = (m02 - m20) / s
        z = (m10 - m01) / s
    elif m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2
        w = (m21 - m12) / s
        x = 0.25 * s
        y = (m01 + m10) / s
        z = (m02 + m20) / s
    elif m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2
        w = (m02 - m20) / s
        x = (m01 + m10) / s
        y = 0.25 * s
        z = (m12 + m21) / s
    else:
        s = math.sqrt(1.0 + m22 - m00 - m11) * 2
        w = (m10 - m01) / s
        x = (m02 + m20) / s
        y = (m12 + m21) / s
        z = 0.25 * s
    return (x, y, z, w)


def set_camera(eye, target):
    q = look_at(eye, target)
    req = (f'name: "camera" position {{ x: {eye[0]} y: {eye[1]} z: {eye[2]} }} '
           f'orientation {{ x: {q[0]:.6f} y: {q[1]:.6f} z: {q[2]:.6f} w: {q[3]:.6f} }}')
    cmd = ('ign topic -t /gui/camera/pose -m ignition.msgs.Pose -p \'' + req + '\'')
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
    print('set_camera:', r.returncode, r.stderr.strip()[:120])
    return q


if __name__ == '__main__':
    eye = (0.42, -0.62, 1.32)
    target = (0.0, -0.10, 1.02)
    if len(sys.argv) >= 7:
        eye = tuple(float(v) for v in sys.argv[1:4])
        target = tuple(float(v) for v in sys.argv[4:7])
    set_camera(eye, target)
