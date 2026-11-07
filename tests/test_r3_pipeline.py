"""R3 pipeline tests: frozen tier configs, seed blocks, policy resolution, and the pre-declared verdict/Holm logic of analyze_r3."""
import os

import numpy as np
import pandas as pd
import pytest

from experiments.analyze_r3 import families, run_family, verdict
from experiments.run_r3 import R2A, R3, RANGE, SEEDS, SMOKE_SEEDS, VARIANTS, policy_of, tier_cells, write_configs
from experiments.v08_common import verify_manifest
from tccer.config import load_config
from tccer.policies import POLICIES


def test_frozen_tier_b_and_c_configs_verify_and_exist():
    verify_manifest(os.path.join(R3, "MANIFEST.sha256"))
    verify_manifest(os.path.join(R2A, "MANIFEST.sha256"))
    for tier in "ABC":
        for cell, files, M in tier_cells(tier):
            for arm, path in files.items():
                assert os.path.exists(path), path
                cfg = load_config(path)
                if arm != "A0":
                    assert cfg.mutation_cap == M, (cell, arm)


def test_tier_cell_structure_and_documented_exclusions():
    a = {c: f for c, f, _ in tier_cells("A")}
    assert "B8" not in a["S2_M6"] and "B8" in a["S2_M3"] and "cocro" not in a["S3_M3"] and "cocro" in a["S1_M6"]
    b = tier_cells("B")
    assert len(b) == 8 and all(set(f) >= {"A0", "A7M", "cocro_m"} and "B8" not in f for _, f, _ in b)
    c = {c: f for c, f, _ in tier_cells("C")}
    assert len(c) == 8 and all("cocro" in f and "cocro_m" in f for f in c.values())
    assert load_config(c["regime_M6"]["A7M"]).failure_model == "extended" and load_config(c["regime_M6"]["A7M"]).regime_epoch == 40


def test_seed_blocks_are_disjoint_from_each_other_and_from_every_earlier_range():
    earlier = set(range(0, 7060)) | set(range(8000, 8600)) | set(range(9000, 9300))      # all ranges used before R3 (incl. R2's 9100-9159, 9200-9259)
    assert not set(SEEDS["A"]) & set(SEEDS["B"]) and set(SEEDS["B"]) == set(SEEDS["C"])    # tiers B and C reuse one block on different environments
    for t, s in SEEDS.items():
        assert not set(s) & earlier and set(s) == set(RANGE[t])
    assert not set(SMOKE_SEEDS) & set(SEEDS["A"]) and len(SEEDS["A"]) == 150 and len(SEEDS["B"]) == 100


def test_every_arm_resolves_to_a_registered_policy():
    for tier in "ABC":
        for _, files, _ in tier_cells(tier):
            for arm in files:
                assert policy_of(arm) in POLICIES, arm
    assert set(VARIANTS) >= {"cocro_m", "cocro_mfg", "cocro", "cocro_r"}


def test_write_configs_refuses_to_overwrite_frozen_configs():
    with pytest.raises(SystemExit):
        write_configs()


def test_verdict_rules_follow_the_declared_definition():
    assert verdict(0.001, -0.03, -0.04, -0.02, 0.01).startswith("first arm better (meaningful)")
    assert verdict(0.001, 0.005, 0.003, 0.007, 0.01) == "second arm better, below margin"
    assert verdict(0.4, 0.002, -0.004, 0.008, 0.01) == "practically equivalent"
    assert verdict(0.4, 0.02, -0.03, 0.07, 0.01) == "inconclusive"
    assert verdict(0.4, 0.004, -0.004, 0.012, 0.01) == "inconclusive"                      # CI not inside the margin


def test_holm_is_applied_within_each_family_only():
    rng = np.random.default_rng(0)
    rows = []
    for cell in ("c1", "c2"):
        for arm, shift in (("x", -0.05), ("y", 0.0), ("z", 0.0)):
            for s in range(30):
                rows.append(dict(cell=cell, arm=arm, seed=s, E=0.4 + shift + rng.normal(0, 0.03)))
    ps = pd.DataFrame(rows)
    t = run_family(ps, [("x", "z"), ("y", "z")], ["c1", "c2"], "fam")
    assert (t.status == "tested").sum() == 4 and t.tests_in_family.iloc[0] == 4
    assert (t.holm_p >= t.wilcoxon_p - 1e-12).all()                                        # Holm never lowers a p-value
    assert t[t.comparison == "x-z"].holm_p.max() < 0.01 and t[t.comparison == "y-z"].holm_p.min() > 0.05
    ex = run_family(ps, [("x", "missing")], ["c1"], "fam2")
    assert ex.status.iloc[0] == "excluded (arm missing)"


def test_predeclared_families_match_the_protocol():
    ca = tier_cells("A")
    fam = {n: (p, c) for n, p, c, _ in families("A", ca)}
    assert fam["primary"][0] == [("cocro_m", "A7M"), ("cocro_m", "B8"), ("cocro_m", "C1")]
    cc = {n: (p, c) for n, p, c, _ in families("C", tier_cells("C"))}
    h2 = [k for k in cc if k.startswith("H2")][0]
    assert cc[h2][0] == [("cocro", "cocro_m")] and all(c.startswith(("regime", "mixed")) for c in cc[h2][1]) and len(cc[h2][1]) == 4
