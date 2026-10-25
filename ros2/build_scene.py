#!/usr/bin/env python3
"""お料理シーンの生成（Ignition Gazebo）

- 既存の Wood cube を撤去
- 具材 3 種（にんじん・トマト・ブロッコリー）を配置
- フライパン（底 + 縁 12 枚 + 持ち手）を配置
- 落ち着いた位置を読み取って scene.json に保存
"""
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, 'models')
os.makedirs(MODELS, exist_ok=True)

BASE_Z = 1.015          # crane_plus のベース（world 座標）
TABLE_TOP = 1.0         # テーブル上面（world）

# ベース座標系での配置（x 右, y 奥が負, z 上）
LAYOUT = {
    'carrot':   dict(kind='box', size=(0.035, 0.035, 0.05), color=(0.95, 0.45, 0.10), xy=(0.000, -0.075)),
    'tomato':   dict(kind='cyl', r=0.022, h=0.042, color=(0.85, 0.15, 0.12), xy=(0.060, -0.080)),
    'broccoli': dict(kind='cyl', r=0.025, h=0.045, color=(0.15, 0.55, 0.20), xy=(-0.060, -0.080)),
    'pan':      dict(kind='pan', r=0.045, h=0.012, color=(0.13, 0.13, 0.15), xy=(0.000, -0.145)),
}


def sdf_object(name, spec):
    x, y = spec['xy']
    col = ' '.join(f'{c:.3f}' for c in spec['color']) + ' 1'
    z_world = TABLE_TOP + 0.06          # 少し上から落とす
    if spec['kind'] == 'box':
        w, d, h = spec['size']
        geom = f'<box><size>{w} {d} {h}</size></box>'
    elif spec['kind'] == 'cyl':
        geom = f'<cylinder><radius>{spec["r"]}</radius><length>{spec["h"]}</length></cylinder>'
    else:
        geom = None

    visuals = []
    collisions = []
    if spec['kind'] == 'pan':
        r, h = spec['r'], spec['h']
        visuals.append(f'<visual name="base"><geometry><cylinder><radius>{r}</radius><length>{h}</length></cylinder></geometry>'
                       f'<material><diffuse>{col}</diffuse><ambient>{col}</ambient></material></visual>')
        collisions.append(f'<collision name="base"><geometry><cylinder><radius>{r}</radius><length>{h}</length></cylinder></geometry></collision>')
        n = 12
        for i in range(n):
            import math
            a = 2 * math.pi * i / n
            cx, cy = r * math.cos(a) * 0.96, r * math.sin(a) * 0.96
            visuals.append(f'<visual name="wall{i}"><pose>{cx:.4f} {cy:.4f} {h/2 + 0.011:.4f} 0 0 {a + 1.5708:.4f}</pose>'
                           f'<geometry><box><size>0.024 0.006 0.022</size></box></geometry>'
                           f'<material><diffuse>{col}</diffuse><ambient>{col}</ambient></material></visual>')
            collisions.append(f'<collision name="wall{i}"><pose>{cx:.4f} {cy:.4f} {h/2 + 0.011:.4f} 0 0 {a + 1.5708:.4f}</pose>'
                              f'<geometry><box><size>0.024 0.006 0.022</size></box></geometry></collision>')
        # 持ち手
        visuals.append(f'<visual name="grip"><pose>{r + 0.035:.4f} 0 {h/2:.4f} 0 0 0</pose>'
                       f'<geometry><box><size>0.075 0.012 0.010</size></box></geometry>'
                       f'<material><diffuse>{col}</diffuse><ambient>{col}</ambient></material></visual>')
        collisions.append(f'<collision name="grip"><pose>{r + 0.035:.4f} 0 {h/2:.4f} 0 0 0</pose>'
                          f'<geometry><box><size>0.075 0.012 0.010</size></box></geometry></collision>')
    else:
        visuals.append(f'<visual name="v"><geometry>{geom}</geometry>'
                       f'<material><diffuse>{col}</diffuse><ambient>{col}</ambient></material></visual>')
        collisions.append(f'<collision name="c"><geometry>{geom}</geometry></collision>')

    mass = 0.05
    return f"""<?xml version="1.0" ?>
<sdf version="1.6">
  <model name="{name}">
    <static>false</static>
    <link name="link">
      <inertial><mass>{mass}</mass><inertia><ixx>1e-5</ixx><iyy>1e-5</iyy><izz>1e-5</izz></inertia></inertial>
      {''.join(visuals)}
      {''.join(collisions)}
    </link>
  </model>
</sdf>
"""


def run(cmd, timeout=20):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        class R:
            stdout = ''
            stderr = 'timeout'
        return R()


def ign_service(service, reqtype, req):
    return run(f'ign service -s {service} --reqtype {reqtype} --reptype ignition.msgs.Boolean '
               f'--timeout 1000 --req \'{req}\'', timeout=12)


def world_poses():
    out = run('ign topic -e -t /world/default/pose/info -n 1', timeout=10).stdout
    poses = {}
    for m in re.finditer(r'name:\s*"([^"]+)"\s*\n\s*id:[^\n]*\n\s*position\s*\{\s*x:\s*([-\d.e]+)\s*y:\s*([-\d.e]+)\s*z:\s*([-\d.e]+)', out):
        poses[m.group(1)] = [float(m.group(2)), float(m.group(3)), float(m.group(4))]
    return poses


def main():
    print('=== 既存オブジェクトの撤去 ===')
    for nm in ['wood_cube_5cm', 'carrot', 'tomato', 'broccoli', 'pan']:
        r = ign_service('/world/default/remove', 'ignition.msgs.Entity', f'name: "{nm}" type: 2')
        print(f'  {nm}: {r.stdout.strip()[:40]}')
        time.sleep(0.3)

    print('=== SDF 生成 ===')
    for name, spec in LAYOUT.items():
        path = os.path.join(MODELS, f'{name}.sdf')
        with open(path, 'w') as f:
            f.write(sdf_object(name, spec))
        print(' ', path)

    print('=== スポーン ===')
    src = ''   # 親プロセスで ROS を source 済み
    for name, spec in LAYOUT.items():
        x, y = spec['xy']
        z = TABLE_TOP + 0.05
        cmd = (src + f'ros2 run ros_gz_sim create -world default -file {MODELS}/{name}.sdf '
               f'-name {name} -x {x:.4f} -y {y:.4f} -z {z:.4f} -allow_renaming false')
        r = run(cmd)
        print(f'  {name}: {r.stdout.strip()[:120]} {r.stderr.strip()[:120]}')
        time.sleep(0.6)

    time.sleep(4.0)
    poses = world_poses()
    print('  poses:', list(poses)[:8])
    if not poses:
        raw = run('ign topic -e -t /world/default/pose/info -n 1').stdout[:600]
        print('  raw:', raw.replace('\n', ' ')[:400])
    scene = {}
    for name in LAYOUT:
        if name in poses:
            w = poses[name]
            scene[name] = {
                'world': [round(v, 4) for v in w],
                'base': [round(w[0], 4), round(w[1], 4), round(w[2] - BASE_Z, 4)],
                'spec': {k: (list(v) if isinstance(v, tuple) else v) for k, v in LAYOUT[name].items()},
            }
        else:
            print(f'  !! {name} の姿勢が取得できません')
    with open(os.path.join(HERE, 'scene.json'), 'w') as f:
        json.dump(scene, f, indent=2)
    print('=== シーン ===')
    print(json.dumps({k: v['base'] for k, v in scene.items()}, indent=1))


if __name__ == '__main__':
    main()
