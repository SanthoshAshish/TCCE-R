"""Focused v0.7 comparison (experiments/focused_v07.py): seeds, run counts, guards, and a miniature pipeline."""
import os
import sys

import pandas as pd
import pytest

import experiments.focused_v07 as fv
from experiments.v07_common import IsolationError


def test_seed_ranges_disjoint_from_reserved_and_archived_ranges():
    cal, ev = set(fv.CAL_SEEDS), set(fv.EVAL_SEEDS)
    reserved = set(range(200, 220)) | set(range(300, 320)) | set(range(7000, 7060))
    archived = (set(range(0, 20)) | set(range(100, 120)) | set(range(1000, 1030)) | set(range(2000, 2030)) |
                set(range(3000, 3030)) | set(range(4000, 4030)) | set(range(5000, 5030)) | set(range(6000, 6060)))
    assert not cal & ev and not (cal | ev) & reserved and not (cal | ev) & archived
    assert len(cal) == 20 and len(ev) == 60


def test_exact_run_counts_match_the_plan():
    cal = len(fv.SCENARIOS) * len(fv.CAL_SEEDS) + len(fv.ARMS) * len(fv.SCENARIOS) * 24 * len(fv.CAL_SEEDS)
    ev = len(fv.SCENARIOS) * len(fv.EVAL_SEEDS) + len(fv.ARMS) * len(fv.CELLS) * len(fv.EVAL_SEEDS)
    assert (cal, ev, cal + ev) == (4380, 1260, 5640)
    assert all(len(g) == 24 for g in fv.GRIDS.values()) and len(fv.CELLS) == 6
    assert fv.CAL_CAP >= 2 * max(fv.BUDGETS)


def test_layout_guards_and_smoke_grid():
    real, smoke = fv.Layout(False), fv.Layout(True)
    n = os.path.normpath
    assert n(real.frozen) == n("configs/v0.7_focused/frozen") and n(real.run_out) == n("results/v0.7_focused/eval")
    assert n(smoke.frozen).startswith(n("results/v0.7_focused/smoke"))               # smoke never touches real paths
    assert n(smoke.run_out) != n(real.run_out) and n(smoke.frozen) != n(real.frozen)
    assert len(smoke.grid("A1")) == fv.SMOKE_POINTS and set(smoke.grid("A3")) <= set(fv.GRIDS["A3"])
    with pytest.raises(IsolationError):
        fv.assert_seeds([7000], real.eval_allowed, "focused evaluation")
    with pytest.raises(IsolationError):
        fv.assert_seeds([500], real.cal_allowed, "focused calibration")


def mini(tmp_path):
    L = fv.Layout(True)
    L.frozen, L.cal_out, L.run_out = (str(tmp_path / "frozen"), str(tmp_path / "cal"), str(tmp_path / "run"))
    L.manifest = os.path.join(L.frozen, "MANIFEST.sha256")
    return L


def test_miniature_pipeline_and_guards(tmp_path):
    L = mini(tmp_path)
    fv.calibrate(L, 2)
    assert os.path.exists(L.manifest) and os.path.exists(os.path.join(L.frozen, "constants.yaml"))
    rep = pd.read_csv(os.path.join(L.frozen, "calibration_report.csv"))
    assert len(rep) == 18 and set(rep.arm) == {"A1", "A3", "A5"} and (rep.threshold > 0).all()
    with pytest.raises(SystemExit, match="frozen"):                       # no recalibration once frozen
        fv.calibrate(L, 2)
    fv.evaluate(L, 2)
    info = pd.read_json(os.path.join(L.run_out, "run_info.json"), typ="series")
    assert info["complete"] and info["n_runs"] == 42 and len(info["script_sha256"]) == 64
    fv.analyze(L)
    out = os.path.join(L.run_out, "analysis")
    for f in ("REPORT.md", "primary_tests.csv", "secondary_tests.csv", "exploratory_diffs.csv", "per_seed_metrics.csv",
              "fig_E_by_cell.png", "fig_forest_E.png"):
        assert os.path.exists(os.path.join(out, f)), f
    ps = pd.read_csv(os.path.join(out, "per_seed_metrics.csv"))
    assert set(ps.arm) == {"A0", "A1", "A3", "A5"} and len(pd.read_csv(os.path.join(out, "primary_tests.csv"))) == 12
    # the compared arms are exactly A1, A3, A5: no other arm appears anywhere in the raw data
    raw = pd.concat(pd.read_csv(os.path.join(L.run_out, g, "epochs.csv"), low_memory=False, usecols=["arm"])
                    for g in os.listdir(L.run_out) if os.path.isdir(os.path.join(L.run_out, g)) and g != "analysis")
    assert set(raw.arm) == {"A0", "A1", "A3", "A5"}
    # tampering with a frozen file blocks the evaluation
    p = next(os.path.join(L.frozen, f) for f in os.listdir(L.frozen) if f.startswith("A5_"))
    with open(p, "a") as fh:
        fh.write("\n# edited\n")
    L.run_out = str(tmp_path / "run2")
    with pytest.raises(RuntimeError, match="changed after freezing"):
        fv.evaluate(L, 2)


def test_real_eval_refuses_when_output_exists_or_tree_dirty(tmp_path):
    from experiments.run_v06 import check_eval_allowed
    done = tmp_path / "eval"
    done.mkdir()
    (done / "COMPLETE").write_text("x")
    with pytest.raises(SystemExit, match="exactly once"):
        check_eval_allowed(str(done), {"dirty_files": []})
    with pytest.raises(SystemExit, match="uncommitted"):
        check_eval_allowed(str(tmp_path / "new"), {"dirty_files": [" M tccer/x.py"]})
    assert sys.version_info >= (3, 9)
