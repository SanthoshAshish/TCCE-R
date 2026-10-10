"""v0.7 runner/analysis helpers: feedback-quality parsing, family exclusions, seed guards, scenario configs."""
import os

import numpy as np
import pandas as pd
import pytest

import experiments.analyze_v07 as a7
from experiments.v07_common import (CELLS, EVAL_SEEDS, IsolationError, SCENARIOS, TUNING_SEEDS, DEV_SEEDS, assert_seeds,
                                    grid, scenario_config)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_seed_ranges_are_disjoint_and_guarded():
    assert not (set(TUNING_SEEDS) & set(EVAL_SEEDS)) and not (set(DEV_SEEDS) & set(EVAL_SEEDS))
    assert min(EVAL_SEEDS) >= 7000 and len(EVAL_SEEDS) == 60
    with pytest.raises(IsolationError):
        assert_seeds([200, 7000], range(200, 220), "calibration")
    with pytest.raises(IsolationError):
        assert_seeds([300], range(7000, 7060), "eval")


def test_scenarios_load_valid_and_as_specified():
    s1, s2, s3 = (scenario_config(s) for s in SCENARIOS)
    for c in (s1, s2, s3):
        assert c.feedback_rule == "counterfactual" and c.link_setup_epochs == 2 and c.budget_on == "configured"
        assert c.edge_budget_frac == 1.0 and c.epochs == 80
    assert s1.burst_rate == 0.1 and s2.burst_rate == 0.0 and s2.p_fail == 0.01
    assert s3.n_nodes == 80 and s3.init_radius == pytest.approx(0.22 * np.sqrt(0.5), abs=1e-4)
    assert len(CELLS) == 6


def test_smoke_grid_subsamples_full_grid():
    g = grid("A1", smoke=True)
    assert len(g) == 6 and set(g) <= set(grid("A1", smoke=False))


def test_feedback_quality_parsing():
    g = pd.DataFrame({"theta_update": [np.nan, "4:S(-0.02);", "", "9:F(0.01);11:N(0);"]})
    m = a7.feedback_metrics(g)
    assert m["fb_updates"] == 3 and m["fb_success"] == pytest.approx(1 / 3)
    assert m["fb_failure"] == pytest.approx(1 / 3) and m["fb_neutral"] == pytest.approx(1 / 3)
    assert m["fb_mean_delta"] == pytest.approx((-0.02 + 0.01 + 0.0) / 3)
    assert a7.feedback_metrics(pd.DataFrame({"x": [1]})) == {"fb_updates": 0}


def test_family_marks_missing_arms_excluded():
    rows = [{"group": "S1_rgg40_bursty_M3", "arm": "A1", "seed": s, "E": 0.4} for s in range(6)]
    fam = a7.family(pd.DataFrame(rows), [("A5", "A1")], [("S1_rgg40_bursty", 3)], "primary")
    assert (fam.status == "excluded (not calibratable)").all() and fam.holm_p.isna().all()
