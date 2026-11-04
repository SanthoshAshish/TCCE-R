"""Wall-clock telemetry must never enter, or influence, the scientific outputs."""
import pandas as pd

from tccer.config import Config, replace
from tccer.sim.engine import simulate

SMALL = replace(Config(), n_nodes=20, init_radius=0.3, radio_range=0.42, epochs=25, rounds_per_epoch=20)


def test_rows_have_no_timing_column():
    rows, _ = simulate(SMALL, 7, "tccer")
    assert not any("_ms" in c or "time" in c.lower() for c in rows[0])


def test_timing_instrumentation_does_not_change_results():
    for policy in ("tccer", "v06_reactive", "v06_random", "static"):
        t = []
        a, ra = simulate(SMALL, 7, policy)
        b, rb = simulate(SMALL, 7, policy, timing=t)
        pd.testing.assert_frame_equal(pd.DataFrame(a), pd.DataFrame(b))
        pd.testing.assert_frame_equal(pd.DataFrame(ra), pd.DataFrame(rb))
        assert len(t) == SMALL.epochs and all(x >= 0 for x in t)
