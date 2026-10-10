"""Protocol rev. 4 (section 2.3a): per-seed intended counts for A6/A7 drawn from the frozen tuning-seed distribution."""
import sys

import numpy as np
import pandas as pd
import pytest

import experiments.run_v06 as run
from experiments.amend_v06_rev4 import empirical_pmf, pmf_string
from experiments.v06_common import base_config
from tccer.config import Config, replace
from tccer.policies.v06 import FrontLoadedArm, RandomTimingArm, draw_intended_count, parse_pmf
from tccer.sim.engine import simulate

PMF3 = [0.05, 0.16, 0.24, 0.55]          # d2_M3 shape from the tuning dry run
CFG = replace(Config(), epochs=80, mutation_cap=3, v06_count_pmf=pmf_string(PMF3))


class Stub:
    def __init__(self, fail_at=()):
        self.fail_at, self.calls, self.last = set(fail_at), [], {}

    def select(self, state, k, mode="lexicographic", rng=None):
        self.calls.append(k)
        return None if k in self.fail_at else ("mut", k)


def run_arm(cls, cfg, seed, fail_at=()):
    pipe = Stub(fail_at)
    pol = cls(cfg, pipe, np.random.default_rng([seed, 3]))
    ok = [pol.decide(k, {"E_hat": 0.5, "C": 0.0, "V": 0.0}, None) is not None for k in range(cfg.epochs)]
    return pol, pipe, ok


def test_parse_pmf_validation():
    assert list(parse_pmf("0.25,0.75", 1)) == [0.25, 0.75]
    for bad in ("0.5,0.5", "0.2,0.2,0.2,0.2", "-0.1,0.6,0.3,0.2", "0.1,0.1,0.1,0.1"):
        with pytest.raises(ValueError):
            parse_pmf(bad, 3)


def test_inverse_cdf_boundaries_and_zero_probability():
    p = np.array([0.05, 0.16, 0.24, 0.55])
    assert draw_intended_count(p, 0.0) == 0 and draw_intended_count(p, 0.0499) == 0
    assert draw_intended_count(p, 0.05) == 1 and draw_intended_count(p, 0.2099) == 1
    assert draw_intended_count(p, 0.21) == 2 and draw_intended_count(p, 0.4499) == 2
    assert draw_intended_count(p, 0.45) == 3 and draw_intended_count(p, 0.999999) == 3
    z = np.array([0.0, 0.5, 0.0, 0.5])
    assert {draw_intended_count(z, u) for u in np.linspace(0, 0.999, 500)} == {1, 3}


def test_intended_counts_follow_the_frozen_distribution():
    counts = np.array([RandomTimingArm(CFG, Stub(), np.random.default_rng([s, 3])).intended for s in range(20000)])
    freq = np.bincount(counts, minlength=4) / len(counts)
    assert np.all(np.abs(freq - np.array(PMF3)) < 0.015), freq


def test_a6_and_a7_share_the_intended_count_per_seed():
    for s in range(200):
        a6 = RandomTimingArm(CFG, Stub(), np.random.default_rng([s, 3])).intended
        a7 = FrontLoadedArm(CFG, Stub(), np.random.default_rng([s, 3])).intended
        assert a6 == a7


def test_timing_semantics_preserved():
    for s in range(300):
        a6 = RandomTimingArm(CFG, Stub(), np.random.default_rng([s, 3]))
        a7 = FrontLoadedArm(CFG, Stub(), np.random.default_rng([s, 3]))
        assert len(a6.schedule) == a6.intended and all(b - a >= 2 for a, b in zip(a6.schedule, a6.schedule[1:]))
        assert a7.schedule == [2 * j for j in range(a7.intended)]


def test_no_extra_mutations_through_retries_or_backlog():
    rng = np.random.default_rng(1)
    for s in range(300):
        fail = set(rng.choice(80, size=int(rng.integers(0, 60)), replace=False).tolist())
        for cls in (RandomTimingArm, FrontLoadedArm):
            pol, pipe, ok = run_arm(cls, CFG, s, fail)
            done = [k for k, x in enumerate(ok) if x]
            assert len(done) <= pol.intended <= 3
            assert len(pipe.calls) == len(set(pipe.calls))                       # one attempt per epoch
            assert all(b - a >= 2 for a, b in zip(done, done[1:]))               # cooldown
            if done:                                                              # no attempts after the count is met
                assert not (len(done) == pol.intended and any(c > done[-1] for c in pipe.calls))
            assert all(r >= sch for r, sch in zip(done, pol.schedule))           # never earlier than scheduled
        pol, _, ok = run_arm(FrontLoadedArm, CFG, s)                              # no failures -> exactly intended
        assert sum(ok) == pol.intended


def test_without_pmf_rev3_behaviour_is_unchanged():
    cfg3 = replace(CFG, v06_count_pmf=None)
    for s in range(50):
        a = RandomTimingArm(cfg3, Stub(), np.random.default_rng([s, 3]))
        rng = np.random.default_rng([s, 3])
        while True:                                                          # rev. 3 algorithm, reproduced
            ref = sorted(int(x) for x in rng.choice(80, size=3, replace=False))
            if all(b - a_ >= 2 for a_, b in zip(ref, ref[1:])):
                break
        assert a.intended == 3 and a.schedule == ref


def test_empirical_pmf():
    p, tally = empirical_pmf(np.array([0, 3, 3, 1, 2, 3, 2, 3]), 3)
    assert tally == [1, 1, 2, 4] and p == [0.125, 0.125, 0.25, 0.5]
    with pytest.raises(ValueError):
        empirical_pmf(np.array([0, 4]), 3)


def test_controls_in_simulator_respect_intended_and_cap():
    cfg = replace(base_config(8), epochs=40, mutation_cap=6, v06_count_pmf=pmf_string([0, 0.1, 0.1, 0.2, 0.2, 0.1, 0.3]))
    for arm in ("v06_random", "v06_front"):
        for s in (100, 101, 102):
            df = pd.DataFrame(simulate(cfg, s, arm, log_rounds=False)[0])
            intended = int(df.v06_intended.iloc[-1])
            assert df.n_mutations.iloc[-1] <= intended <= 6
            assert (df.select_outcome == "mutated").sum() == df.n_mutations.iloc[-1]


def test_run_guards_for_outputs(tmp_path, monkeypatch):
    done = tmp_path / "dry"
    done.mkdir()
    (done / "COMPLETE").write_text("x")
    monkeypatch.setattr(sys, "argv", ["run", "--mode", "dry", "--out", str(done)])
    with pytest.raises(SystemExit, match="never overwritten"):
        run.main()
    monkeypatch.setattr(sys, "argv", ["run", "--mode", "eval", "--out", str(tmp_path / "x")])
    with pytest.raises(SystemExit, match="not allowed in eval"):
        run.main()
