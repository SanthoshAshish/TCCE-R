"""v0.7 counterfactual feedback: consistency with the factual run, beneficial / harmful / ineffective / placebo
cases, overlap isolation, no use of future information, invalid windows, and unchanged default behaviour."""
import os
import warnings

import numpy as np
import pandas as pd
import pytest
import yaml

import tccer.sim.engine as eng
from tccer.config import load_config, replace
from tccer.core.counterfactual import CounterfactualFeedback, Snapshot
from tccer.core.feedback import FeedbackEvaluator
from tccer.core.mutations import Mutation
from tccer.policies import POLICIES
from tccer.sim.engine import simulate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUSTOM = os.path.join(ROOT, "configs", "v0.5", "custom_4node.yaml")
CF = dict(feedback_rule="counterfactual")


def custom(**kw):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return replace(load_config(CUSTOM), **kw)


def run_capture(cfg, seed, policy):
    """simulate() and return (rows, policy instance) so the attached exogenous record can be inspected."""
    holder = {}
    base = POLICIES[policy]

    class Spy(base):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            holder["p"] = self

    POLICIES[policy] = Spy
    try:
        rows, _ = simulate(cfg, seed, policy, log_rounds=False)
    finally:
        POLICIES[policy] = base
    return pd.DataFrame(rows).set_index("epoch"), holder["p"]


def snap_of(df_unused, p, m, cfg):
    """Snapshot equal to the initial topology (valid when no mutation happened before epoch m)."""
    rec = p.ctx
    configured = np.zeros(len(rec.eu), bool)
    from tccer.network.scenario import load_scenario
    configured[load_scenario(cfg.scenario_file, cfg).init_idx] = True
    return Snapshot(epoch=m, configured=configured, ready_at=np.zeros(len(rec.eu), int))


# ------------------------------------------------------------------ consistency with the factual simulation
def test_with_branch_reproduces_factual_run_and_without_branch_reproduces_static():
    cfg = custom(**CF)
    df, p = run_capture(cfg, 0, "tccer")
    assert df.select_outcome[6] == "mutated" and (df.select_outcome == "mutated").sum() == 1
    m, d, H = 6, cfg.link_setup_epochs, cfg.feedback_horizon
    window = list(range(m + 1, m + d + H + 1))
    snap = snap_of(df, p, m, cfg)
    mut = Mutation(add=None, remove=None)
    # rebuild the applied mutation from the log ("-0-1 +0-2")
    rec = p.ctx
    rm, ad = df.mutation[6].split()
    idx = {(int(a), int(b)): i for i, (a, b) in enumerate(zip(rec.eu, rec.ev))}
    mut = Mutation(add=idx[tuple(sorted(map(int, ad[1:].split("-"))))],
                   remove=idx[tuple(sorted(map(int, rm[1:].split("-"))))])
    E_with = rec.replay(snap, mut, window, now=79 if cfg.epochs > 79 else cfg.epochs - 1)
    E_without = rec.replay(snap, None, window, now=cfg.epochs - 1)
    assert np.array_equal(E_with, df.E_hat.loc[window].to_numpy())             # exactly the factual run
    static, _ = run_capture(cfg, 0, "static")
    assert np.array_equal(E_without, static.E_hat.loc[window].to_numpy())     # exactly the no-mutation run


# ------------------------------------------------------------------ beneficial / harmful / ineffective / placebo
def test_beneficial_mutation_is_success():
    df, p = run_capture(custom(**CF), 0, "tccer")
    assert df.feedback[10].startswith("6:S")                                  # reconnection: Delta < 0
    delta = float(df.feedback[10].split("(")[1].rstrip(")"))
    assert delta < 0
    assert df.theta[10] == pytest.approx(1.0 * (1 - 0.1))


def test_harmful_mutation_is_failure_and_ineffective_is_neutral_and_placebo_is_neutral():
    # 5 consensus rounds so that topology matters; window m+1..m+d+H = 1..4 ends before the failures at epoch 5
    cfg = custom(rounds_per_epoch=5, **CF)
    _, p = run_capture(cfg, 0, "static")                                      # static run -> observed record
    rec = p.ctx
    idx = {(int(a), int(b)): i for i, (a, b) in enumerate(zip(rec.eu, rec.ev))}
    fb = CounterfactualFeedback(cfg, rec)
    base = snap_of(None, p, 0, cfg)
    harmful = Mutation(add=idx[(0, 2)], remove=idx[(0, 1)])                   # 4-cycle -> triangle + pendant
    fb.register(base, harmful)
    fb.register(Snapshot(2, base.configured.copy(), base.ready_at.copy()), None)   # no-mutation placebo
    res = {m: (o, dlt) for m, o, dlt in fb.evaluate(14)}
    assert res[0][0] == "F" and res[0][1] > 0
    assert res[2] == ("N", 0.0)
    # ineffective: release a link that stays failed through the window and add a link that is failed too
    scen = yaml.safe_load(open(os.path.join(ROOT, "examples", "custom_4node.yaml"), encoding="utf-8"))
    scen["failure_events"] = [{"epoch": 0, "link": [0, 2], "action": "fail"},
                              {"epoch": 0, "link": [0, 1], "action": "fail"}]
    tmp = os.path.join(os.path.dirname(cfg.scenario_file), "_tmp_ineffective_scenario.yaml")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            yaml.safe_dump(scen, f)
        cfg2 = replace(cfg, scenario_file=tmp)
        _, p2 = run_capture(cfg2, 0, "static")
        fb2 = CounterfactualFeedback(cfg2, p2.ctx)
        fb2.register(snap_of(None, p2, 2, cfg2), Mutation(add=idx[(0, 2)], remove=idx[(0, 1)]))
        assert fb2.evaluate(14) == [(2, "N", 0.0)]
    finally:
        os.remove(tmp)


def test_placebo_never_succeeds_on_bursty_dev_seeds_while_old_rule_often_does():
    cfg = replace(load_config(os.path.join(ROOT, "configs", "v0.6", "frozen", "A0_static.yaml")),
                  epochs=40, **CF)
    new_s, old_s, n = 0, 0, 0
    for seed in (300, 301, 302):
        df, p = run_capture(cfg, seed, "static")
        rec = p.ctx
        conf = np.zeros(len(rec.eu), bool)
        from tccer.network.generators import random_geometric
        conf[random_geometric(cfg.n_nodes, cfg.init_radius, cfg.radio_range, seed)[4]] = True
        E = df.E_hat.to_numpy()
        for m in range(3, 40 - cfg.link_setup_epochs - cfg.feedback_horizon):
            if E[m] < np.quantile(E, 0.75):
                continue                                                      # placebo at high-stress epochs
            fb = CounterfactualFeedback(cfg, rec)
            fb.register(Snapshot(m, conf, np.zeros(len(conf), int)), None)
            (_, o, dlt), = fb.evaluate(39)
            new_s += o == "S"
            old = FeedbackEvaluator(replace(cfg, feedback_after_setup=True))
            old.register(m)
            old_s += old.evaluate(39, list(E))[0][1]
            n += 1
    assert n >= 10 and new_s == 0                                             # counterfactual: never "success"
    assert old_s / n > 0.5                                                    # before/after: regression to the mean


# ------------------------------------------------------------------ overlap isolation, no future information, invalid
def test_overlapping_mutations_do_not_share_attribution():
    """The first mutation's Delta is identical whether or not a second mutation happens inside its window."""
    found = 0
    for seed in range(300, 320):
        cfg = replace(load_config(os.path.join(ROOT, "configs", "v0.6", "frozen", "A0_static.yaml")),
                      epochs=60, feedback_rule="counterfactual", w_E=1.0, w_C=0.0, w_V=0.0, kappa=0.3,
                      theta0=0.5, theta_min=0.25, trigger_cooldown=2)
        a, _ = run_capture(cfg, seed, "tccer")
        muts = a.index[a.select_outcome == "mutated"].tolist()
        if len(muts) < 2 or muts[1] > muts[0] + cfg.link_setup_epochs + cfg.feedback_horizon:
            continue
        b, _ = run_capture(replace(cfg, mutation_cap=1), seed, "tccer")
        fa = [x for x in a.feedback.dropna() if x.startswith(f"{muts[0]}:")]
        fb = [x for x in b.feedback.dropna() if x.startswith(f"{muts[0]}:")]
        assert fa and fa == fb
        found += 1
        if found == 2:
            break
    assert found >= 1


def test_replay_refuses_future_epochs_and_window_past_end_is_unevaluated():
    cfg = custom(**CF)
    _, p = run_capture(cfg, 0, "static")
    with pytest.raises(ValueError, match="future"):
        p.ctx.replay(snap_of(None, p, 3, cfg), None, [4, 5], now=4)
    fb = CounterfactualFeedback(cfg, p.ctx)
    fb.register(snap_of(None, p, 13, cfg), None)                              # window 14..17 > last epoch 14
    assert fb.evaluate(14) == [] and fb.unevaluated() == [13]


def test_default_rule_is_unchanged_before_after():
    df, _ = run_capture(custom(), 0, "tccer")                                 # feedback_rule default
    assert df.feedback[10] == "6:S"                                           # v0.6.1 behaviour, no delta suffix


def test_v06_a5_arm_legacy_rule_still_reproduces_archived_dry_run():
    import io
    arch = os.path.join(ROOT, "archive", "v0.6", "dryrun_rev4", "d2_M3", "epochs.csv")
    old = pd.read_csv(arch, low_memory=False)
    old = old[(old.arm == "A5") & (old.seed == 100)].drop(columns=["arm"]).reset_index(drop=True).dropna(axis=1, how="all")
    cfg = load_config(os.path.join(ROOT, "configs", "v0.6", "frozen", "A5_d2_M3.yaml"))
    assert cfg.feedback_rule == "before_after"
    new = pd.DataFrame(simulate(cfg, 100, "v06_tccer", log_rounds=False)[0])
    cols = [c for c in old.columns if c in new.columns]
    rt = lambda d: pd.read_csv(io.StringIO(d[cols].to_csv(index=False)))
    pd.testing.assert_frame_equal(rt(old), rt(new), check_dtype=False)


def test_a5_arm_counterfactual_mode_logs_outcomes_and_neutral_does_not_move_theta():
    cfg = replace(load_config(os.path.join(ROOT, "configs", "v0.6", "frozen", "A5_d2_M6.yaml")),
                  feedback_rule="counterfactual", mutation_cap=None)
    seen = set()
    for seed in (300, 301, 302, 303):
        df = pd.DataFrame(simulate(cfg, seed, "v06_tccer", log_rounds=False)[0])
        prev = None
        for _, r in df.iterrows():
            upd = r.theta_update if isinstance(r.theta_update, str) else ""
            for m, o, d in __import__("re").findall(r"(\d+):([SFN])\(([^)]*)\)", upd):
                seen.add(o)
                if o == "N":
                    assert float(d) == 0.0
            if prev is not None and upd and all(x[1] == "N" for x in __import__("re").findall(r"(\d+):([SFN])", upd)):
                assert r.theta == prev                                         # neutral-only epochs keep theta
            prev = r.theta
    assert {"S", "F"} <= seen
