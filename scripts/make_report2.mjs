/**
 * make_report2.mjs — レポート（お料理ロボット実装編）
 * 第4回・第5回の演習記述は含めない。実装と改善の記録に絞る。
 */
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { spawnSync } from 'node:child_process';
import { encodePNG } from '../cooking-robot/src/lib/png.js';

const ROOT = path.resolve(import.meta.dirname, '..');
const OUT = path.join(ROOT, 'cooking_demo');
const FFMPEG = process.env.FFMPEG
  || 'C:\\Users\\SUN HANYU\\AppData\\Roaming\\kingsoft\\wps\\addons\\pool\\win-i386\\aivideo_3.1.0.33\\aivideo\\ffmpeg.exe';

const FONT_R = 'C\\\\:/Windows/Fonts/YuGothM.ttc';
const FONT_B = 'C\\\\:/Windows/Fonts/YuGothB.ttc';
const MONO = 'C\\\\:/Windows/Fonts/consola.ttf';
const PW = 1488, PH = 2105, MX = 100, MT = 100, MB = 96, CW = PW - MX * 2;
const SZ = { body: 25, h1: 42, h2: 31, cap: 20, title: 46, sub: 25, mono: 19 };
const C = { text: '0x1F2937', head: '0x111827', accent: '0xC2410C', orange: '0xE07A2B', gray: '0x6B7280', line: '0xD8DEE6', code: '0x0F172A' };

const isWide = (cp) => (cp >= 0x3000 && cp <= 0x30ff) || (cp >= 0x3400 && cp <= 0x9fff) || (cp >= 0xff00 && cp <= 0xff60) || (cp >= 0x300 && cp <= 0x36f);
function measure(t, s) { let w = 0; for (const ch of t) { const cp = ch.codePointAt(0); w += cp < 128 ? s * (ch === ' ' ? 0.28 : 0.55) : isWide(cp) ? s : s * 0.85; } return w; }
function wrap(t, s, width) {
  const out = []; let cur = '', cw = 0;
  for (const ch of t) { const w = measure(ch, s); if (cw + w > width && cur) { out.push(cur); cur = ''; cw = 0; } cur += ch; cw += w; }
  if (cur) out.push(cur); return out;
}
const pngSize = (p) => { const b = fs.readFileSync(p); return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) }; };

/* ---------- 図（動画から切り出す） ---------- */
const video = path.join(OUT, 'cooking_demo.mp4');
const figs = {};
for (const [k, t] of [['f_scene', 8], ['f_grasp', 42], ['f_pan', 72]]) {
  const dst = path.join(OUT, `${k}.png`);
  const r = spawnSync(FFMPEG, ['-hide_banner', '-loglevel', 'error', '-y', '-ss', String(t), '-i', video, '-frames:v', '1', dst], { stdio: 'ignore' });
  if (r.status === 0 && fs.existsSync(dst)) figs[k] = dst;
}

/* ---------- 本文 ---------- */
const blocks = [];
const H1 = (t) => blocks.push({ t: 'h1', text: t });
const H2 = (t) => blocks.push({ t: 'h2', text: t });
const P = (t) => blocks.push({ t: 'p', text: t });
const B = (l) => blocks.push({ t: 'b', list: l });
const CODE = (l) => blocks.push({ t: 'code', list: l });
const FIG = (k, cap) => blocks.push({ t: 'fig', key: k, cap });

blocks.push({ t: 'title', text: 'お料理ロボット', sub: '食材が「飛ぶ」問題の改善と、その限界の記録' });

H1('1. 概要');
P('ROS 2 Humble / Ignition Gazebo（Fortress 6.16）/ MoveIt 2 の環境で、crane_plus（4 自由度＋グリッパ）に調理タスクを実行させた。材料 3 つ（にんじん・トマト・ブロッコリー）をテーブルから取ってフライパンへ入れ、最後にフライパンの上で混ぜる。');
P('本レポートは実装の記録と、動画で「食材がフライパンへ飛び込んで見える」問題に対して行った改善、および改善しきれなかった理由をまとめたものである。');

H1('2. 実装したもの（コード一式）');
H2('2.1 構成');
CODE([
  'cooking/',
  '  cooking_robot.py      タスク本体（IK→関節軌道、把持、搬送、撹拌）',
  '  build_scene.py        食材とフライパンの SDF 生成・配置・初期姿勢の取得',
  '  set_camera.py         Gazebo GUI の視点設定（録画構図の固定）',
  '  final_demo.sh         環境リセット→シーン生成→録画→タスク実行の一括スクリプト',
  '  record_only.sh        シーンを戻して録画しながらタスクを再実行',
  '  make_dj_sdf.py        DetachableJoint プラグインを挿入した SDF の生成',
  '  launch/cooking_gazebo.launch.py  食材→ロボットの順に生成する launch',
  '  dj_grasp_test.py      attach/detach の検証スクリプト',
  '  models/*.sdf          材料 3 種とフライパンのモデル',
]);
H2('2.2 タスク実行の流れ');
P('把持点は MoveIt の /compute_ik で関節角に変換し、ros2_control の FollowJointTrajectory で実行する。crane_plus は 4 自由度なので、手先姿勢は「下向き」に固定して位置のみを解いた。');
CODE([
  'ik(x, y, z)      -> /compute_ik（group=arm, tip=crane_plus_link_endtip）',
  'move(q)          -> /crane_plus_arm_controller/follow_joint_trajectory',
  'grip(close/open) -> /crane_plus_gripper_controller/follow_joint_trajectory',
  '',
  '各材料について: 真上 -> 降下 -> 閉じる -> 持ち上げ -> フライパン上へ -> 離す',
  '最後にフライパン上で半径 20 mm の円を描く（撹拌）',
]);
P('実行結果は 30 動作・実時間 約 80 秒で、終了時に 3 つともフライパン内（Gazebo の姿勢情報で z ≈ 0.065 m）にあることを確認した。');
FIG('f_scene', '図1　シーン全景。左がフライパン、中央が材料、奥がアーム。');
FIG('f_grasp', '図2　材料を把持してフライパンへ運ぶ。');

H1('3. 食材が「飛ぶ」問題と改善');
H2('3.1 原因');
B([
  '把持中の食材の位置を、移動の始点と終点の 2 点だけで更新していた。腕は連続的に動くのに食材は 2 点間を直線で飛ぶため、指から外れて見えた。',
  '離す瞬間に、食材をフライパンの座標へ直接テレポートさせていた。これが「飛び込む」動きの直接の原因である。',
  '指で挟む物理的な把持は行っておらず、位置を上書きしているだけだった。',
]);
H2('3.2 改善内容');
B([
  '把持中は、腕の軌道と同じ時間で食材の位置を 20 Hz で補間して更新するようにした（Follower スレッド）。腕と食材が同じ速さで動くため、指から外れない。',
  '降下の段階から追従を開始し、食材が指に挟まったまま下りるようにした。',
  '離すときはテレポートをやめ、その場でグリッパを開くだけにした。食材は手先の高さから重力で落ちてフライパンに入る。',
]);
CODE([
  '# 改善前（飛んで見える）',
  'set_obj_pose(name, px, py, BASE_Z + 0.045)   # 離す瞬間にフライパンへ移動',
  '',
  '# 改善後（追従して運び、その場で落とす）',
  'Follower(name, p0, p1, sec).start()          # 軌道と同じ時間で 20 Hz 補間',
  'grip(False)                                   # 開くだけ。テレポートしない',
]);
P('この変更で、動画上は「食材が指に挟まれて持ち上がり、運ばれ、離すと自然に落ちる」動きになった。瞬間移動はなくなっている。');
FIG('f_pan', '図3　フライパンの上で混ぜる。材料はすでに鍋の中にある。');

H1('4. なぜ完全な「物理把持」にできなかったか');
P('ChatGPT からの修正アドバイスにあったとおり、根本的な解決は「位置の上書き」をやめて固定関節で握ることである。Ignition Gazebo 標準の DetachableJoint を使う実装を実際に試した。');
H2('4.1 試した内容');
CODE([
  'ign sdf -p crane_plus.urdf > crane_plus.sdf        # URDF から SDF を生成',
  'make_dj_sdf.py                                     # 3 個のプラグインを挿入',
  '  <parent_link>crane_plus_link_hand</parent_link>',
  '  <child_model>carrot</child_model><child_link>link</child_link>',
  '  <detach_topic>/cooking/carrot/detach</detach_topic>',
  '  <attach_topic>/cooking/carrot/attach</attach_topic>',
  'cooking_gazebo.launch.py                           # 食材→ロボットの順に生成',
  'attach(name) / detach(name)                        # Empty メッセージを publish',
]);
H2('4.2 結果（実測）');
P('プラグインはロードされ、/cooking/carrot/state などのトピックも広告された。しかし attach / detach を送っても食材の位置は変化しなかった。');
CODE([
  'start        carrot = (-0.0126, -0.0606, 1.0400)',
  'attach 後     carrot = (-0.0127, -0.0606, 1.0400)',
  '持ち上げ後    carrot = (-0.0126, -0.0605, 1.0402)   # 腕は 10 cm 移動',
  'detach 後     carrot = (-0.0128, -0.0607, 1.0400)',
]);
H2('4.3 できなかった理由（候補）');
P('実測できたのは「attach / detach を送っても食材が動かなかった」という事実までで、原因は特定できていない。とくに、attach しても何も動かなかった点は、DART や再接続の制約だけでは説明しきれない。以下は候補である。');
B([
  'この world の物理エンジンは DART（DartzBoxedLcpSolver）である。ChatGPT からの修正アドバイスでも、DetachableJoint では親モデルの self_collide や DART の既知の問題に注意が必要と指摘されていた。',
  '同じアドバイスでは「接触している間の再接続は未対応」とされていた。把持は指と食材の接触が前提なので、attach の瞬間に失敗しやすい。',
  'プラグインは親リンクを持つモデル（crane_plus）に書く必要があり、ロボットの SDF を差し替えて再生成する必要がある。今回は launch を自作して対応したが、子モデルをロボット生成より先に置く順序制約も生じた。',
  'トピック名やメッセージ型の不一致、プラグインが購読していない可能性も残る。/cooking/*/state は広告されていたが、メッセージが実際に流れていたかは未確認である。',
  '摩擦係数・接触剛性の調整で挟む方式も検討したが、軽い物体では滑る例が多く、結果が環境に依存するため採用しなかった。',
]);
P('以上から、原理的に不可能ではないが、この環境では「固定関節で握る」方式を安定動作させられなかった。納品した動画は 3.2 の追従方式である。');

H1('5. まとめと今後');
B([
  '「飛んで見える」問題は、離す瞬間のテレポートをやめ、軌道と同じ時間で 20 Hz 追従させることで解消した。',
  '一方、物理的に握る方式（DetachableJoint）は、プラグインのロードまでは確認できたが、腕を動かしても食材が追従せず、この環境では成立しなかった。',
  '次に試すべきは、指が触れる直前に attach する運用、物理エンジンを ODE に切り替えた比較、自作の把持プラグイン（SuctionGripper 方式）である。',
]);

H1('6. 「把持動作改善調査レポート」の指摘への対応');
P('別途いただいた調査レポート（Priority A / B の提案）について、実装したもの・しなかったもの・試して逆効果だったものを整理する。');
B([
  'A1 各制御ステップで手先姿勢を取得して追従 → 実装した（軌道と同じ時間で Follower が補間）。ただし 50 Hz に上げると、直線補間が腕の曲線経路から外れて食材が鍋の縁に衝突し、鍋の外へ弾き出される事例が出たため 20 Hz に戻した。',
  'A2 急移動をやめ、持ち上げ高さ・フライパン上方・落下位置のウェイポイントを設ける → 実装済み（lift → to_pan → in_pan）。',
  'A3 リリース時に座標を書き換えない → 実装済み。現在位置でグリッパを開くだけにした。',
  'A4 リリース点は縁の内側・底面より少し上 → 実装済み（手先 z=0.072、鍋の縁 0.034）。',
  'A5 把持中は閉じたまま、リリース後のみ開く／開閉完了を待つ → 実装済み（grip は軌道完了まで待つ）。',
  'B1 接触確認後に attach → 未実装（接触センサーを付けていない）。',
  'B2 固定ジョイントで attach/detach → 試装したが、腕を動かしても食材が追従せず成立しなかった（4 章）。',
  'B3 プラグインのバージョン確認 → 実施済み（Gazebo Sim 6.16 / Fortress にプラグインは存在）。',
  '3.1〜3.5 の GitHub 例の調査 → 確認済み。crane_plus の pick_and_place の段階構成は本実装の流れと同等。Ignition 対応の例（DetachableJoint / AttachablePlugin）は Harmonic 前提が多く、本環境では未検証。',
]);
P('また、落下位置を鍋の中で散らす（3 点に分ける）案も試したが、縁付近に落ちた食材が跳ねて鍋の外へ出たため、単一の落下点に戻した。現状は 3 つが鍋の中で積み重なる形で静止する。');
H1('7. 再現手順');
CODE([
  '$ docker start pai_ros2_new && docker exec -it pai_ros2_new bash',
  '  source /opt/ros/humble/setup.bash',
  '  source ~/airobot_ws/install/setup.bash',
  '  ros2 launch crane_plus_gazebo crane_plus_with_table.launch.py',
  '  python3 ~/cooking/build_scene.py      # 材料とフライパンを配置',
  '  python3 ~/cooking/set_camera.py       # 視点を固定',
  '  python3 ~/cooking/cooking_robot.py    # タスク実行',
]);

/* ---------- レイアウト ---------- */
const pages = [[]]; let y = MT;
const page = () => pages[pages.length - 1];
const newPage = () => { pages.push([]); y = MT; };
function place(op, h) { if (y + h > PH - MB) newPage(); op.y = y; page().push(op); y += h; return op; }

for (const b of blocks) {
  if (b.t === 'title') {
    place({ t: 'text', text: b.text, x: MX, size: SZ.title, bold: true, color: C.head }, 62);
    place({ t: 'text', text: b.sub, x: MX, size: SZ.sub, bold: true, color: C.orange }, 52);
    place({ t: 'rect', x: MX, w: CW, h: 3, color: C.line }, 22);
  } else if (b.t === 'h1') {
    if (y > MT) y += 20;
    place({ t: 'text', text: b.text, x: MX, size: SZ.h1, bold: true, color: C.head }, 54);
    place({ t: 'rect', x: MX, w: 110, h: 5, color: C.orange }, 26);
  } else if (b.t === 'h2') {
    y += 8;
    place({ t: 'text', text: b.text, x: MX, size: SZ.h2, bold: true, color: C.accent }, 42);
  } else if (b.t === 'p') {
    for (const line of wrap(b.text, SZ.body, CW)) place({ t: 'text', text: line, x: MX, size: SZ.body, color: C.text }, 39);
    y += 4;
  } else if (b.t === 'b') {
    for (const item of b.list) {
      const lines = wrap(item.replace(/\*\*/g, ''), SZ.body - 1, CW - 30);
      if (y + 44 > PH - MB) newPage();
      lines.forEach((line, i) => {
        if (i === 0) place({ t: 'dot', x: MX + 4 }, 0);
        place({ t: 'text', text: line, x: MX + 30, size: SZ.body - 1, color: C.text }, i === 0 ? 36 : 37);
      });
      y += 4;
    }
    y += 4;
  } else if (b.t === 'code') {
    const lh = 28;
    const h = b.list.length * lh + 24;
    if (y + h > PH - MB) newPage();
    page().push({ t: 'rect', x: MX, y, w: CW, h, color: C.code, fill: true });
    b.list.forEach((line, i) => page().push({ t: 'text', text: line, x: MX + 16, y: y + 12 + i * lh, size: SZ.mono, color: '0xE5E7EB', mono: true }));
    y += h + 14;
  } else if (b.t === 'fig') {
    const p = figs[b.key];
    if (!p) continue;
    const d = pngSize(p);
    const w = CW;
    const h0 = Math.round((w * d.h) / d.w);
    const hh = Math.min(h0, 600);
    const ww = Math.round((hh * d.w) / d.h);
    if (y + hh + 40 > PH - MB) newPage();
    place({ t: 'image', path: p, w: ww, h: hh, x: MX + (CW - ww) / 2 }, hh + 8);
    for (const line of wrap(b.cap, SZ.cap, CW)) place({ t: 'text', text: line, x: MX + (CW - measure(line, SZ.cap)) / 2, size: SZ.cap, color: C.gray }, 26);
    y += 18;
  }
}

/* ---------- 描画 ---------- */
const bg = path.join(OUT, 'rbg.png');
fs.writeFileSync(bg, encodePNG(PW, PH, new Uint8Array(PW * PH * 3).fill(255)));
const rendered = pages.map((ops, idx) => {
  const inputs = ['-i', bg];
  const imgs = ops.filter((o) => o.t === 'image');
  imgs.forEach((o) => inputs.push('-i', o.path));
  const f = []; let last = '[0:v]';
  imgs.forEach((o, i) => {
    f.push(`[${i + 1}:v]scale=${Math.round(o.w)}:${Math.round(o.h)}[s${i}]`);
    f.push(`${last}[s${i}]overlay=${Math.round(o.x)}:${Math.round(o.y)}[o${i}]`);
    last = `[o${i}]`;
  });
  const chain = [];
  for (const o of ops) {
    if (o.t === 'rect') chain.push(`drawbox=x=${Math.round(o.x)}:y=${Math.round(o.y)}:w=${Math.round(o.w)}:h=${Math.round(o.h)}:color=${o.color}@1:t=${o.fill ? 'fill' : Math.max(1, Math.round(o.h))}`);
    else if (o.t === 'dot') chain.push(`drawbox=x=${Math.round(o.x)}:y=${Math.round(o.y + 11)}:w=7:h=7:color=${C.orange}@1:t=fill`);
    else if (o.t === 'text') {
      const txt = o.text.replace(/\\/g, '\\\\').replace(/'/g, '’').replace(/"/g, '”').replace(/:/g, '：').replace(/,/g, '、').replace(/%/g, '％');
      const hasJp = /[^\x00-\x7F]/.test(o.text);
      const font = o.bold ? FONT_B : (o.mono && !hasJp) ? MONO : FONT_R;
      chain.push(`drawtext=fontfile=${font}:text='${txt}':fontsize=${o.size}:fontcolor=${o.color}:x=${Math.round(o.x)}:y=${Math.round(o.y)}`);
    }
  }
  const filter = `${f.length ? f.join(';') + ';' : ''}${last}${chain.length ? chain.join(',') : 'null'}`;
  const fp = path.join(OUT, `rf${idx}.txt`);
  fs.writeFileSync(fp, filter, 'utf8');
  const out = path.join(OUT, `rp${idx}.png`);
  const r = spawnSync(FFMPEG, ['-hide_banner', '-loglevel', 'error', '-y', ...inputs, '-filter_complex', filter, '-frames:v', '1', out], { stdio: 'inherit' });
  if (r.status !== 0) throw new Error(`page ${idx} failed`);
  console.log(`page ${idx + 1}/${pages.length}`);
  return out;
});

/* ---------- PDF ---------- */
function buildPDF(files, outPath) {
  const pw = 595.28, ph = 841.89;
  const imgs = files.map((p, i) => {
    const raw = path.join(OUT, `rp${i}.rgb`);
    spawnSync(FFMPEG, ['-hide_banner', '-loglevel', 'error', '-y', '-i', p, '-f', 'rawvideo', '-pix_fmt', 'rgb24', raw], { stdio: 'inherit' });
    return zlib.deflateSync(fs.readFileSync(raw), { level: 9 });
  });
  const n = files.length, chunks = [];
  const push = (id, body, raw = null, suffix = null) => chunks.push({ id, body, raw, suffix });
  push(1, '<< /Type /Catalog /Pages 2 0 R >>');
  push(2, `<< /Type /Pages /Count ${n} /Kids [${Array.from({ length: n }, (_, i) => `${3 + i * 3} 0 R`).join(' ')}] >>`);
  for (let i = 0; i < n; i++) {
    const pg = 3 + i * 3, ct = 4 + i * 3, im = 5 + i * 3;
    const s = `q ${pw} 0 0 ${ph} 0 0 cm /Im0 Do Q`;
    push(ct, `<< /Length ${s.length} >>\nstream\n${s}\nendstream`);
    push(pg, `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pw} ${ph}] /Resources << /XObject << /Im0 ${im} 0 R >> >> /Contents ${ct} 0 R >>`);
    push(im, `<< /Type /XObject /Subtype /Image /Width ${PW} /Height ${PH} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length ${imgs[i].length} >>\nstream\n`, imgs[i], '\nendstream');
  }
  const parts = []; const off = []; let pos = 0;
  const w = (x) => { const b = Buffer.isBuffer(x) ? x : Buffer.from(x, 'binary'); parts.push(b); pos += b.length; };
  w('%PDF-1.4\n%\u00E2\u00E3\u00CF\u00D3\n');
  chunks.sort((a, b) => a.id - b.id);
  for (const c of chunks) {
    off[c.id] = pos; w(`${c.id} 0 obj\n`); w(c.body);
    if (c.raw) w(c.raw); if (c.suffix) w(c.suffix);
    w('\nendobj\n');
  }
  const xref = pos, maxId = chunks[chunks.length - 1].id;
  w(`xref\n0 ${maxId + 1}\n0000000000 65535 f \n`);
  for (let i = 1; i <= maxId; i++) w(`${String(off[i] ?? 0).padStart(10, '0')} 00000 n \n`);
  w(`trailer\n<< /Size ${maxId + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
  fs.writeFileSync(outPath, Buffer.concat(parts));
}

const out = path.join(OUT, '報告書2.pdf');
buildPDF(rendered, out);
console.log(`PDF: ${out} (${(fs.statSync(out).size / 1024 / 1024).toFixed(2)} MB, ${pages.length} pages)`);
