"""Architecture-level checks: monitor (local disagreement), config robustness, and the full nine-stage chain
debt -> trigger -> coupling evaluator -> safety gate -> selector -> reconfigured network -> feedback -> threshold."""
import io
import os
import warnings

import networkx as nx
import numpy as np
import pandas as pd
import pytest
import yaml

from tccer.config import duplicate_top_level_keys, load_config, replace
from tccer.consensus.algorithm import local_disagreement, run_epoch, run_epoch_state
from tccer.metrics.resilience import laplacian
from tccer.sim.engine import simulate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUSTOM = os.path.join(ROOT, "configs", "v0.5", "custom_4node.yaml")


def load_quiet(path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return load_config(path)


# ------------------------------------------------------------------ (2) consensus monitor
def test_local_disagreement_values_and_laplacian_identity():
    x = np.array([0.0, 1.0, 3.0])
    u, v = np.array([0, 1]), np.array([1, 2])                 # path 0-1-2
    d = local_disagreement(x, u, v)
    assert list(d) == [1.0, 5.0, 4.0]
    assert d.sum() / 2 == pytest.approx(x @ laplacian(3, u, v) @ x)
    assert list(local_disagreement(x, np.array([], int), np.array([], int))) == [0.0, 0.0, 0.0]


def test_run_epoch_state_matches_run_epoch_and_preserves_mean():
    g = nx.cycle_graph(6)
    e = np.array(list(g.edges()))
    x0 = np.random.default_rng(3).random(6)
    up = lambda t: np.ones(len(e), bool)
    err, x = run_epoch_state(x0, e[:, 0], e[:, 1], up, 30)
    assert np.array_equal(err, run_epoch(x0, e[:, 0], e[:, 1], up, 30))
    assert x.mean() == pytest.approx(x0.mean())


def test_engine_logs_local_disagreement():
    rows, _ = simulate(load_quiet(CUSTOM), 0, "static", log_rounds=False)
    df = pd.DataFrame(rows)
    assert (df.local_disagreement_total >= 0).all() and (df.local_disagreement_max >= 0).all()
    assert df.local_disagreement_total.iloc[:5].max() < 1e-12      # converged 4-cycle before the failures


# ------------------------------------------------------------------ config robustness
def test_duplicate_config_keys_warn_and_last_value_wins(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("epochs: 80\nrounds_per_epoch: 10\nepochs: 15\n")
    assert duplicate_top_level_keys(p.read_text()) == ["epochs"]
    with pytest.warns(UserWarning, match="repeats key"):
        assert load_config(str(p)).epochs == 15
    q = tmp_path / "ok.yaml"
    q.write_text("epochs: 12\n")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert load_config(str(q)).epochs == 12


# ------------------------------------------------------------------ the full chain on the custom 4-node scenario
def test_full_chain_on_custom_scenario():
    """Deterministic scenario (no random failures): links 0-1 and 2-3 fail at epoch 5, recover at epoch 10."""
    cfg = load_quiet(CUSTOM)
    df = pd.DataFrame(simulate(cfg, 0, "tccer", log_rounds=False)[0]).set_index("epoch")
    kappa, theta0 = cfg.kappa, cfg.theta0
    # (1)-(3): failure -> disconnection -> stress -> CUSUM debt
    assert df.components[4] == 1 and df.components[5] == 2
    assert df.debt[5] == pytest.approx(max(0.0, df.stress[5] - kappa))
    assert df.debt[5] < theta0 and not df.triggered[5]
    # (4)-(7): debt crosses theta -> trigger -> reconnecting candidate ranked first (M_dcomp=-1) -> gate -> applied
    assert df.debt.loc[:5].iloc[-1] + df.stress[6] - kappa > theta0 and df.triggered[6]
    assert df.select_outcome[6] == "mutated" and df.M_dcomp[6] == -1
    assert df.debt[6] == 0.0                                        # debt repaid after the mutation
    # (8): break-before-make -> link in setup at 7, network reconnected at 8
    assert df.pending_links[7] == 1 and df.components[7] == 2 and df.components[8] == 1
    # (9): feedback window 8..10 (m+1+d .. m+d+H) judged at epoch 10 -> success -> theta * (1 - beta)
    assert df.feedback[10] == "6:S"
    assert df.theta[9] == theta0 and df.theta[10] == pytest.approx(theta0 * (1 - cfg.beta))
    fixed = pd.DataFrame(simulate(cfg, 0, "tccer_fixed", log_rounds=False)[0])
    assert (fixed.theta == theta0).all()                           # ablation: theta never adapts


def test_chain_when_selector_finds_no_candidate(tmp_path):
    """No spare links: the trigger fires, the selector has nothing valid, the debt is NOT repaid, the trigger
    keeps firing, and no feedback/threshold update happens."""
    scen = yaml.safe_load(open(os.path.join(ROOT, "examples", "custom_4node.yaml"), encoding="utf-8"))
    scen["potential_links"] = scen["initial_links"]                 # nothing to rewire to
    (tmp_path / "s.yaml").write_text(yaml.safe_dump(scen))
    cfg = replace(load_quiet(CUSTOM), scenario_file=str(tmp_path / "s.yaml"))
    df = pd.DataFrame(simulate(cfg, 0, "tccer", log_rounds=False)[0]).set_index("epoch")
    fired = df.index[df.triggered.astype(bool)]
    assert len(fired) >= 2
    assert set(df.select_outcome[fired]) <= {"no_candidates", "all_rejected"}
    assert (df.n_mutations == 0).all() and (df.theta == cfg.theta0).all()
    assert all(df.debt[k] > df.debt[k - 1] for k in fired if k - 1 in df.index and df.components[k] > 1)


def test_gate_and_cooldown_interaction_in_chain():
    """After a successful mutation the next attempt waits for the trigger cooldown, even if debt re-crosses theta."""
    cfg = replace(load_quiet(CUSTOM), theta0=0.1, theta_min=0.05, trigger_cooldown=3)
    df = pd.DataFrame(simulate(cfg, 0, "tccer", log_rounds=False)[0])
    muts = df.epoch[df.select_outcome == "mutated"].tolist()
    assert all(b - a >= 3 for a, b in zip(muts, muts[1:]))


# ------------------------------------------------------------------ v0.6 outputs unaffected (tuning seed, archived dry run)
@pytest.mark.parametrize("arm,policy", [("A1", "v06_reactive"), ("A3", "v06_cusum_e"), ("A6", "v06_random")])
def test_v06_dry_run_rows_reproduce(arm, policy):
    arch = os.path.join(ROOT, "archive", "v0.6", "dryrun_rev4", "d2_M3", "epochs.csv")
    old = pd.read_csv(arch, low_memory=False)
    old = old[(old.arm == arm) & (old.seed == 100)].drop(columns=["arm"]).reset_index(drop=True)
    old = old.dropna(axis=1, how="all")
    cfg = load_config(os.path.join(ROOT, "configs", "v0.6", "frozen", f"{arm}_d2_M3.yaml"))
    new = pd.DataFrame(simulate(cfg, 100, policy, log_rounds=False)[0])
    cols = [c for c in old.columns if c in new.columns]
    rt = lambda d: pd.read_csv(io.StringIO(d[cols].to_csv(index=False)))
    pd.testing.assert_frame_equal(rt(old), rt(new), check_dtype=False)   # combined CSV stores ints as float
