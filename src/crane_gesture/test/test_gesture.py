import math

import pytest

from crane_gesture.gesture import LIMITS_DEG, MAX_VEL_DEG, validate
from crane_gesture.llm import PRESETS


def test_clips_out_of_range():
    g = validate([dict(t=1.0, shoulder=500, elbow=-500)], return_to_neutral=False)
    shoulder, elbow = math.degrees(g.arm_rad[0][1]), math.degrees(g.arm_rad[0][2])
    assert shoulder == pytest.approx(LIMITS_DEG['shoulder'][1])
    assert elbow == pytest.approx(LIMITS_DEG['elbow'][0])
    assert g.warnings


def test_velocity_limit_stretches_time():
    g = validate([dict(t=0.1, base_yaw=90)], return_to_neutral=False)
    assert g.times[0] >= 90 / MAX_VEL_DEG - 1e-6


def test_missing_joints_hold_previous_value():
    g = validate([dict(t=1, wrist=30), dict(t=2, hand=-20)], return_to_neutral=False)
    assert math.degrees(g.arm_rad[1][3]) == pytest.approx(30)


def test_returns_to_neutral_and_times_increase():
    g = validate([dict(t=1, shoulder=30)])
    assert g.arm_rad[-1] == [0.0, 0.0, 0.0, 0.0]
    assert all(b > a for a, b in zip(g.times, g.times[1:]))


def test_rejects_empty_and_nan():
    with pytest.raises(ValueError):
        validate([])
    g = validate([dict(t=1, shoulder=float('nan'))], return_to_neutral=False)
    assert g.arm_rad[0][1] == 0.0


@pytest.mark.parametrize('name', list(PRESETS))
def test_presets_are_valid_without_warnings(name):
    g = validate(PRESETS[name])
    assert not g.warnings
