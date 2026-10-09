"""Run an experiment: config x seeds x policies -> CSV logs.

Fairness rules:
  * every policy sees the same graph, failure trace and x(0) for a given seed (common random numbers);
  * every policy uses the same candidate set, safety gate and edge budget;
  * mutation budget matching: TCCE-R runs first; each mutating baseline gets mutation_cap = M_tccer
    for that seed, and periodic/random use period = epochs // (M_tccer + 1) (same number of mutations,
    spread uniformly).

Usage:  python -m experiments.run --config configs/default.yaml --seeds 20 --out results/default
"""
import argparse
import os
import time

import pandas as pd

from tccer.config import load_config, replace, save_config
from tccer.sim.engine import simulate

DEFAULT_POLICIES = ["tccer", "tccer_fixed", "static", "random", "periodic", "reactive"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--seed-start", type=int, default=0)
    ap.add_argument("--policies", nargs="+", default=DEFAULT_POLICIES)
    ap.add_argument("--out", default="results/default")
    ap.add_argument("--no-rounds", action="store_true", help="skip per-round CSV (smaller output)")
    args = ap.parse_args()

    cfg = load_config(args.config)
    os.makedirs(args.out, exist_ok=True)
    save_config(cfg, os.path.join(args.out, "config_used.yaml"))

    epochs, rounds = [], []
    t0 = time.time()
    for seed in range(args.seed_start, args.seed_start + args.seeds):
        e, r = simulate(cfg, seed, "tccer", log_rounds=not args.no_rounds)
        epochs += e
        rounds += r
        M = e[-1]["n_mutations"]
        matched = replace(cfg, mutation_cap=M, period=max(1, cfg.epochs // (M + 1)) if M else cfg.epochs + 1)
        for p in args.policies:
            if p == "tccer":
                continue
            e, r = simulate(cfg if p == "tccer_fixed" else matched, seed, p, log_rounds=not args.no_rounds)
            epochs += e
            rounds += r
        print(f"seed {seed}: TCCE-R mutations = {M}  ({time.time() - t0:.1f}s)")

    pd.DataFrame(epochs).to_csv(os.path.join(args.out, "epochs.csv"), index=False)
    if rounds:
        pd.DataFrame(rounds).to_csv(os.path.join(args.out, "rounds.csv"), index=False)
    print(f"wrote {args.out}/epochs.csv" + ("" if args.no_rounds else f" and {args.out}/rounds.csv"))


if __name__ == "__main__":
    main()
