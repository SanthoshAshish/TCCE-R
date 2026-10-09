"""v0.5: scenario-file input, summary.txt, network visualisation, demo configs, default-behaviour preservation."""
import io
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest
import yaml

from tccer.config import Config, load_config, replace
from tccer.network.scenario import ScenarioError, load_scenario
from tccer.policies import POLICIES
from tccer.sim.engine import simulate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLE_CFG = os.path.join(ROOT, "examples", "grid_scenario_config.yaml")


def scripted_only(cfg):
    return replace(cfg, p_transient=0.0, p_fail=0.0, burst_rate=0.0)


def down_by_epoch(cfg, seed=0, policy="static"):
    """{epoch: set of (u, v) links that are down during that epoch}."""
    out = {}

    def obs(k, state, m):
        out[k] = {state.edge(i) for i in np.flatnonzero(state.down)}
    simulate(cfg, seed, policy, log_rounds=False, on_epoch=obs)
    return out


# ------------------------------------------------------------------ default behaviour is preserved
@pytest.mark.parametrize("policy", ["static", "tccer"])
def test_default_run_matches_archived_v04_rows(policy):
    """No scenario_file -> identical to the archived v0.4 held-out run (seed 5000, delay 2)."""
    cfg = load_config(os.path.join(ROOT, "configs", "v0.4", "selected_d2.yaml"))
    assert cfg.scenario_file is None
    arch = pd.read_csv(os.path.join(ROOT, "archive", "v0.4", "eval_d2", "epochs.csv"))
    old = arch[(arch.seed == 5000) & (arch.policy == policy)].reset_index(drop=True)
    new = pd.DataFrame(simulate(cfg, 5000, policy, log_rounds=False)[0])
    cols = [c for c in old.columns if c in new.columns]           # columns this policy logs
    assert set(old.columns) - set(cols) <= {"debt", "stress", "theta", "triggered", "feedback"}
    roundtrip = lambda d: pd.read_csv(io.StringIO(d[cols].to_csv(index=False)))   # same CSV text -> same values
    pd.testing.assert_frame_equal(roundtrip(old), roundtrip(new))
    assert (new.n_scripted_down == 0).all()


# ------------------------------------------------------------------ scripted events at the right epochs
def test_scripted_link_events_happen_at_exact_epochs():
    cfg = scripted_only(load_config(EXAMPLE_CFG))
    down = down_by_epoch(cfg)
    for k in range(cfg.epochs):
        assert ((3, 7) in down[k]) == (12 <= k < 20), k        # fail at 12, recover at 20
        # (11,15): fail at 15, recover at 22; it also lies in the top-right region outage (epochs 24-26)
        assert ((11, 15) in down[k]) == (15 <= k < 22 or 24 <= k < 27), k


def test_scripted_region_events_cover_duration_only():
    cfg = scripted_only(load_config(EXAMPLE_CFG))
    sc = load_scenario(cfg.scenario_file, cfg)
    down = down_by_epoch(cfg)
    left = [e for e in sc.events if e["type"] == "region" and e["epoch"] == 6][0]["links"]
    top_right = [e for e in sc.events if e["type"] == "region" and e["epoch"] == 24][0]["links"]
    for k in range(cfg.epochs):
        for l in left:
            assert (l in down[k]) == (6 <= k < 11 or 16 <= k < 20), (k, l)
        for l in top_right:
            if l != (11, 15):                                   # (11,15) also has its own link events
                assert (l in down[k]) == (24 <= k < 27), (k, l)


def test_purely_scripted_scenario_has_no_random_failures():
    cfg = scripted_only(load_config(EXAMPLE_CFG))
    df = pd.DataFrame(simulate(cfg, 3, "tccer", log_rounds=False)[0])
    assert (df.n_down_potential == df.n_scripted_down).all()
    assert df.n_scripted_down.max() > 0


def test_random_failures_still_active_with_scenario():
    cfg = replace(load_config(EXAMPLE_CFG), p_fail=0.05)
    df = pd.DataFrame(simulate(cfg, 3, "static", log_rounds=False)[0])
    assert (df.n_down_potential >= df.n_scripted_down).all()
    assert (df.n_down_potential > df.n_scripted_down).any()


def test_all_policies_receive_identical_failure_trace():
    cfg = replace(load_config(EXAMPLE_CFG), p_fail=0.03)
    ref = None
    for p in POLICIES:
        df = pd.DataFrame(simulate(cfg, 2, p, log_rounds=False)[0])
        trace = (df.n_down_potential.tolist(), df.n_scripted_down.tolist())
        ref = ref or trace
        assert trace == ref, p
    sets = [down_by_epoch(cfg, 2, p) for p in ["static", "reactive", "tccer"]]
    assert sets[0] == sets[1] == sets[2]


def test_initial_values_are_used():
    cfg = scripted_only(load_config(EXAMPLE_CFG))
    sc = load_scenario(cfg.scenario_file, cfg)
    assert sc.initial_values.shape == (cfg.epochs, 16)
    assert (sc.initial_values[0] == [0, 0, 1, 1] * 4).all()


def test_constant_initial_values_give_zero_consensus_error(tmp_path):
    s, c = _write(tmp_path, {"initial_values": [0.5] * 4})
    df = pd.DataFrame(simulate(load_config(c), 0, "static", log_rounds=False)[0])
    assert (df.E_hat == 0).all()


def test_per_epoch_initial_values(tmp_path):
    vals = [[float(k), 0.0, 0.0, 0.0] for k in range(10)]
    s, c = _write(tmp_path, {"initial_values": vals})
    sc = load_scenario(load_config(c).scenario_file, load_config(c))
    assert sc.initial_values[7, 0] == 7.0


def test_scenario_path_is_resolved_relative_to_config():
    cfg = load_config(EXAMPLE_CFG)
    assert os.path.isabs(cfg.scenario_file)
    assert os.path.samefile(cfg.scenario_file, os.path.join(ROOT, "examples", "grid_scenario.yaml"))


def test_default_potential_links_from_radio_range(tmp_path):
    s, c = _write(tmp_path, {}, drop=("potential_links",))
    cfg = load_config(c)
    sc = load_scenario(cfg.scenario_file, cfg)
    assert len(sc.eu) == 4          # square of side 0.2 with radio_range 0.25: 4 sides, no diagonals


# ------------------------------------------------------------------ validation
BASE = {
    "nodes": [[0.0, 0.0], [0.2, 0.0], [0.2, 0.2], [0.0, 0.2]],
    "potential_links": [[0, 1], [1, 2], [2, 3], [0, 3], [0, 2]],
    "initial_links": [[0, 1], [1, 2], [2, 3]],
}


def _write(tmp_path, changes, drop=()):
    data = {k: v for k, v in BASE.items() if k not in drop}
    data.update(changes)
    s = tmp_path / "s.yaml"
    s.write_text(yaml.safe_dump(data))
    c = tmp_path / "c.yaml"
    c.write_text(yaml.safe_dump({"scenario_file": "s.yaml", "epochs": 10, "rounds_per_epoch": 5,
                                 "radio_range": 0.25, "budget_on": "configured", "edge_budget_frac": 1.0}))
    return str(s), str(c)


INVALID = [
    ({"initial_links": [[0, 1], [1, 7]]}, "node index 7 does not exist"),
    ({"initial_links": [[0, 1], [2, 2]]}, "connects a node to itself"),
    ({"initial_links": [[0, 1], [1, 0]]}, "listed twice"),
    ({"potential_links": [[0, 1], [1, 2]]}, "not in potential_links"),
    ({"edges": []}, "unknown key"),
    ({"nodes": [[0, 0], [1, "a"], [0, 1], [1, 1]]}, "nodes[1]"),
    ({"initial_values": [1, 2, 3]}, "has 3 values but there are 4 nodes"),
    ({"initial_values": [[1, 2, 3, 4]]}, "per-epoch lists"),
    ({"failure_events": [{"epoch": 10, "link": [0, 1], "action": "fail"}]}, "integer from 0 to 9"),
    ({"failure_events": [{"epoch": -1, "link": [0, 1], "action": "fail"}]}, "integer from 0 to 9"),
    ({"failure_events": [{"epoch": 2, "link": [1, 3], "action": "fail"}]}, "not a potential link"),
    ({"failure_events": [{"epoch": 2, "link": [0, 1], "action": "break"}]}, "'action' must be 'fail' or 'recover'"),
    ({"failure_events": [{"epoch": 2, "link": [0, 1], "action": "recover"}]}, "without an earlier"),
    ({"failure_events": [{"epoch": 2, "link": [0, 1], "action": "fail"},
                         {"epoch": 4, "link": [0, 1], "action": "fail"}]}, "already failed since epoch 2"),
    ({"failure_events": [{"epoch": 2, "link": [0, 1], "action": "fail"},
                         {"epoch": 2, "link": [1, 0], "action": "recover"}]}, "same epoch 2"),
    ({"failure_events": [{"epoch": 2, "link": [0, 1], "action": "fail", "region": {}}]}, "either 'link' or 'region'"),
    ({"failure_events": [{"epoch": 2, "region": {"center": [5, 5], "radius": 0.1}, "duration": 2}]},
     "contains no link midpoint"),
    ({"failure_events": [{"epoch": 2, "region": {"center": [0.1, 0.1], "radius": -1}, "duration": 2}]},
     "radius must be a positive number"),
    ({"failure_events": [{"epoch": 2, "region": {"center": [0.1, 0.1], "radius": 0.3}, "duration": 0}]},
     "'duration' must be a whole number"),
    ({"failure_events": [{"epoch": 2}]}, "needs either 'link'"),
]


@pytest.mark.parametrize("changes,message", INVALID)
def test_invalid_scenarios_are_rejected_with_clear_message(tmp_path, changes, message):
    s, c = _write(tmp_path, changes)
    with pytest.raises(ScenarioError) as e:
        load_scenario(s, load_config(c))
    assert message in str(e.value) and "s.yaml" in str(e.value)


def test_missing_required_key_and_missing_file(tmp_path):
    s, c = _write(tmp_path, {}, drop=("initial_links",))
    with pytest.raises(ScenarioError, match="required key 'initial_links'"):
        load_scenario(s, load_config(c))
    with pytest.raises(ScenarioError, match="not found"):
        load_scenario(str(tmp_path / "nope.yaml"), load_config(c))
    (tmp_path / "bad.yaml").write_text("nodes: [[0, 0]\n")
    with pytest.raises(ScenarioError, match="not valid YAML"):
        load_scenario(str(tmp_path / "bad.yaml"), load_config(c))


def test_valid_scenario_runs_for_every_policy(tmp_path):
    s, c = _write(tmp_path, {"failure_events": [{"epoch": 3, "link": [1, 2], "action": "fail"},
                                                {"epoch": 6, "link": [1, 2], "action": "recover"}]})
    for p in POLICIES:
        rows, _ = simulate(load_config(c), 0, p, log_rounds=False)
        assert [r["n_scripted_down"] for r in rows] == [0, 0, 0, 1, 1, 1, 0, 0, 0, 0]


# ------------------------------------------------------------------ demo configs
def test_demo_config_uses_selected_v04_settings():
    demo = load_config(os.path.join(ROOT, "configs", "v0.5", "demo.yaml"))
    sel = load_config(os.path.join(ROOT, "configs", "v0.4", "selected_d2.yaml"))
    for k in ["w_E", "w_C", "w_V", "kappa", "reactive_threshold", "degree_fix", "degree_basis",
              "feedback_after_setup", "failed_link_value", "budget_on", "edge_budget_frac", "link_setup_epochs",
              "burst_rate", "p_fail"]:
        assert getattr(demo, k) == getattr(sel, k), k


# ------------------------------------------------------------------ end to end: run, analyze, visualize
def _run(*args):
    return subprocess.run([sys.executable, "-m", *args], cwd=ROOT, check=True, capture_output=True, text=True)


def test_end_to_end_scenario_run_outputs(tmp_path):
    out = tmp_path / "run"
    _run("experiments.run", "--config", EXAMPLE_CFG, "--seeds", "5", "--policies", "static", "periodic",
         "reactive", "tccer", "--out", str(out))
    _run("experiments.analyze", str(out))
    viz = tmp_path / "viz"
    _run("experiments.visualize", "--config", EXAMPLE_CFG, "--seed", "0", "--epochs", "0", "17", "25",
         "--out", str(viz))
    for f in ["epochs.csv", "rounds.csv", "config_used.yaml", "scenario_used.yaml", "summary.csv",
              "paired_tests.csv", "summary.txt", "timeseries.png", "summary_bars.png", "tccer_trace.png"]:
        assert (out / f).exists(), f
    for f in ["network_initial.png", "network_snapshots.png", "edge_states.csv"]:
        assert (viz / f).exists(), f
    txt = (out / "summary.txt").read_text(encoding="utf-8")
    assert "scenario file" in txt and "tccer" in txt and "always simulated first" in txt

    # the pictures show the same runs as the CSV: working links per snapshot epoch must match
    ep = pd.read_csv(out / "epochs.csv")
    es = pd.read_csv(viz / "edge_states.csv")
    for (p, k), g in es.groupby(["policy", "epoch"]):
        live = int(g.status.isin(["active", "rewired in"]).sum())
        assert live == int(ep[(ep.seed == 0) & (ep.policy == p) & (ep.epoch == k)].live_edges.iloc[0]), (p, k)
        failed = int((g.status == "failed").sum())
        assert failed <= int(ep[(ep.seed == 0) & (ep.policy == p) & (ep.epoch == k)].n_down_potential.iloc[0])


def test_visualization_is_reproducible(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        _run("experiments.visualize", "--config", EXAMPLE_CFG, "--seed", "1", "--epochs", "5", "18",
             "--policies", "static", "tccer", "--out", str(d))
    pd.testing.assert_frame_equal(pd.read_csv(a / "edge_states.csv"), pd.read_csv(b / "edge_states.csv"))


def test_visualize_rejects_out_of_range_epoch(tmp_path):
    r = subprocess.run([sys.executable, "-m", "experiments.visualize", "--config", EXAMPLE_CFG, "--epochs", "99",
                        "--out", str(tmp_path)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode != 0 and "out of range" in r.stderr
