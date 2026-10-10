"""v0.6: arm mechanics (protocol 2), backlog semantics, Static invariance, common traces, isolation, checksums,
and analysis functions (protocol 4-6)."""
import os

import numpy as np
import pandas as pd
import pytest

import experiments.analyze_v06 as an
from experiments.calibrate_v06 import choose, static_constants
from experiments.run_v06 import check_eval_allowed
from experiments.v06_common import (ARM_POLICY, IsolationError, assert_seeds, base_config, verify_manifest,
                                    write_manifest)
from tccer.config import Config, replace
from tccer.policies.v06 import (FrontLoadedArm, MovingAverageArm, MovingAverageResetArm, RandomTimingArm,
                                ReactiveArm, CusumEArm, CusumECVArm, TCCERArm)
from tccer.sim.engine import simulate


class StubPipeline:
    """select() fails at epochs in `fail_at`, else returns a token. Records attempt epochs."""

    def __init__(self, fail_at=()):
        self.fail_at, self.calls, self.last = set(fail_at), [], {}

    def select(self, state, k, mode="lexicographic", rng=None):
        self.calls.append(k)
        return None if k in self.fail_at else ("mut", k)


def drive(arm_cls, E, cfg, fail_at=(), C=None, V=None, rng=None):
    pipe = StubPipeline(fail_at)
    pol = arm_cls(cfg, pipe, rng if rng is not None else np.random.default_rng([0, 3]))
    out = []
    for k, e in enumerate(E):
        obs = {"E_hat": e, "C": 0.0 if C is None else C[k], "V": 0.0 if V is None else V[k]}
        m = pol.decide(k, obs, None)
        out.append(m is not None)
    return pol, pipe, out


CFG = replace(Config(), epochs=20, mutation_cap=3, v06_threshold=0.5)


# ------------------------------------------------------------------ shared rules (protocol 2.1)
def test_reactive_threshold_cooldown_and_cap():
    pol, pipe, ok = drive(ReactiveArm, [0.9] * 20, CFG)
    assert [k for k, x in enumerate(ok) if x] == [0, 2, 4]          # cooldown 2, cap 3
    assert pipe.calls == [0, 2, 4]                                   # no attempts after the cap


def test_failed_attempt_changes_nothing_and_retries_next_epoch():
    pol, pipe, ok = drive(ReactiveArm, [0.9] * 20, CFG, fail_at={0, 1})
    assert pipe.calls[:3] == [0, 1, 2] and [k for k, x in enumerate(ok) if x] == [2, 4, 6]
    assert pol.failed_attempts == 2 and pol.attempts == 5


def test_at_most_one_attempt_per_epoch_all_arms():
    for cls in (ReactiveArm, MovingAverageArm, CusumEArm, CusumECVArm, FrontLoadedArm, RandomTimingArm):
        cfg = replace(CFG, v06_kappa=0.1, mutation_cap=5)
        pol, pipe, _ = drive(cls, [0.95] * 20, cfg, fail_at=set(range(0, 20, 3)))
        assert len(pipe.calls) == len(set(pipe.calls)), cls


def test_uncapped_calibration_mode():
    pol, pipe, ok = drive(ReactiveArm, [0.9] * 20, replace(CFG, mutation_cap=None))
    assert sum(ok) == 10                                             # every 2nd epoch, no cap


def test_moving_average_window_partial_start_and_no_reset():
    pol, _, _ = drive(MovingAverageArm, [0.0, 1.0, 1.0], replace(CFG, v06_threshold=0.9))
    assert pol.stat == pytest.approx(2 / 3)
    pol, _, ok = drive(MovingAverageArm, [1.0] * 6, replace(CFG, v06_threshold=0.5))
    assert pol.hist == [1.0] * 6                                     # never reset
    pol_r, _, _ = drive(MovingAverageResetArm, [1.0] * 6, replace(CFG, v06_threshold=0.5))
    assert len(pol_r.hist) < 6                                       # A2-reset clears after a success


def test_cusum_recursion_reset_on_success_only():
    cfg = replace(CFG, v06_threshold=1.0, v06_kappa=0.3, mutation_cap=5)
    pol, pipe, ok = drive(CusumEArm, [0.8, 0.8, 0.8, 0.0], cfg)
    # D: 0.5, 1.0 (not > 1.0), 1.5 -> success at k=2 -> reset to 0; then max(0, 0 + 0 - 0.3) = 0
    assert [k for k, x in enumerate(ok) if x] == [2] and pol.stat == 0.0
    pol, pipe, ok = drive(CusumEArm, [0.8] * 4, cfg, fail_at={2})
    assert pipe.calls == [2, 3] and ok[3] and pol.stat == 0.0        # failed attempt kept D, retried


def test_cusum_ecv_stress_weights():
    cfg = replace(CFG, v06_threshold=100.0, v06_kappa=0.0)
    pol, _, _ = drive(CusumECVArm, [0.2], cfg, C=[1.0], V=[0.5])
    assert pol.stat == pytest.approx(0.5 * 0.2 + 0.3 * 1.0 + 0.2 * 0.5)


def test_tccer_theta_bounds_and_feedback_timing():
    d = 2
    cfg = replace(CFG, v06_threshold=1.0, v06_kappa=0.0, mutation_cap=1, link_setup_epochs=d,
                  feedback_after_setup=False, feedback_horizon=5)       # base-config values must be ignored
    E = [0.6, 0.6, 0.6] + [0.1] * 17
    C = [1.0, 1.0, 1.0] + [0.0] * 17          # s = 0.5*0.6 + 0.3*1 = 0.6 -> D: 0.6, 1.2 (> 1) -> mutation at k=1
    pol, _, ok = drive(TCCERArm, E, cfg, C=C)
    assert ok[1] and sum(ok) == 1
    # after-window = m+1+d .. m+d+3 = 4..6, evaluated at k=6 -> success -> theta = 0.9
    assert pol.n_updates == 1 and pol.n_success == 1 and pol.theta == pytest.approx(0.9)
    pol.theta = 0.26
    for _ in range(3):
        pol.theta = max(0.25 * pol.theta0, pol.theta * 0.9)
    assert pol.theta == pytest.approx(0.25)


def test_tccer_theta_upper_bound_on_failures():
    cfg = replace(CFG, v06_threshold=0.1, v06_kappa=0.0, mutation_cap=10, link_setup_epochs=0, epochs=60)
    E = [0.2] * 60                                                    # after-window never lower -> failures
    pol, _, _ = drive(TCCERArm, E, cfg)
    assert pol.n_failure > 0 and pol.theta <= 4 * 0.1 + 1e-12


# ------------------------------------------------------------------ schedules and backlog (protocol 2.3)
def test_random_schedule_gaps_reproducible_and_from_policy_stream():
    cfg = replace(Config(), epochs=80, mutation_cap=6)
    s1 = RandomTimingArm(cfg, StubPipeline(), np.random.default_rng([6001, 3])).schedule
    s2 = RandomTimingArm(cfg, StubPipeline(), np.random.default_rng([6001, 3])).schedule
    assert s1 == s2 and len(set(s1)) == 6 and all(b - a >= 2 for a, b in zip(s1, s1[1:]))
    assert all(0 <= x < 80 for x in s1)


def test_front_loaded_schedule():
    assert FrontLoadedArm(replace(Config(), mutation_cap=3), StubPipeline(), None).schedule == [0, 2, 4]


def test_backlog_delays_later_mutations_never_earlier():
    cfg = replace(CFG, mutation_cap=3)
    pol, pipe, ok = drive(FrontLoadedArm, [0.0] * 20, cfg, fail_at={0, 1, 2})
    done = [k for k, x in enumerate(ok) if x]
    assert done == [3, 5, 7]                         # schedule 0,2,4: backlog 2 at k=2, then cooldown spacing
    assert pol.lags() == [3, 3, 3] and pol.backlog == 0
    assert len(pipe.calls) == len(set(pipe.calls))  # one attempt per epoch
    pol, _, ok = drive(FrontLoadedArm, [0.0] * 20, cfg)
    assert [k for k, x in enumerate(ok) if x] == [0, 2, 4] and pol.lags() == [0, 0, 0]


def test_scheduled_arm_unexecuted_when_run_ends():
    cfg = replace(CFG, epochs=6, mutation_cap=3)
    pol, _, ok = drive(FrontLoadedArm, [0.0] * 6, cfg, fail_at={0, 1, 2, 3, 4, 5})
    assert sum(ok) == 0 and pol.backlog == 3


def test_schedule_independent_of_failures_and_values():
    a = RandomTimingArm(replace(Config(), mutation_cap=4), StubPipeline(), np.random.default_rng([7, 3])).schedule
    pol, _, _ = drive(RandomTimingArm, [0.9] * 80, replace(Config(), mutation_cap=4, epochs=80),
                      rng=np.random.default_rng([7, 3]), fail_at={1, 2, 3})
    assert pol.schedule == a


# ------------------------------------------------------------------ simulator-level checks
def test_static_invariant_to_delay_and_budget():
    a = pd.DataFrame(simulate(base_config(2), 100, "static", log_rounds=False)[0])
    b = pd.DataFrame(simulate(replace(base_config(8), mutation_cap=6), 100, "static", log_rounds=False)[0])
    pd.testing.assert_frame_equal(a, b)


def test_common_failure_trace_across_all_v06_arms():
    cfg = replace(base_config(2), epochs=30, mutation_cap=3, v06_threshold=0.4, v06_kappa=0.3)
    traces = {arm: pd.DataFrame(simulate(cfg, 101, ARM_POLICY[arm], log_rounds=False)[0]).n_down_potential.tolist()
              for arm in ARM_POLICY}
    assert len({tuple(t) for t in traces.values()}) == 1


def test_v06_arms_respect_cap_and_one_mutation_per_epoch_in_simulator():
    cfg = replace(base_config(2), epochs=30, mutation_cap=3, v06_threshold=0.2, v06_kappa=0.1)
    for arm in ("A1", "A2", "A3", "A4", "A5", "A6", "A7"):
        df = pd.DataFrame(simulate(cfg, 102, ARM_POLICY[arm], log_rounds=False)[0])
        assert df.n_mutations.iloc[-1] <= 3 and (df.select_outcome == "mutated").sum() == df.n_mutations.iloc[-1]


# ------------------------------------------------------------------ isolation, calibration rule, checksums
def test_seed_isolation_guards():
    assert_seeds(range(100, 120), range(100, 120), "calibration")
    with pytest.raises(IsolationError):
        assert_seeds([100, 6000], range(100, 120), "calibration")
    with pytest.raises(IsolationError):
        assert_seeds([6000, 119], range(6000, 6060), "eval run")


def test_calibration_choice_rule():
    grid = [(0.3, 9.0), (0.5, 6.2), (0.6, 5.8), (0.8, 3.0), (0.9, 1.0)]
    assert choose(grid, 3)[:2] == (0.8, 3.0) and choose(grid, 3)[2]
    thr, mean, ok = choose([(0.5, 5.8), (0.6, 6.2)], 6)        # tie |0.2| -> larger threshold
    assert thr == 0.6 and ok
    assert not choose([(0.5, 9.0), (0.9, 1.0)], 3)[2]        # outside +-15% -> not calibratable


def test_static_constants():
    df = pd.DataFrame({"E_hat": [0.1, 0.2, 0.3, 0.9], "components": [1, 1, 1, 2],
                       "C": [0.0, 0.0, 0.0, 1.0], "V": [0.0, 0.0, 0.0, 0.0]})
    c = static_constants(df)
    assert c["kappa_E"] == pytest.approx(0.2) and c["kappa_s"] == pytest.approx(0.1)
    assert c["tau"] == pytest.approx(np.quantile([0.1, 0.2, 0.3, 0.9], 0.75))


def test_manifest_detects_changes(tmp_path):
    f1, f2 = tmp_path / "a.yaml", tmp_path / "b.csv"
    f1.write_text("x: 1\n")
    f2.write_text("c\n1\n")
    man = tmp_path / "MANIFEST.sha256"
    write_manifest([str(f1), str(f2)], str(man))
    verify_manifest(str(man))
    f1.write_text("x: 2\n")
    with pytest.raises(RuntimeError, match="changed"):
        verify_manifest(str(man))
    f1.write_text("x: 1\n")
    (tmp_path / "extra.yaml").write_text("y: 1\n")
    with pytest.raises(RuntimeError, match="unlisted"):
        verify_manifest(str(man))
    with pytest.raises(RuntimeError, match="not found"):
        verify_manifest(str(tmp_path / "missing.sha256"))


def test_eval_runs_exactly_once_and_needs_clean_tree(tmp_path):
    clean = {"dirty_files": []}
    check_eval_allowed(str(tmp_path / "new"), clean)
    with pytest.raises(SystemExit, match="uncommitted"):
        check_eval_allowed(str(tmp_path / "new"), {"dirty_files": [" M tccer/x.py"]})
    done = tmp_path / "done"
    done.mkdir()
    (done / "COMPLETE").write_text("x")
    with pytest.raises(SystemExit, match="exactly once"):
        check_eval_allowed(str(done), clean)
    partial = tmp_path / "partial"
    partial.mkdir()
    (partial / "x.csv").write_text("x")
    with pytest.raises(SystemExit, match="not empty"):
        check_eval_allowed(str(partial), clean)


# ------------------------------------------------------------------ analysis functions (protocol 4-6)
def test_episode_classification_primary_and_sensitivity():
    flags = np.array([1, 0, 1, 1, 1, 0, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1], dtype=bool)
    eps = an.episodes(flags)
    assert eps == [(0, 1, False), (2, 3, False), (6, 4, False), (11, 6, True)]
    assert [an.classify_length(L) for _, L, _ in eps] == ["T", "I", "P", "P"]
    assert [an.classify_length(L, "S3") for _, L, _ in eps] == ["T", "P", "P", "P"]
    assert [an.classify_length(L, "S6") for _, L, _ in eps] == ["T", "I", "I", "P"]
    cls = an.epoch_classes(flags)
    assert list(cls[:6]) == ["T", "calm", "I", "I", "I", "calm"]


def test_run_metrics_precision_detection_wasted_recovery():
    an.CONST["tau"] = 0.5
    E0 = np.array([0.1] * 20)
    E0[5:10] = 0.9            # persistent episode 5..9
    E0[14] = 0.9              # transient at 14
    comp0 = np.ones(20, int)
    comp0[6:9] = 2            # static disconnected 6..8 (anchor at 6)
    static_g = pd.DataFrame({"epoch": range(20), "E_hat": E0, "components": comp0})
    labels = {"primary": an.epoch_classes(E0 > 0.5)}
    arm = pd.DataFrame({"epoch": range(20), "E_hat": 0.3, "final_error": 0.1, "components": 1, "lambda2": 0.1,
                        "pending_links": 0, "n_mutations": 0, "select_outcome": "", "mutation": "",
                        "removed_failed_link": False})
    arm.loc[[7, 14, 17], "select_outcome"] = "mutated"
    arm.loc[7, ["mutation", "removed_failed_link"]] = ["-1-2 +3-4", True]
    arm.loc[[6, 7], "components"] = 2
    arm["n_mutations"] = (arm.select_outcome == "mutated").cumsum()
    down = np.zeros((20, 1), bool)
    down[7:11, 0] = True     # released link (1,2) down 7..10; window for m=7, d=2 is 8..12 -> up at 11 -> wasted
    r = an.run_metrics(arm, static_g, labels, 2, 3, down, {(1, 2): 0})
    assert r["precision"] == pytest.approx(1 / 3) and r["false_alarm"] == pytest.approx(2 / 3)
    assert r["false_alarm_transient"] == pytest.approx(1 / 3) and r["false_alarm_calm"] == pytest.approx(1 / 3)
    assert r["detection_rate"] == 1.0 and r["detection_delay"] == 2
    assert r["wasted_releases"] == 1 and r["wasted_release_rate"] == 1.0
    assert r["anchored_recovery"] == 2 and r["anchors_censored"] == 0
    assert r["mutations"] == 3 and r["cap_hit"]


def test_trace_rebuild_matches_engine_and_detects_mismatch():
    cfg = base_config(2)
    df = pd.DataFrame(simulate(cfg, 103, "static", log_rounds=False)[0])
    down, index = an.rebuild_down(cfg, 103, df.n_down_potential.to_numpy())
    assert down.shape[0] == 80
    bad = df.n_down_potential.to_numpy().copy()
    bad[5] += 1
    with pytest.raises(RuntimeError, match="does not match"):
        an.rebuild_down(cfg, 103, bad)


def test_statistics_helpers_and_verdicts():
    assert an.wilcoxon_p(np.zeros(10)) == (1.0, 0, True)
    assert an.rank_biserial(np.array([1.0, 2.0, -0.5])) == pytest.approx((5 - 1) / 6)
    lo, hi = an.boot_ci(np.array([0.1, 0.2, 0.3, 0.4]))
    assert lo == an.boot_ci(np.array([0.1, 0.2, 0.3, 0.4]))[0] and lo <= 0.25 <= hi
    V = an.verdict
    assert V(0.01, -0.03, (-0.05, -0.01), False, prec_lo=-0.01) == "accumulated debt adds meaningful timing information"
    assert V(0.01, -0.03, (-0.05, -0.01), False, prec_lo=-0.08).startswith("first arm better on error, precision")
    assert V(0.01, -0.01, (-0.02, 0.0), False) == "first arm better, below minimum meaningful effect"
    assert V(0.01, 0.03, (0.01, 0.05), False) == "second arm meaningfully better"
    assert V(0.2, 0.001, (-0.01, 0.015), False) == "practically equivalent"
    assert V(0.2, 0.001, (-0.03, 0.015), False) == "inconclusive"
    assert V(1.0, 0.0, (0.0, 0.0), True) == "practically equivalent (identical)"


def test_removed_link_parsing():
    assert an.removed_link("-12-3 +4-9") == (3, 12) and an.removed_link("+4-9") is None


def test_family_holm_and_verdicts_on_synthetic_data():
    rng = np.random.default_rng(0)
    rows = []
    for d, M in [(2, 3), (2, 6), (8, 3), (8, 6)]:
        cell = f"d{d}_M{M}"
        for s in range(60):
            base = rng.uniform(0.3, 0.5)
            shift = -0.05 if cell == "d2_M3" else 0.0          # A3 clearly better only in d2_M3
            for arm, e in (("A1", base), ("A3", base + shift + rng.normal(0, 0.005))):
                rows.append({"group": cell, "arm": arm, "seed": s, "E": e, "precision": 0.5})
    ps = pd.DataFrame(rows)
    fam = an.family(ps, [("A3", "A1")], [(2, 3), (2, 6), (8, 3), (8, 6)], "primary", primary=True)
    assert (fam.status == "tested").all() and len(fam) == 4
    raw = fam.set_index("cell").wilcoxon_p
    assert (fam.holm_p >= fam.wilcoxon_p - 1e-15).all()
    v = fam.set_index("cell").verdict
    assert v["d2_M3"] == "accumulated debt adds meaningful timing information"
    assert v["d8_M6"] in ("practically equivalent", "inconclusive")
    assert raw["d2_M3"] < 1e-6
    missing = an.family(ps[ps.arm == "A1"], [("A3", "A1")], [(2, 3)], "primary", primary=True)
    assert (missing.status == "excluded (not calibratable)").all() and missing.holm_p.isna().all()
