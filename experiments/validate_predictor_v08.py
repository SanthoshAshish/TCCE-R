"""E1: does the v0.8 predictive model track counterfactual replay? (docs/PROTOCOL_v0.8.md section 10)

  python -m experiments.validate_predictor_v08 --smoke   # dev seeds 8100-8101, scenario S1 -> results/v0.8/E1_smoke
  python -m experiments.validate_predictor_v08           # dev seeds 8100-8119, 3 scenarios  -> results/v0.8/E1

Design. A passive probe policy (never mutates, so the topology is the unadapted network under the shared failure trace)
visits probe epochs k = 2, 6, ..., 74. At each it takes the controller's feasible shortlist (the same generator, gate and
cand_k as RCPR; index 0 is the lexicographic first choice) and records the predictor's quantities for the null action and
every candidate. After the run, every candidate is *replayed* from the pre-decision snapshot with and without the
mutation on the window k+1..k+d+3 (the window of the counterfactual feedback), giving the realised effect.
No tuning is done here and held-out seeds (9000-9059) are not touched.

Pre-declared criteria (written before the first run; thresholds are this author's proposal, not from a reference):
  C1  pooled Spearman rho between the window-matched predicted error change and the realised change (non-neutral
      candidates) has a 95% seed-cluster bootstrap lower bound > 0.10, and rho > 0 in each scenario;
  C2  the candidate with the lowest predicted J (risk-filtered, as RCPR picks) has a realised error change that is lower
      than the mean over the decision's candidates, by a paired difference whose 95% bootstrap upper bound is < 0.
  Verdict "informative" iff C1 and C2 hold; otherwise "not demonstrated informative" and E2 should not be launched.
"""
import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.stats import spearmanr

from experiments.v08_common import (DEV_SEEDS, SCENARIOS, assert_seeds, git_state, scenario_config, sha256, versions,
                                    write_json)
from tccer.config import replace
from tccer.core.counterfactual import Snapshot
from tccer.core.predict import HazardEstimator, Predictor
from tccer.policies import POLICIES
from tccer.policies.base import Policy
from tccer.sim.engine import simulate

PROBE_EPOCHS = tuple(range(2, 75, 4))        # k + d + 3 <= 79 for d = 2
FEEDBACK_H = 3                               # window length after setup, as the counterfactual feedback (v06.HORIZON)
BOOT, BOOT_SEED = 2000, 20261107
OUT, SMOKE_OUT = "results/v0.8/E1", "results/v0.8/E1_smoke"


class ProbePolicy(Policy):
    """Records predictor outputs for every shortlisted candidate at probe epochs; never mutates."""
    name = "v08_probe"
    INSTANCES = []

    def __init__(self, cfg, pipeline, rng):
        super().__init__(cfg, pipeline, rng)
        self.hz = HazardEstimator(cfg.hz_window, cfg.hz_prior_h, cfg.hz_prior_r, cfg.hz_prior_w)
        self.pred = Predictor(cfg, self.hz)
        self.records = []
        ProbePolicy.INSTANCES.append(self)

    def decide(self, k, obs, state):
        self.hz.update(state)
        if k in PROBE_EPOCHS:
            self._probe(k, state)
        return None

    def _probe(self, k, state):
        pipe, cfg = self.pipeline, self.cfg
        order, tabu = pipe._ranked(state, k, "lexicographic", None)
        feas = []
        for m, _ in order[:30]:
            if pipe.gate.check(state, m, tabu)[0]:
                feas.append(m)
                if len(feas) >= cfg.cand_k:
                    break
        if not feas:
            return
        live, (h, r) = state.live_mask(), self.hz.rates()
        null = self.pred.evaluate(state, None, live)
        snap = Snapshot(k, state.configured.copy(), state.ready_at.copy())
        for rank, m in enumerate(feas):
            parts = self.pred.evaluate(state, m, live)
            cfg_int = state.configured.copy()
            if m.remove is not None:
                cfg_int[m.remove] = False
            self.records.append({"epoch": k, "rank": rank, "n_cand": len(feas), "snap": snap, "m": m, "null": null,
                                 "parts": parts, "E_int": self.pred._E(state, cfg_int, h, r),
                                 "J_null": self.pred.J(null), "J_a": self.pred.J(parts)})


POLICIES[ProbePolicy.name] = ProbePolicy         # registered at import, so spawned workers see it as well


def _disconnected(ctx, snap, mutation, window):
    """Number of epochs in `window` whose live graph (replay topology) is disconnected."""
    configured, ready = snap.configured.copy(), snap.ready_at.copy()
    if mutation is not None:
        if mutation.add is not None:
            configured[mutation.add] = True
            ready[mutation.add] = snap.epoch + 1 + ctx.cfg.link_setup_epochs
        if mutation.remove is not None:
            configured[mutation.remove] = False
    n = 0
    for t in window:
        live = np.flatnonzero(configured & ~ctx.down[t] & (ready <= t))
        g = coo_matrix((np.ones(len(live)), (ctx.eu[live], ctx.ev[live])), shape=(ctx.n, ctx.n))
        n += int(connected_components(g, directed=False)[0] > 1)
    return n


def run_one(args):
    scenario, seed, M = args
    cfg = replace(scenario_config(scenario), mutation_cap=M)
    ProbePolicy.INSTANCES.clear()
    simulate(cfg, seed, ProbePolicy.name, log_rounds=False)
    pol = ProbePolicy.INSTANCES[-1]
    ctx, d, last = pol.ctx, cfg.link_setup_epochs, cfg.epochs - 1
    rows, cache = [], {}
    for rec in pol.records:
        snap, m = rec["snap"], rec["m"]
        window = list(range(snap.epoch + 1, snap.epoch + d + FEEDBACK_H + 1))
        if snap.epoch not in cache:
            cache[snap.epoch] = (ctx.replay(snap, None, window, last).mean(), _disconnected(ctx, snap, None, window))
        e0, dis0 = cache[snap.epoch]
        e1, dis1 = ctx.replay(snap, m, window, last).mean(), _disconnected(ctx, snap, m, window)
        n, a, W = rec["null"], rec["parts"], d + FEEDBACK_H
        rows.append({
            "scenario": scenario, "seed": seed, "epoch": snap.epoch, "rank": rec["rank"], "n_cand": rec["n_cand"],
            "remove": -1 if m.remove is None else m.remove, "add": -1 if m.add is None else m.add,
            "E_null": n["E"], "E_int": rec["E_int"], "E_a": a["E"], "R_null": n["R"], "R_a": a["R"], "C_a": a["C"],
            "S_a": a["S"], "J_null": rec["J_null"], "J_a": rec["J_a"],
            "allowed": bool(a["R"] <= max(cfg.risk_eps, n["R"]) + 1e-12),
            "pred_dE_1": a["E"] - n["E"],                                          # one-epoch predicted change
            "pred_dE_win": (d * rec["E_int"] + FEEDBACK_H * a["E"] - W * n["E"]) / W,   # window-matched prediction
            "pred_dJ": rec["J_a"] - rec["J_null"], "pred_dR": a["R"] - n["R"],
            "real_E_without": e0, "real_dE": e1 - e0, "real_ddisc": dis1 - dis0})
    return rows


# --------------------------------------------------------------------------------------------- analysis
def _rho(x, y):
    if len(x) < 3 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return np.nan
    return float(spearmanr(x, y).correlation)


def _decisions(df):
    """One row per decision: realised effect of (A) the predicted-best allowed candidate, (B) the lexicographic first
    candidate, (C) the mean over candidates, (D) the oracle best; plus the act/defer outcome."""
    out = []
    for key, g in df.groupby(["scenario", "seed", "epoch"]):
        if len(g) < 3:
            continue
        allowed = g[g.allowed]
        if allowed.empty:
            continue
        best = allowed.loc[allowed.J_a.idxmin()]
        out.append({"scenario": key[0], "seed": key[1], "epoch": key[2], "n": len(g),
                    "A_pred_best": best.real_dE, "B_lexi_first": g.loc[g["rank"].idxmin()].real_dE,
                    "C_mean": g.real_dE.mean(), "D_oracle": g.real_dE.min(), "act": bool(best.J_a < best.J_null),
                    "top1_hit": bool(g.loc[g.pred_dE_win.idxmin()].real_dE == g.real_dE.min()), "chance": 1.0 / len(g)})
    return pd.DataFrame(out)


def _boot_units(df, stat, rng, reps=BOOT):
    """Seed-cluster bootstrap of stat(df): resample (scenario, seed) units with replacement."""
    units = df[["scenario", "seed"]].drop_duplicates().to_numpy()
    groups = {tuple(u): g for u, g in df.groupby(["scenario", "seed"])}
    vals = []
    for _ in range(reps):
        pick = units[rng.integers(0, len(units), len(units))]
        v = stat(pd.concat([groups[tuple(u)] for u in pick]))
        if v == v:
            vals.append(v)
    return (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))) if vals else (np.nan, np.nan)


def analyze(df):
    rng = np.random.default_rng(BOOT_SEED)
    nn = df[df.real_dE != 0]                                        # non-neutral candidates
    res = {"n_candidates": int(len(df)), "n_decisions": int(df.groupby(["scenario", "seed", "epoch"]).ngroups),
           "n_units": int(df[["scenario", "seed"]].drop_duplicates().shape[0]),
           "share_neutral": float((df.real_dE == 0).mean())}
    pooled = lambda d: _rho(d.pred_dE_win.to_numpy(), d.real_dE.to_numpy())
    res["spearman_dE_win"] = pooled(nn)
    res["spearman_dE_win_ci"] = _boot_units(nn, pooled, rng)
    res["spearman_dE_1"] = _rho(nn.pred_dE_1.to_numpy(), nn.real_dE.to_numpy())
    res["spearman_dJ_vs_realdE"] = _rho(nn.pred_dJ.to_numpy(), nn.real_dE.to_numpy())
    res["spearman_dR_vs_real_ddisc"] = _rho(df.pred_dR.to_numpy(), df.real_ddisc.to_numpy())
    res["share_disconnection_changed"] = float((df.real_ddisc != 0).mean())
    sa = nn[nn.pred_dE_win != 0]
    res["sign_agreement_dE_win"] = float((np.sign(sa.pred_dE_win) == np.sign(sa.real_dE)).mean()) if len(sa) else np.nan
    res["by_scenario"] = {s: {"n": int(len(g)), "spearman": _rho(g.pred_dE_win.to_numpy(), g.real_dE.to_numpy())}
                          for s, g in nn.groupby("scenario")}
    dec = _decisions(df)
    res["n_decisions_used"] = int(len(dec))
    if len(dec):
        for col in ("A_pred_best", "B_lexi_first", "C_mean", "D_oracle"):
            res[f"mean_{col}"] = float(dec[col].mean())
        res["top1_hit_rate"], res["top1_chance"] = float(dec.top1_hit.mean()), float(dec.chance.mean())
        for name, a, b in (("A_minus_C", "A_pred_best", "C_mean"), ("A_minus_B", "A_pred_best", "B_lexi_first")):
            res[name] = float((dec[a] - dec[b]).mean())
            res[name + "_ci"] = _boot_dec(dec, a, b, rng)
        act = dec[dec.act]
        res["act_share"] = float(dec.act.mean())
        res["act_and_beneficial"] = float((act.A_pred_best < 0).mean()) if len(act) else np.nan
        res["defer_but_beneficial"] = float((dec[~dec.act].A_pred_best < 0).mean()) if (~dec.act).any() else np.nan
    c1 = (res["spearman_dE_win_ci"][0] > 0.10) and all(v["spearman"] > 0 for v in res["by_scenario"].values())
    c2 = len(dec) > 0 and res["A_minus_C_ci"][1] < 0
    res["C1"], res["C2"] = bool(c1), bool(c2)
    res["verdict"] = "informative" if (c1 and c2) else "not demonstrated informative"
    return res, dec


def _boot_dec(dec, a, b, rng, reps=BOOT):
    units = dec[["scenario", "seed"]].drop_duplicates().to_numpy()
    groups = {tuple(u): (g[a] - g[b]).to_numpy() for u, g in dec.groupby(["scenario", "seed"])}
    vals = []
    for _ in range(reps):
        pick = units[rng.integers(0, len(units), len(units))]
        vals.append(np.concatenate([groups[tuple(u)] for u in pick]).mean())
    return (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)))


def write_report(res, out):
    f = lambda x: "n/a" if x is None or x != x else f"{x:.4f}"
    ci = lambda t: f"[{f(t[0])}, {f(t[1])}]"
    lines = ["# E1: predictor validation (development seeds, never held-out)", "",
             f"Candidates {res['n_candidates']} in {res['n_decisions']} decisions, {res['n_units']} (scenario, seed) units; "
             f"share of candidates with zero realised effect (neutral): {f(res['share_neutral'])}.", "",
             "## Does predicted error track the counterfactual replay?", "",
             f"- Spearman, window-matched predicted dE vs realised dE (non-neutral): **{f(res['spearman_dE_win'])}**, 95% seed-cluster bootstrap {ci(res['spearman_dE_win_ci'])}",
             f"- per scenario: " + ", ".join(f"{s}: {f(v['spearman'])} (n={v['n']})" for s, v in res["by_scenario"].items()),
             f"- one-epoch predicted dE vs realised dE: {f(res['spearman_dE_1'])}; predicted dJ vs realised dE: {f(res['spearman_dJ_vs_realdE'])}",
             f"- sign agreement (non-neutral, predicted dE != 0): {f(res['sign_agreement_dE_win'])}",
             f"- risk proxy: Spearman(predicted dR, realised change in disconnected epochs) = {f(res['spearman_dR_vs_real_ddisc'])}; disconnection changed in {f(res['share_disconnection_changed'])} of candidates", "",
             "## Does choosing by predicted J help? (realised dE over the window; lower = better)", ""]
    if res["n_decisions_used"]:
        lines += [f"{res['n_decisions_used']} decisions with >= 3 candidates:", "",
                  "| selection | mean realised dE |", "|---|---|",
                  f"| predicted-best (RCPR rule, risk-filtered) | {f(res['mean_A_pred_best'])} |",
                  f"| lexicographic first (A4/A5 rule) | {f(res['mean_B_lexi_first'])} |",
                  f"| mean over candidates | {f(res['mean_C_mean'])} |",
                  f"| oracle best | {f(res['mean_D_oracle'])} |", "",
                  f"- predicted-best minus candidate mean: {f(res['A_minus_C'])}, 95% CI {ci(res['A_minus_C_ci'])}",
                  f"- predicted-best minus lexicographic first: {f(res['A_minus_B'])}, 95% CI {ci(res['A_minus_B_ci'])}",
                  f"- top-1 agreement with the oracle: {f(res['top1_hit_rate'])} (chance {f(res['top1_chance'])})",
                  f"- RCPR would act in {f(res['act_share'])} of decisions; among them the chosen move was beneficial in {f(res['act_and_beneficial'])}; "
                  f"among deferrals the best move would have been beneficial in {f(res['defer_but_beneficial'])}", ""]
    lines += ["## Pre-declared criteria", "", f"- C1 (rho lower bound > 0.10 and rho > 0 in every scenario): **{res['C1']}**",
              f"- C2 (predicted-best better than candidate mean, CI upper bound < 0): **{res['C2']}**",
              f"- **Verdict: {res['verdict']}**", "",
              "## Limitations", "",
              "- The probe never mutates, so the visited states are those of the unadapted network; states reached by an adapting controller may differ.",
              "- The realised effect is a single deterministic replay on the one realised failure trace and x(0) per epoch, not an expectation.",
              "- Thresholds in C1/C2 are proposals; the full numbers above are reported regardless of the verdict.",
              "- Candidates in one decision share a removed link, so the within-decision comparison is among added links only.",
              "- Development seeds only; this is a diagnostic of the model, not evidence that RCPR beats any baseline."]
    with open(os.path.join(out, "REPORT.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--M", type=int, default=3, help="cap handed to the config (irrelevant to a passive probe)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    seeds = (8100, 8101) if a.smoke else DEV_SEEDS
    assert_seeds(seeds, range(8100, 8120), "E1 predictor validation")
    scenarios = SCENARIOS[:1] if a.smoke else SCENARIOS
    out = SMOKE_OUT if a.smoke else OUT
    if os.path.exists(os.path.join(out, "COMPLETE")):
        raise SystemExit(f"{out} already complete; outputs are never overwritten")
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    tasks = [(s, seed, a.M) for s in scenarios for seed in seeds]
    print(f"E1: {len(tasks)} probe runs on {a.workers} workers -> {out}", flush=True)
    if a.workers <= 1:
        res = [run_one(t) for t in tasks]
    else:
        with ProcessPoolExecutor(max_workers=a.workers) as ex:
            res = list(ex.map(run_one, tasks))
    df = pd.DataFrame([r for rows in res for r in rows])
    df.to_csv(os.path.join(out, "candidates.csv"), index=False)
    summary, dec = analyze(df)
    dec.to_csv(os.path.join(out, "decisions.csv"), index=False)
    with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, default=str)
    write_report(summary, out)
    write_json(os.path.join(out, "run_info.json"), {"seeds": list(seeds), "scenarios": list(scenarios), "smoke": a.smoke,
                                                    "probe_epochs": list(PROBE_EPOCHS), "git": git_state(),
                                                    "versions": versions(), "seconds": round(time.time() - t0, 1),
                                                    "bootstrap": [BOOT, BOOT_SEED],
                                                    "script_sha256": sha256(__file__)})
    with open(os.path.join(out, "COMPLETE"), "w") as fh:
        fh.write(f"{len(df)} candidate rows\n")
    print(open(os.path.join(out, "REPORT.md"), encoding="utf-8").read())


if __name__ == "__main__":
    main()
