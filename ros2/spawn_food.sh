#!/bin/bash
# 食材 3 つを生成する（ロボット生成より前に実行する）
source /opt/ros/humble/setup.bash
source /home/ubuntu/airobot_ws/install/setup.bash
M=/home/ubuntu/cooking/models
for spec in "carrot:0.000:-0.075" "tomato:0.060:-0.080" "broccoli:-0.060:-0.080"; do
  name=${spec%%:*}; rest=${spec#*:}; x=${rest%%:*}; y=${rest#*:}
  ros2 run ros_gz_sim create -world default -file $M/$name.sdf -name $name \
    -x $x -y $y -z 1.050 -allow_renaming false >> /tmp/spawn_food.log 2>&1
  echo "spawn $name ($x,$y)" >> /tmp/spawn_food.log
  sleep 0.5
done
# フライパン
ros2 run ros_gz_sim create -world default -file $M/pan.sdf -name pan \
  -x 0.0 -y -0.145 -z 1.050 -allow_renaming false >> /tmp/spawn_food.log 2>&1
echo "spawn pan" >> /tmp/spawn_food.log
