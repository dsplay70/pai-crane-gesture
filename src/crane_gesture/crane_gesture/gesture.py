"""CRANE+ V2 のジェスチャ表現と安全バリデータ（ROS 非依存）.

LLM は「度」単位のキーフレーム列を出力する。ここでは
  1. 可動域（URDF の limit より内側に安全マージンを取った範囲）へのクリップ
  2. 関節速度が上限を超えないよう時刻を引き延ばす
  3. キーフレーム数・総時間の上限チェック
を行い、ロボットに送れる形（ラジアン）に変換する。
AI の出力をそのまま実機に流さず、必ずここを通すのが設計方針。
"""

from dataclasses import dataclass, field
import math

# 名前は LLM 向けの意味のある名前、値は ROS の関節名
ARM_JOINTS = {
    'base_yaw': 'crane_plus_joint1',
    'shoulder': 'crane_plus_joint2',
    'elbow': 'crane_plus_joint3',
    'wrist': 'crane_plus_joint4',
}
HAND_JOINT = ('hand', 'crane_plus_joint_hand')

# 安全な可動域 [deg]。URDF の limit より内側に取り、テーブルや自己干渉を避ける
LIMITS_DEG = {
    'base_yaw': (-120.0, 120.0),
    'shoulder': (-80.0, 80.0),
    'elbow': (-110.0, 110.0),
    'wrist': (-100.0, 100.0),
    'hand': (-35.0, 10.0),
}

MAX_VEL_DEG = 90.0   # 関節速度の上限 [deg/s]（URDF は約115deg/s）
MIN_DT = 0.15        # キーフレーム間の最小時間 [s]
MAX_KEYFRAMES = 24
MAX_DURATION = 15.0  # ジェスチャ全体の上限 [s]

# 全関節 0 = 直立。ジェスチャの始まりと終わりはこの姿勢
NEUTRAL = {name: 0.0 for name in LIMITS_DEG}

JOINT_GUIDE = """\
関節（単位は度。全関節0度で真上にまっすぐ立った姿勢）:
- base_yaw: 台座の水平回転。+で(ロボットから見て)左、-で右を向く。範囲 -120〜120
- shoulder: 肩。+で前に倒れる（お辞儀の方向）、-で後ろに反る。範囲 -80〜80
- elbow: 肘。+で後ろに曲がる、-で前に曲がる。範囲 -110〜110
- wrist: 手首（頭部）。+で後ろに反る（上を向く）、-で前に曲がる（うつむく）。範囲 -100〜100
- hand: グリッパ（口のように使える）。-35で大きく開く、0で閉じ気味、10で閉じる
参考姿勢: 休憩姿勢(縮こまる) shoulder=-66, elbow=-115。腕全体を前に倒すときは shoulder を+、
バランスを取るため elbow を-にすると手先が前に出る。
"""


@dataclass
class Keyframe:
    t: float
    joints: dict  # 名前 -> 度


@dataclass
class ValidatedGesture:
    times: list = field(default_factory=list)       # 各キーフレームの到達時刻 [s]
    arm_rad: list = field(default_factory=list)     # [[j1, j2, j3, j4], ...]
    hand_rad: list = field(default_factory=list)    # [hand, ...]
    warnings: list = field(default_factory=list)

    @property
    def duration(self):
        return self.times[-1] if self.times else 0.0


def validate(keyframes, start=None, return_to_neutral=True):
    """LLM のキーフレーム列を検証・補正し、送信可能な軌道を返す.

    keyframes: [{'t': 秒, 'base_yaw': 度, ...}, ...]（欠けた関節は直前の値を保持）
    start: 現在姿勢（度）。None なら直立とみなす
    """
    warnings = []
    if not keyframes:
        raise ValueError('keyframes is empty')
    if len(keyframes) > MAX_KEYFRAMES:
        warnings.append(f'keyframes truncated {len(keyframes)} -> {MAX_KEYFRAMES}')
        keyframes = keyframes[:MAX_KEYFRAMES]

    keyframes = sorted(keyframes, key=lambda k: float(k.get('t', 0.0)))
    prev = dict(start or NEUTRAL)
    prev_t_in = 0.0
    t_out = 0.0
    poses, times = [], []

    for kf in keyframes:
        pose = {}
        for name, (lo, hi) in LIMITS_DEG.items():
            v = kf.get(name)
            v = prev[name] if v is None or not math.isfinite(float(v)) else float(v)
            if v < lo or v > hi:
                warnings.append(f'{name}={v:.1f} clipped to [{lo}, {hi}]')
                v = min(max(v, lo), hi)
            pose[name] = v

        t_in = float(kf.get('t', prev_t_in))
        dt = max(t_in - prev_t_in, MIN_DT)
        # 最も大きく動く関節が速度上限に収まるように時間を延ばす
        max_delta = max(abs(pose[n] - prev[n]) for n in pose)
        dt_needed = max_delta / MAX_VEL_DEG
        if dt_needed > dt:
            warnings.append(f't={t_in:.2f}: stretched {dt:.2f}s -> {dt_needed:.2f}s (velocity limit)')
            dt = dt_needed
        t_out += dt
        poses.append(pose)
        times.append(round(t_out, 3))
        prev, prev_t_in = pose, t_in

    if return_to_neutral and any(abs(prev[n]) > 1e-6 for n in prev):
        max_delta = max(abs(prev[n]) for n in prev)
        t_out += max(max_delta / MAX_VEL_DEG, 1.0)
        poses.append(dict(NEUTRAL))
        times.append(round(t_out, 3))

    if t_out > MAX_DURATION:
        raise ValueError(f'gesture too long: {t_out:.1f}s > {MAX_DURATION}s')

    g = ValidatedGesture(times=times, warnings=warnings)
    for p in poses:
        g.arm_rad.append([math.radians(p[n]) for n in ARM_JOINTS])
        g.hand_rad.append(math.radians(p[HAND_JOINT[0]]))
    return g
