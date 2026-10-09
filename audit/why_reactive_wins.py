"""Descriptive: when and in what state each strategy spends its (equal) mutation budget. Held-out v0.4 data."""
import pandas as pd
rows = []
for d in [0, 2, 4, 8]:
    df = pd.read_csv(f"results/v0.4/eval_d{d}/epochs.csv")
    m = df[df.select_outcome == "mutated"]
    for p, g in m.groupby("policy"):
        rows.append(dict(delay=d, policy=p, mutations=len(g), median_epoch=g.epoch.median(),
                         share_in_first_20_epochs=(g.epoch < 20).mean(),
                         share_while_disconnected=(g.components > 1).mean(),
                         share_reconnecting=(g.M_dcomp < 0).mean(),
                         share_released_failed=g.removed_failed_link.astype(bool).mean(),
                         mean_E_at_mutation=g.E_hat.mean()))
print(pd.DataFrame(rows).round(3).to_string(index=False))
