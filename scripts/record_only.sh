#!/bin/bash
# シーンを戻して、画面録画しながら調理タスクを実行する
source /opt/ros/humble/setup.bash
source /home/ubuntu/airobot_ws/install/setup.bash
export DISPLAY=:0
cd /home/ubuntu/cooking
mkdir -p videos

echo "=== シーン再生成 ==="
timeout 120 python3 -u build_scene.py 2>&1 | tail -8
timeout 30 python3 set_camera.py 0.40 -0.58 1.30 0.0 -0.10 1.02 2>&1 | tail -1
sleep 2

echo "=== 録画開始 ==="
nohup ffmpeg -y -f x11grab -framerate 20 -video_size 1028x800 -i :0.0 \
  -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p \
  videos/raw_demo.mp4 > /tmp/ffmpeg.log 2>&1 &
FPID=$!
sleep 3

echo "=== 調理 ==="
timeout 260 python3 -u cooking_robot.py 2>&1 | tail -25
sleep 2
kill -INT $FPID 2>/dev/null
sleep 4
echo "=== 録画 ==="
ls -la videos/raw_demo.mp4
ffprobe -v error -show_entries format=duration -of default=nw=1 videos/raw_demo.mp4
