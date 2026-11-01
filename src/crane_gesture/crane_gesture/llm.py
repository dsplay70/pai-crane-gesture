"""Gemini でユーザの言葉からジェスチャ（キーフレーム列）を生成する（ROS 非依存）.

構造化出力（JSON スキーマ）で形式を縛り、数値の安全性は gesture.validate に任せる。
API キーが無い・通信に失敗した場合は PRESETS から近いものを返す。
"""

import json
import os

from pydantic import BaseModel, Field

from crane_gesture.gesture import JOINT_GUIDE


class KeyframeModel(BaseModel):
    t: float = Field(description='ジェスチャ開始からの秒数')
    base_yaw: float
    shoulder: float
    elbow: float
    wrist: float
    hand: float


class GesturePlan(BaseModel):
    emotion: str = Field(description='相手の発話から読み取った感情（英語1語: joy, sadness, surprise など）')
    intent: str = Field(description='ロボットがこの動きで伝えたいこと（日本語・短く）')
    reply: str = Field(description='ロボットが返す一言（日本語・20文字程度）')
    keyframes: list[KeyframeModel]


SYSTEM_PROMPT = f"""\
あなたは卓上ロボットアーム CRANE+ V2 の「身体表現の振付師」です。
ユーザの言葉から気持ちを読み取り、言葉を使わずに体の動きで共感・応答するジェスチャを作ってください。

{JOINT_GUIDE}
振付のルール:
- 3〜10秒程度、キーフレームは4〜16個。t は単調増加。
- 直立（全関節0）から始まり、最後は直立に戻らなくてよい（システムが戻す）。
- 速すぎる動きはシステムが自動で遅くする。速さで感情を表す場合も1キーフレームあたり0.25秒以上空ける。
- 感情に合った「質感」を出す: 喜び=弾むような繰り返し、悲しみ=ゆっくりうなだれる、
  驚き=素早くのけぞってから戻る、同意=うなずき（wrist の上下）、否定=首振り（base_yaw の左右）など。
- hand は口や手のように使ってよい（パクパク＝おしゃべり・笑い、閉じたまま＝緊張）。
"""

# API が使えないときの手作りジェスチャ（度）。few-shot 的な参考にもなる
PRESETS = {
    'joy': [
        dict(t=0.6, base_yaw=0, shoulder=-15, elbow=20, wrist=30, hand=-30),
        dict(t=1.1, base_yaw=20, shoulder=0, elbow=-10, wrist=0, hand=5),
        dict(t=1.6, base_yaw=-20, shoulder=-15, elbow=20, wrist=30, hand=-30),
        dict(t=2.1, base_yaw=20, shoulder=0, elbow=-10, wrist=0, hand=5),
        dict(t=2.6, base_yaw=0, shoulder=-15, elbow=20, wrist=30, hand=-30),
    ],
    'sadness': [
        dict(t=2.0, base_yaw=0, shoulder=20, elbow=-40, wrist=-60, hand=5),
        dict(t=4.0, base_yaw=-15, shoulder=30, elbow=-50, wrist=-80, hand=5),
        dict(t=5.5, base_yaw=-15, shoulder=30, elbow=-50, wrist=-80, hand=5),
    ],
    'agree': [
        dict(t=0.5, base_yaw=0, shoulder=10, elbow=0, wrist=-35, hand=0),
        dict(t=0.9, base_yaw=0, shoulder=0, elbow=0, wrist=0, hand=0),
        dict(t=1.4, base_yaw=0, shoulder=10, elbow=0, wrist=-35, hand=0),
        dict(t=1.8, base_yaw=0, shoulder=0, elbow=0, wrist=0, hand=0),
    ],
    'bow': [
        dict(t=1.5, base_yaw=0, shoulder=45, elbow=-20, wrist=-30, hand=0),
        dict(t=2.5, base_yaw=0, shoulder=45, elbow=-20, wrist=-30, hand=0),
    ],
}

DEFAULT_MODEL = 'gemini-flash-lite-latest'  # 約2秒で応答（flash 系は 7〜10秒）


def load_dotenv(path):
    """KEY=VALUE 形式の .env を環境変数に読み込む（既に設定済みの値は上書きしない）."""
    if not path or not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                if v.strip():
                    os.environ.setdefault(k.strip(), v.strip())


class GesturePlanner:
    def __init__(self, model=None, api_key=None, thinking=None):
        self.model = model or os.environ.get('GEMINI_MODEL') or DEFAULT_MODEL
        # 推論の深さ（minimal/low/medium/high）。空ならモデルの既定値
        self.thinking = thinking or os.environ.get('GEMINI_THINKING') or 'low'
        api_key = api_key or os.environ.get('GEMINI_API_KEY')
        self.client = None
        if api_key:
            from google import genai
            self.client = genai.Client(api_key=api_key)

    def plan(self, message):
        """発話 -> dict(emotion, intent, reply, keyframes, source)."""
        if self.client is None:
            return self._fallback(message, 'no GEMINI_API_KEY')
        from google.genai import types
        try:
            res = self.client.models.generate_content(
                model=self.model,
                contents=message,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type='application/json',
                    response_schema=GesturePlan,
                    temperature=0.8,
                    thinking_config=types.ThinkingConfig(thinking_level=self.thinking),
                ),
            )
            plan = res.parsed if res.parsed is not None else GesturePlan(**json.loads(res.text))
            out = plan.model_dump()
            out['source'] = self.model
            return out
        except Exception as e:  # noqa: BLE001 通信・形式エラーはすべてフォールバック
            return self._fallback(message, f'{type(e).__name__}: {e}')

    @staticmethod
    def _fallback(message, reason):
        key = 'bow'
        if any(w in message for w in ('嬉', 'うれし', 'やった', '楽し', '最高', '!', '！')):
            key = 'joy'
        elif any(w in message for w in ('悲', 'つら', '辛', '疲', '残念', '落ち込')):
            key = 'sadness'
        elif any(w in message for w in ('ね？', 'よね', 'そう', 'うん')):
            key = 'agree'
        return dict(emotion=key, intent='(preset)', reply='', keyframes=PRESETS[key],
                    source=f'preset ({reason})')
