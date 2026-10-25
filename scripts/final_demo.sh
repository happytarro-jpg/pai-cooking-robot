#!/bin/bash
# 最終デモ: 環境リセット → シーン生成 → 画面録画しながら調理タスクを実行
source /opt/ros/humble/setup.bash
source /home/ubuntu/airobot_ws/install/setup.bash
export DISPLAY=:0
cd /home/ubuntu/cooking
mkdir -p shots videos

echo "=== 1. 停止とクリーンアップ ==="
pkill -9 -f cooking_robot.py 2>/dev/null
pkill -9 -f "ros2 launch crane_plus" 2>/dev/null
pkill -9 -f "ign gazebo" 2>/dev/null
pkill -9 -f move_group 2>/dev/null
pkill -9 -f rviz2 2>/dev/null
pkill -9 -f "ffmpeg -f x11grab" 2>/dev/null
sleep 4
rm -rf /tmp/ign* 2>/dev/null
echo "cleanup done"

echo "=== 2. 起動 ==="
cd /home/ubuntu
nohup ros2 launch crane_plus_gazebo crane_plus_with_table.launch.py > /tmp/crane_launch.log 2>&1 &
for i in $(seq 1 60); do
  if timeout 3 ros2 topic echo /joint_states --once > /dev/null 2>&1; then
    echo "joint_states ready (${i})"
    break
  fi
  sleep 2
done
sleep 4
pkill -f rviz2 2>/dev/null
sleep 3

echo "=== 3. シーン生成 ==="
cd /home/ubuntu/cooking
timeout 120 python3 -u build_scene.py 2>&1 | tail -10
timeout 30 python3 set_camera.py 0.40 -0.58 1.30 0.0 -0.10 1.02 2>&1 | tail -1
sleep 2

echo "=== 4. 録画開始 ==="
nohup ffmpeg -y -f x11grab -framerate 20 -video_size 1028x800 -i :0.0 \
  -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p \
  /home/ubuntu/cooking/videos/raw_demo.mp4 > /tmp/ffmpeg.log 2>&1 &
FPID=$!
sleep 3

echo "=== 5. 調理タスク ==="
timeout 200 python3 -u cooking_robot.py 2>&1 | tee /tmp/cooking.log | tail -45
RC=$?
sleep 3
kill -INT $FPID 2>/dev/null
sleep 4
echo "=== 6. 録画結果 ==="
ls -la /home/ubuntu/cooking/videos/raw_demo.mp4
tail -3 /tmp/ffmpeg.log
echo "task rc=$RC"

