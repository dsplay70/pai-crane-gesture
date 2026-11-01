"""提出動画を組み立てる（Mac 上で実行）.

  python3 video/make_video.py videos/take3.mp4 [--repo <GitHub URL>]

（動画内にはアカウント名を入れない方針。YouTube のタイトルにだけ付ける）

- record_demo が残したイベント記録（take*.json）から各デモの区間を自動で切り出す
- タイトル・コンセプト・技術・応用・エンドのカードとテロップは PIL で描く（ヒラギノ角ゴシック）
- ffmpeg でつないで videos/final_<日時>.mp4（1920x1080, 30fps, H.264, 無音 AAC）に書き出す
"""

import argparse
import glob
import json
import os
import subprocess
import tempfile
import time
import unicodedata

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

W, H, FPS = 1920, 1080, 30
BG, FG, SUB = (22, 24, 29), (242, 242, 242), (154, 163, 178)
ACCENT, WARN = (94, 194, 160), (224, 184, 79)
CROP = 'crop=1900:1068:10:6,scale=1920:1080'  # RViz 全画面の縁を落とす


def hiragino(weight):
    for f in glob.glob('/System/Library/Fonts/*.ttc'):
        if unicodedata.normalize('NFC', os.path.basename(f)) == f'ヒラギノ角ゴシック W{weight}.ttc':
            return f
    raise FileNotFoundError(f'Hiragino W{weight}')


def font(size, weight=4):
    return ImageFont.truetype(hiragino(weight), size)


MONO = '/System/Library/Fonts/Menlo.ttc'


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def text_center(d, y, s, f, fill=FG):
    w = d.textlength(s, font=f)
    d.text(((W - w) / 2, y), s, font=f, fill=fill)


# ---------- カード ----------

def card_title(bg_frame, path):
    img = Image.open(bg_frame).convert('RGB').resize((W, H))
    img = ImageEnhance.Brightness(img).enhance(0.35)
    d = ImageDraw.Draw(img)
    text_center(d, 380, 'ことばに、うごきで応える。', font(104, 7))
    text_center(d, 540, 'Gemini × ROS 2 × CRANE+ V2', font(48, 4), SUB)
    img.save(path)


def card_concept(path):
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    lines = ['ロボットとの会話は、画面と音声がほとんど。',
             'でも人は、うなずきや身ぶりでも気持ちを伝え合う。',
             'Gemini が言葉から気持ちを読み取り、腕の動きをその場で振り付ける。']
    for i, s in enumerate(lines):
        text_center(d, 150 + i * 80, s, font(48, 6 if i == 2 else 4), FG if i == 2 else SUB)

    boxes = [('あなたの言葉', ['「テストで100点', 'だった！」']),
             ('Gemini', ['気持ちを読み取り', '動きを JSON で振付']),
             ('安全チェック', ['可動域・速度・長さ', 'を検証して補正']),
             ('CRANE+ V2', ['ROS 2 で軌道を送り', 'Gazebo で動く'])]
    bw, bh, gap, y0 = 360, 230, 80, 560
    x0 = (W - (4 * bw + 3 * gap)) / 2
    for i, (name, body) in enumerate(boxes):
        x = x0 + i * (bw + gap)
        hl = i in (1, 2)
        d.rounded_rectangle([x, y0, x + bw, y0 + bh], 18, outline=ACCENT if hl else SUB, width=4 if hl else 2,
                            fill=(30, 48, 44) if hl else BG)
        f1, f2 = font(44, 7), font(32, 4)
        d.text((x + (bw - d.textlength(name, font=f1)) / 2, y0 + 40), name, font=f1, fill=FG)
        for j, s in enumerate(body):
            d.text((x + (bw - d.textlength(s, font=f2)) / 2, y0 + 120 + j * 46), s, font=f2, fill=SUB)
        if i < 3:  # 矢印
            ax, ay = x + bw + 12, y0 + bh / 2
            d.line([ax, ay, ax + gap - 24, ay], fill=SUB, width=4)
            d.polygon([(ax + gap - 24, ay - 12), (ax + gap - 8, ay), (ax + gap - 24, ay + 12)], fill=SUB)
    text_center(d, 860, '発話から動き出すまで約2秒', font(36, 4), WARN)
    img.save(path)


def card_tech(path, events):
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((140, 110), 'AI の出力は、そのままロボットに送らない', font=font(60, 7), fill=FG)
    d.text((140, 210), '可動域を超えた値は切り詰め、速すぎる動きは時間を延ばしてから実行する。',
           font=font(36, 4), fill=SUB)
    # 実際の補正ログ（今回の録画で記録されたもの）
    logs = [(e['text'], v) for e in events for v in e['validator']][:4]
    d.rounded_rectangle([140, 290, W - 140, 300 + 70 + 52 * max(len(logs), 1)], 14, fill=(12, 13, 16))
    d.text((170, 310), '今回の録画で実際に起きた補正', font=font(28, 4), fill=WARN)
    mono = ImageFont.truetype(MONO, 32)
    for i, (_, v) in enumerate(logs):
        d.text((170, 360 + i * 52), f'validator: {v}', font=mono, fill=ACCENT)
    if not logs:
        d.text((170, 360), '（この録画では補正は発生しなかった）', font=font(30, 3), fill=SUB)

    # 応答時間の比較
    y = 680
    lat = [e['latency_s'] for e in events if e.get('latency_s')]
    lite = sum(lat) / len(lat) if lat else 2.0
    d.text((140, y), '応答時間（発話 → 動きの生成）', font=font(36, 6), fill=FG)
    scale, bx = 85, 640  # 1秒あたりの px、0秒の位置（両方の棒をここから描く）
    d.line([bx, y + 64, bx, y + 230], fill=SUB, width=2)
    for sec in range(0, 11, 2):  # 目盛り
        x = bx + sec * scale
        d.line([x, y + 222, x, y + 230], fill=SUB, width=2)
        lbl = f'{sec}秒'
        d.text((x - d.textlength(lbl, font=font(24, 3)) / 2, y + 236), lbl, font=font(24, 3), fill=SUB)
    # (名前, 最短, 最長, 色, ラベル): 0〜最短を濃い棒、最短〜最長のばらつきを薄い延長で表す
    rows = [('gemini-flash-lite（採用）', lite, lite, ACCENT, f'平均 {lite:.1f} 秒'),
            ('gemini-flash（比較）', 7.3, 9.9, SUB, '7.3〜9.9 秒')]
    for i, (name, lo, hi, c, label) in enumerate(rows):
        yy = y + 80 + i * 70
        d.text((140, yy), name, font=font(32, 4), fill=FG)
        d.rectangle([bx, yy + 4, bx + lo * scale, yy + 40], fill=c)
        if hi > lo:
            faint = tuple(int(v * 0.45 + b_ * 0.55) for v, b_ in zip(c, BG))
            d.rectangle([bx + lo * scale, yy + 4, bx + hi * scale, yy + 40], fill=faint)
        d.text((bx + hi * scale + 20, yy + 2), label, font=font(32, 4), fill=c)
    d.text((140, y + 300), '会話のテンポを優先して flash-lite を採用。通信できないときは手作りのジェスチャで動き続ける。',
           font=font(30, 3), fill=SUB)
    img.save(path)


def card_apps(path):
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    text_center(d, 250, 'こんな場面で', font(44, 4), SUB)
    text_center(d, 330, '見守りロボット ・ 介護の現場 ・ 声が届きにくい場所での合図', font(56, 6))
    text_center(d, 560, '次の一歩', font(44, 4), SUB)
    text_center(d, 640, '音声入力 ・ カメラで表情を読む ・ 実機での再現', font(56, 6))
    img.save(path)


def card_end(path, repo):
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    text_center(d, 420, 'ご覧いただきありがとうございました', font(64, 7))
    text_center(d, 560, f'コード: {repo}' if repo else 'コードは GitHub で公開（URL は概要欄）', font(36, 4), SUB)
    img.save(path)


def banner(path, s):
    """デモ映像の上に重ねる帯テロップ（透過 PNG）."""
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font(48, 7)
    w = d.textlength(s, font=f)
    d.rounded_rectangle([60, 50, 60 + w + 64, 50 + 96], 16, fill=(22, 24, 29, 220))
    d.rectangle([60, 50, 70, 146], fill=ACCENT + (255,))
    d.text((60 + 36, 70), s, font=f, fill=FG)
    img.save(path)


# ---------- 区間の書き出し ----------

ENC = ['-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', str(FPS), '-an']


def seg_image(png, dur, out, black_tail=0.15):
    # フェードは区間の終わりより black_tail 秒早く黒に落としきる（最後のコマにテロップが薄く残らないように）
    fade_end = dur - black_tail
    run(['ffmpeg', '-y', '-loop', '1', '-t', str(dur), '-i', png,
         '-vf', f'fade=in:st=0:d=0.4,fade=out:st={fade_end - 0.45:.3f}:d=0.45', *ENC, out])


def seg_clip(raw, a, b, out, overlay=None, overlay_until=None):
    if overlay:
        run(['ffmpeg', '-y', '-ss', f'{a:.2f}', '-to', f'{b:.2f}', '-i', raw, '-i', overlay,
             '-filter_complex', f"[0:v]{CROP}[v];[v][1:v]overlay=0:0:enable='lt(t,{overlay_until})'",
             *ENC, out])
    else:
        run(['ffmpeg', '-y', '-ss', f'{a:.2f}', '-to', f'{b:.2f}', '-i', raw, '-vf', CROP, *ENC, out])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('raw')
    ap.add_argument('--repo', default='')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    raw = args.raw
    meta = json.load(open(os.path.splitext(raw)[0] + '.json'))
    events = [e for e in meta['events'] if e['ok']]
    # 毎回別名で書き出す（プレーヤーで開いたままのファイルを上書きすると、古い表示のまま黒画面になるため）
    out = args.out or os.path.join(os.path.dirname(raw), time.strftime('final_%m%d_%H%M%S.mp4'))
    tmp = tempfile.mkdtemp(prefix='pai_video_')
    p = lambda name: os.path.join(tmp, name)  # noqa: E731

    run(['ffmpeg', '-y', '-ss', '1.5', '-i', raw, '-frames:v', '1', '-vf', CROP, p('bg.png')])
    card_title(p('bg.png'), p('title.png'))
    card_concept(p('concept.png'))
    card_tech(p('tech.png'), events)
    card_apps(p('apps.png'))
    card_end(p('end.png'), args.repo)
    banner(p('b_try.png'), '話しかけてみる')
    banner(p('b_yabai.png'), '同じ「やばい」でも、文脈で気持ちは逆になる')

    segs = []
    seg_image(p('title.png'), 5, p('s00.mp4'))
    seg_image(p('concept.png'), 13, p('s01.mp4'))
    segs += [p('s00.mp4'), p('s01.mp4')]
    for i, e in enumerate(events):
        a, b = e['send'] - 0.6, e['done'] + 1.2
        o = p(f'd{i}.mp4')
        if i == 0:
            seg_clip(raw, a, b, o, p('b_try.png'), 3.0)
        elif 'やばい' in e['text']:
            seg_clip(raw, a, b, o, p('b_yabai.png'), b - a)
        else:
            seg_clip(raw, a, b, o)
        segs.append(o)
    seg_image(p('tech.png'), 15, p('s10.mp4'))
    seg_image(p('apps.png'), 8, p('s11.mp4'))
    seg_image(p('end.png'), 6, p('s12.mp4'), black_tail=1.0)  # 最後は1秒黒で終える
    segs += [p('s10.mp4'), p('s11.mp4'), p('s12.mp4')]

    with open(p('list.txt'), 'w') as f:
        f.writelines(f"file '{s}'\n" for s in segs)
    run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', p('list.txt'),
         '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-shortest',
         '-c:v', 'copy', '-c:a', 'aac', '-b:a', '64k', '-movflags', '+faststart', out])
    dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                         '-of', 'csv=p=0', out]).decode())
    print(f'{out}  {dur:.1f}s  ({len(events)} demos)  work: {tmp}')


if __name__ == '__main__':
    main()
