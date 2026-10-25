#!/usr/bin/env python3
"""crane_plus の SDF に DetachableJoint プラグインを挿入する"""
import os

HERE = '/home/ubuntu/cooking/model'
SRC = os.path.join(HERE, 'crane_plus.sdf')
DST = os.path.join(HERE, 'crane_plus_dj.sdf')
GRIPPER_LINK = os.environ.get('GRIPPER_LINK', 'crane_plus_link_hand')
ITEMS = ['carrot', 'tomato', 'broccoli']
CHILD_LINK = 'link'

sdf = open(SRC, encoding='utf-8').read()
plugins = []
for name in ITEMS:
    plugins.append(f'''    <plugin filename="ignition-gazebo-detachable-joint-system"
            name="ignition::gazebo::systems::DetachableJoint">
      <parent_link>{GRIPPER_LINK}</parent_link>
      <child_model>{name}</child_model>
      <child_link>{CHILD_LINK}</child_link>
      <detach_topic>/cooking/{name}/detach</detach_topic>
      <attach_topic>/cooking/{name}/attach</attach_topic>
      <output_topic>/cooking/{name}/state</output_topic>
    </plugin>
''')
sdf = sdf.replace('  </model>\n</sdf>', ''.join(plugins) + '  </model>\n</sdf>')
if 'DetachableJoint' not in sdf:
    raise SystemExit('insert failed: </model> pattern not found')
open(DST, 'w', encoding='utf-8').write(sdf)
print('wrote', DST, len(sdf), 'bytes,', sdf.count('DetachableJoint'), 'plugins')
