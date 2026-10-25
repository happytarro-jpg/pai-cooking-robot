# お料理ロボット（crane_plus + Ignition Gazebo + MoveIt 2）

ROS 2 Humble / Ignition Gazebo（Fortress 6.16）/ MoveIt 2 で、4 自由度アーム **crane_plus** に
「材料を取る → フライパンへ入れる → 混ぜる」という調理タスクを実行させるプロジェクトです。

- デモ動画: [`docs/demo.mp4`](docs/demo.mp4)
- レポート: [`docs/説明資料_PAI最終課題_happytarro-jpg.pdf`](docs/説明資料_PAI最終課題_happytarro-jpg.pdf)

▶ [デモ動画を見る（docs/demo.mp4）](docs/demo.mp4)

## できること

| 工程 | 内容 |
| --- | --- |
| シーン生成 | 材料 3 種（にんじん・トマト・ブロッコリー）とフライパンを SDF で生成し、テーブル上に配置 |
| 把持 | MoveIt の `/compute_ik` で手先位置を関節角に変換し、`FollowJointTrajectory` で実行 |
| 搬送 | 材料を手先に追従させたままフライパン上部へ移動（瞬間移動しない） |
| 投入 | フライパンの上でグリッパを開き、重力で落下させる |
| 撹拌 | フライパンの上で半径 20 mm の円を描く |

実行結果: **30 動作 / 実時間 約 80 秒**で、終了時に 3 つともフライパン内にあることを Gazebo の姿勢情報で確認。

## 構成

```
ros2/
  cooking_robot.py            タスク本体（IK → 関節軌道、把持、搬送、撹拌）
  build_scene.py              材料・フライパンの SDF 生成 → 配置 → 初期姿勢の取得（scene.json）
  set_camera.py               Gazebo GUI の視点設定（録画構図の固定）
  make_dj_sdf.py              DetachableJoint プラグイン入り SDF の生成（検証用）
  spawn_food.sh               材料とフライパンの生成（DetachableJoint 検証用）
  dj_grasp_test.py            attach / detach の検証スクリプト
  launch/cooking_gazebo.launch.py  食材 → ロボットの順に生成する launch
  models/                     SDF（build_scene.py が生成。リポジトリには含めない）
scripts/
  final_demo.sh               環境リセット → シーン生成 → 録画 → タスク実行
  record_only.sh              シーンを戻して録画しながらタスクを再実行
  render_video.mjs            録画から字幕付きの課題動画を作る
  make_report2.mjs            レポート PDF を生成する
docs/
  demo.mp4                    課題動画（1 分 25 秒・字幕付き）
  説明資料_PAI最終課題_happytarro-jpg.pdf   レポート（4 ページ）
```

## 必要環境

- Docker（`airobotbook/ros2-desktop-ai-robot-book-humble` コンテナ: ROS 2 Humble / Ignition Gazebo 6 / MoveIt 2 / crane_plus）
- VNC でデスクトップに接続できること（Gazebo GUI を表示・録画するため）
- ffmpeg（動画とレポートの生成に使用。Windows 側でも可）

## コンテナへの配置

このリポジトリのファイルは、コンテナ内の ~/cooking に置いて実行します。

```bash
docker cp ros2/. pai_ros2_new:/home/ubuntu/cooking/
docker exec -it pai_ros2_new bash -lc "cd ~/cooking && python3 -m py_compile cooking_robot.py"
```

## 使い方

```bash
# 1. コンテナ起動
docker start pai_ros2_new
docker exec -it pai_ros2_new bash

# 2. ROS 環境
source /opt/ros/humble/setup.bash
source ~/airobot_ws/install/setup.bash
export DISPLAY=:0

# 3. シミュレータ起動（別ターミナル）
ros2 launch crane_plus_gazebo crane_plus_with_table.launch.py

# 4. シーンを作ってタスク実行
python3 ~/cooking/build_scene.py
python3 ~/cooking/set_camera.py
python3 ~/cooking/cooking_robot.py
```

録画込みで一括実行する場合:

```bash
bash scripts/final_demo.sh      # 環境リセット → シーン生成 → 録画 → タスク
bash scripts/record_only.sh     # シーンを戻して録画だけやり直す
```

動画とレポートの再生成（Windows 側）:

```bash
node scripts/render_video.mjs   # docs/demo.mp4 相当を cooking_demo/ に出力
node scripts/make_report2.mjs   # レポート PDF を cooking_demo/ に出力
```

## 実装メモ

### 把持点の計算

crane_plus は 4 自由度のため、手先姿勢は「下向き」に固定し、位置のみを IK で解いています。

```python
q = ik(x, y, z)   # /compute_ik（group=arm, tip=crane_plus_link_endtip）
move(q)           # /crane_plus_arm_controller/follow_joint_trajectory
grip(True/False)  # /crane_plus_gripper_controller/follow_joint_trajectory
```

### 把持の表現（重要）

Gazebo の摩擦把持は再現性が低いため、把持中は**手先の軌道と同じ時間で 20 Hz 補間**して材料の姿勢を更新しています。
離すときは座標を書き換えず、その場でグリッパを開くだけにしました。これにより「材料がフライパンへ飛び込む」ように見える問題を解消しています。

```python
# 改善前（飛んで見える）
set_obj_pose(name, px, py, BASE_Z + 0.045)   # 離す瞬間にフライパンへ移動

# 改善後（追従して運び、その場で落とす）
Follower(name, p0, p1, sec).start()          # 軌道と同じ時間で 20 Hz 補間
grip(False)                                   # 開くだけ。テレポートしない
```

## 限界と今後

- **物理的な把持（固定関節）は未達**です。Ignition 標準の DetachableJoint を実際に組み込みましたが、腕を 10 cm 動かしても材料が追従せず、この環境では成立しませんでした（原因は未特定、候補はレポート 4.3 節）。
- 材料はフライパンの中で積み重なって静止します（落下点を散らすと縁で跳ねて外へ出るため）。
- 今後は「接触直前に attach する運用」「物理エンジンを ODE に切り替えた比較」「自作の把持プラグイン（SuctionGripper 方式）」を試す予定です。

## ライセンス

MIT License（[LICENSE](LICENSE)）。ただし crane_plus のモデル・パッケージは RT Corporation のライセンスに従います。
