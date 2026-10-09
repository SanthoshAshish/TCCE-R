"""Calibration step 2 (static policy, tuning seeds 100-119 only). Same target as step 1."""
import pandas as pd
from tccer.config import load_config, replace
from tccer.sim.engine import simulate

base = replace(load_config("configs/v0.3_binding_base.yaml"), degree_basis="configured",
               feedback_after_setup=True, failed_link_value="if_up")
rows = []
for pf, rate, rad in [(0.01, 0.05, 0.15), (0.005, 0.0, 0.15), (0.005, 0.1, 0.12), (0.005, 0.1, 0.15), (0.005, 0.15, 0.12)]:
    df = pd.concat([pd.DataFrame(simulate(replace(base, p_fail=pf, burst_rate=rate, burst_radius=rad), s, "static",
                                          log_rounds=False)[0]) for s in range(100, 120)])
    rows.append(dict(p_fail=pf, burst_rate=rate, burst_radius=rad, disconnected=(df.components > 1).mean(),
                     E=df.E_hat.mean(), links_down=df.n_down_potential.mean(), burst_down=df.n_burst_down.mean(),
                     V=df.V.mean(), V_p90=df.V.quantile(.9)))
print(pd.DataFrame(rows).round(3).to_string(index=False))
