import itertools

import pytest

from gopalan_ml.bcs import Anchor, estimate_bcs, label_for, round_to_step
from gopalan_ml.measure import Measurements


def meas(depth=None, rib=None, rump=None, hip=None):
    m = Measurements(rib_visibility=rib, rump_width_cm=rump, hip_width_cm=hip)
    if depth is not None:
        m.body_length_cm, m.body_depth_cm = 100.0, depth * 100.0
    return m


def test_typical_animal_is_ideal():
    r = estimate_bcs(meas(depth=0.38, rib=0.07, rump=50, hip=52.6))
    assert r.score == 3.0
    assert r.label == "Ideal"
    assert r.beta is True


def test_thin_and_fat_extremes():
    assert estimate_bcs(meas(depth=0.20, rib=0.20, rump=40, hip=50)).score == 1.0
    assert estimate_bcs(meas(depth=0.60, rib=0.00, rump=60, hip=50)).score == 5.0


def test_old_bug_3_scores_use_quarter_steps_including_3():
    scores = set()
    for d, rib in itertools.product([0.26 + 0.01 * i for i in range(25)], [0.0, 0.04, 0.08, 0.12]):
        s = estimate_bcs(meas(depth=d, rib=rib)).score
        assert 1.0 <= s <= 5.0
        assert (s * 4) == int(s * 4)
        scores.add(s)
    assert 3.0 in scores
    assert {2.25, 2.75, 3.25, 3.75} <= scores  # values the old formula could never produce


def test_old_bug_2_anchors_are_configurable():
    custom = {"depth_ratio": Anchor(thin=0.10, fat=0.20, weight=1.0)}
    assert estimate_bcs(meas(depth=0.38), anchors=custom).score == 5.0


def test_deterministic():
    m = meas(depth=0.41, rib=0.05, rump=48, hip=50)
    assert estimate_bcs(m).to_dict() == estimate_bcs(m).to_dict()


def test_needs_at_least_one_signal():
    with pytest.raises(ValueError, match="side-view"):
        estimate_bcs(Measurements())


def test_confidence_grows_with_more_agreeing_signals():
    one = estimate_bcs(meas(depth=0.38))
    three = estimate_bcs(meas(depth=0.38, rib=0.07, rump=50, hip=52.6))
    disagree = estimate_bcs(meas(depth=0.48, rib=0.12, rump=42, hip=50))
    assert three.confidence > one.confidence
    assert three.confidence > disagree.confidence
    assert all(0 < r.confidence <= 0.9 for r in (one, three, disagree))
    assert any("single measurement" in w for w in one.warnings)


def test_explanation_lists_signal_effects():
    r = estimate_bcs(meas(depth=0.46, rib=0.11))
    effects = {s.name: s.effect for s in r.signals}
    assert effects == {"depth_ratio": "fatter", "rib_visibility": "thinner"}
    d = r.to_dict()
    assert d["scale"].startswith("1-5") and "calibrated" in d["note"]


def test_out_of_range_warning():
    assert any("outside the usual range" in w for w in estimate_bcs(meas(depth=0.9)).warnings)


@pytest.mark.parametrize("x,expected", [(2.874, 2.75), (2.875, 3.0), (3.125, 3.25), (1.0, 1.0)])
def test_round_to_step_half_up(x, expected):
    assert round_to_step(x) == expected


def test_farmer_score_and_labels():
    r = estimate_bcs(meas(depth=0.40, rib=0.07))
    assert r.farmer_score * 2 == int(r.farmer_score * 2)
    # depth 0.37 -> position 0.45 -> raw 2.8 -> 2.75, shown to farmers as 3.0
    r275 = estimate_bcs(meas(depth=0.37))
    assert (r275.score, r275.farmer_score, r275.label) == (2.75, 3.0, "Ideal")
    assert [label_for(s) for s in (1.5, 2.5, 3.5, 4.5, 5.0)] == ["Very thin", "Thin", "Ideal", "Fat", "Obese"]
