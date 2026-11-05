import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hemaviz.kinematics import (FOREARM, UPPER_ARM, LONGSWORD, P, seg_seg,  # noqa: E402
                                skeleton)
from hemaviz.sim import simulate  # noqa: E402
from hemaviz.techniques import SCENARIOS, TECHNIQUES, VOM_TAG  # noqa: E402
from hemaviz.timings import (default_store, durations, effective_ms,  # noqa: E402
                             frames_to_ms)

DUR = durations(default_store())


def run(key, **kw):
    s = next(x for x in SCENARIOS if x.key == key)
    args = dict(cue_phase=s.cue_phase, reaction_ms=s.reaction_ms,
                distance=s.distance)
    args.update(kw)
    return simulate(s.a, s.b, DUR, **args)


def test_seg_seg_crossing_and_parallel():
    d, s, t = seg_seg(np.array([0., 0, 0]), np.array([2., 0, 0]),
                      np.array([1., -1, 0.5]), np.array([1., 1, 0.5]))
    assert d == pytest.approx(0.5)
    assert s == pytest.approx(0.5) and t == pytest.approx(0.5)
    d, *_ = seg_seg(np.array([0., 0, 0]), np.array([1., 0, 0]),
                    np.array([0., 1, 0]), np.array([1., 1, 0]))
    assert d == pytest.approx(1.0)


def test_ik_keeps_bone_lengths():
    for pose in (VOM_TAG, P((0.9, 1.4, 0.0), 5, 0, yaw=20, lean=10)):
        sk = skeleton(pose, LONGSWORD)
        assert np.linalg.norm(sk["el_r"] - sk["sh_r"]) == pytest.approx(UPPER_ARM, abs=1e-6)
        assert np.linalg.norm(sk["hand_r"] - sk["el_r"]) == pytest.approx(FOREARM, abs=2e-3)
        blade = np.linalg.norm(sk["tip"] - sk["guard"])
        assert blade == pytest.approx(LONGSWORD.blade)


def test_timing_store_uses_median_of_trials():
    st = default_store()
    assert effective_ms(st, "messer.zwerch") == st["actions"]["messer.zwerch"]["default_ms"]
    st["actions"]["messer.zwerch"]["trials_ms"] = [300, 500, 310]
    assert effective_ms(st, "messer.zwerch") == 310
    assert frames_to_ms(10, 52, 120) == pytest.approx(350)


def test_every_technique_runs_against_a_dummy():
    for key, t in TECHNIQUES.items():
        if not t.phases:
            continue
        dummy = "dummy_ls" if t.weapon == "messer" else "dummy_m"
        r = simulate(key, dummy, DUR, distance=2.4)
        assert r.frames and r.duration < 4.0


def test_mutual_zornhau_reach_wins():
    r = run("mutual")
    a, b = r.first_hit
    assert a is not None and a.part == "head"
    assert b is None or b.t > a.t


def test_zwerch_covers_on_the_cross_and_hits():
    r = run("zwerch")
    kinds = [(e.kind, e.by) for e in r.events]
    assert ("displace", 1) in kinds
    assert r.first_hit[1] is not None and r.first_hit[1].part == "head"
    assert r.first_hit[0] is None
    assert r.verdict == "B wins clean"


def test_zwerch_fails_when_late_or_slow():
    assert run("zwerch", reaction_ms=120).verdict != "B wins clean"
    assert run("zwerch", speed_b=1.4).verdict != "B wins clean"


def test_nachreisen_beats_the_wind_up():
    r = run("nachreisen")
    b = r.first_hit[1]
    assert b is not None and ("forearm" in b.part or "hand" in b.part)
    assert r.first_hit[0] is None or r.first_hit[0].t > b.t


def test_hanging_cover_then_einlaufen():
    r = run("einlauf")
    assert any(e.kind == "displace" and e.by == 1 for e in r.events)
    assert r.verdict == "B wins clean"


def test_displaced_action_cannot_score():
    r = run("zwerch")
    disp = next(e for e in r.events if e.kind == "displace")
    assert not any(e.kind == "hit" and e.by == 0 and e.t > disp.t
                   for e in r.events)
