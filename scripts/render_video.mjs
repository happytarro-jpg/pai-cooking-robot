/** 録画から課題動画を作る（字幕つき） */
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const DIR = path.join(ROOT, 'cooking_demo');
const FF = 'C:\\Users\\SUN HANYU\\AppData\\Roaming\\kingsoft\\wps\\addons\\pool\\win-i386\\aivideo_3.1.0.33\\aivideo\\ffmpeg.exe';
const src = path.join(DIR, 'raw_demo.mp4');

const d = spawnSync(FF, ['-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', src], { encoding: 'utf8' });
const D = Math.floor(Number(d.stdout.trim()) || 80);
const t = (f) => (D * f).toFixed(2);
const T = { a: t(0.13), b: t(0.44), c: t(0.66), e: t(0.80), g: t(0.95) };
const END = (D + 3).toFixed(2);

const F_R = 'C\\\\:/Windows/Fonts/YuGothM.ttc';
const F_B = 'C\\\\:/Windows/Fonts/YuGothB.ttc';
const chain = [];
let lab = '[v0]';

function step(expr, isLast = false) {
  const out = isLast ? '[out]' : `[v${chain.length + 1}]`;
  chain.push(`${lab}${expr}${out}`);
  lab = out;
}
const box = (text, size, color, x, y, t0, t1, bold = false, bg = false) => {
  const txt = text.replace(/\\/g, '\\\\').replace(/'/g, '’').replace(/:/g, '：').replace(/,/g, '、').replace(/%/g, '％');
  return `drawtext=fontfile=${bold ? F_B : F_R}:text='${txt}':fontsize=${size}:fontcolor=${color}`
    + (bg ? ':box=1:boxcolor=0x0d1117@0.72:boxborderw=14' : '')
    + `:x=${x}:y=${y}:enable='between(t,${t0},${t1})'`;
};

chain.push(`[0:v]crop=608:470:2:290,scale=720:556:flags=lanczos,pad=1280:720:280:100:color=0x0d1117,setsar=1[v0]`);
step(`drawbox=x=0:y=0:w=1280:h=64:color=0x0d1117@0.85:t=fill`);
step(`drawbox=x=0:y=650:w=1280:h=70:color=0x0d1117@0.85:t=fill`);
step(`drawbox=x=0:y=0:w=1280:h=4:color=0xE07A2B@1:t=fill`);
step(`drawbox=x=0:y=0:w=1280:h=720:color=0x0d1117@1:t=fill:enable='between(t,0,6)'`);
step(`drawbox=x=0:y=0:w=1280:h=720:color=0x0d1117@0.94:t=fill:enable='between(t,${D},${END})'`);

const items = [
  box('お料理ロボット', 58, '0xF2F6FB', '(w-tw)/2', 250, 0, 6, true),
  box('ROS 2 + Gazebo + MoveIt で材料を炒める', 26, '0xE07A2B', '(w-tw)/2', 330, 0, 6),
  box('crane_plus 4 自由度アーム / Ignition Gazebo', 20, '0x9FB0C0', '(w-tw)/2', 380, 1, 6),
  box('お料理ロボット', 27, '0xF2F6FB', 28, 18, 6, END, true),
  box('材料を取る → フライパンへ → 混ぜる', 20, '0x9FB0C0', 28, 50, 6, END),
  box('材料を 3 つ用意（にんじん・トマト・ブロッコリー）', 30, '0xF2F6FB', 60, 668, 6, T.a, false, true),
  box('MoveIt の逆運動学で把持位置を計算して降りる', 30, '0xF2F6FB', 60, 668, T.a, T.b, false, true),
  box('グリッパで挟んで持ち上げ、フライパンへ運ぶ', 30, '0xF2F6FB', 60, 668, T.b, T.c, false, true),
  box('フライパンの上で離す → 落ちて中に入る', 30, '0xF2F6FB', 60, 668, T.c, T.e, false, true),
  box('フライパンの上で円を描いて混ぜる', 30, '0xF2F6FB', 60, 668, T.e, T.g, false, true),
  box('完成', 46, '0xE07A2B', '(w-tw)/2', 250, D, END, true),
  box('材料 3 つをフライパンへ（30 動作 / 約 80 秒）', 24, '0xF2F6FB', '(w-tw)/2', 330, D, END),
  box('ROS 2 Humble + Ignition Gazebo 11 + MoveIt 2 / crane_plus', 20, '0x9FB0C0', '(w-tw)/2', 380, D, END),
];
items.forEach((it, i) => step(it, i === items.length - 1));

const filterPath = path.join(DIR, 'vf.txt');
fs.writeFileSync(filterPath, chain.join(';\n'), 'utf8');
const out = path.join(DIR, 'PAI最終課題_お料理ロボット.mp4');
const r = spawnSync(FF, ['-hide_banner', '-loglevel', 'error', '-y', '-i', src, '-filter_script:v', filterPath,
  '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-an', out], { stdio: 'inherit' });
if (r.status !== 0) throw new Error('ffmpeg failed');
console.log(`done: ${out} ${(fs.statSync(out).size / 1024 / 1024).toFixed(2)} MB / ${D}s`);
