"""End-to-end: determinism and common random numbers across policies."""
import pandas as pd

from tccer.config import Config, replace
from tccer.policies import POLICIES
from tccer.sim.engine import simulate

SMALL = replace(Config(), n_nodes=20, init_radius=0.3, radio_range=0.42, epochs=25, rounds_per_epoch=20)


def test_same_seed_same_result():
    a, ra = simulate(SMALL, 7, "tccer")
    b, rb = simulate(SMALL, 7, "tccer")
    pd.testing.assert_frame_equal(pd.DataFrame(a), pd.DataFrame(b))
    pd.testing.assert_frame_equal(pd.DataFrame(ra), pd.DataFrame(rb))


def test_failure_trace_is_policy_independent():
    traces = [pd.DataFrame(simulate(SMALL, 3, p, log_rounds=False)[0]).n_down_potential.tolist()
              for p in POLICIES]
    assert all(t == traces[0] for t in traces)


def test_all_policies_run_and_respect_cap():
    for p in POLICIES:
        rows, _ = simulate(replace(SMALL, mutation_cap=2, period=3), 1, p, log_rounds=False)
        assert len(rows) == SMALL.epochs
        if p not in ("tccer", "tccer_fixed"):
            assert rows[-1]["n_mutations"] <= 2
