"""Assert that the numeric and directional claims of paper/manuscript_v3.md hold in the committed analysis files.   python paper/tools/check_claims_v3.py"""
import json
import re
import sys

import pandas as pd

A = "revision/analysis/R3/A"
tests = pd.read_csv(f"{A}/tests.csv")
tt = tests[tests.status == "tested"]
summ = pd.read_csv(f"{A}/summary_by_arm_cell.csv")
eff = pd.read_csv(f"{A}/efficiency.csv")
val = json.load(open(f"{A}/validation.json"))
V = json.load(open("paper/tables_v3/v3_values.json", encoding="utf-8"))
md = open("paper/manuscript_v3.md", encoding="utf-8").read()
P = tt[tt.family == "primary"]
AB = tt[tt.family == "ablation"]
R = tt[tt.family.str.startswith("rollout")]
fails, n = [], 0


def chk(name, cond):
    global n
    n += 1
    if not cond:
        fails.append(name)


def S(arm, cell, col):
    r = summ[(summ.arm == arm) & (summ.cell == cell)][col]
    return float(r.iloc[0]) if len(r) else float("nan")


CELLS = ["S1_M3", "S1_M6", "S2_M3", "S2_M6", "S3_M3", "S3_M6"]
chk("17 primary tests", len(P) == 17)
chk("COCRO-M lower in all primary", bool((P.mean_diff < 0).all()))
chk("all primary Holm < 0.05", bool((P.holm_p < 0.05).all()))
chk("max primary Holm p <= 0.0005 as stated", float(P.holm_p.max()) <= 0.00055)
chk("15 exceed 0.01", int(P["verdict_0.01"].str.contains("meaningful").sum()) == 15)
chk("10 exceed 0.02", int(P["verdict_0.02"].str.contains("meaningful").sum()) == 10)
chk("A7M: 6 tests, 4 beyond 0.01, 2 beyond 0.02", (lambda q: len(q) == 6 and q["verdict_0.01"].str.contains("meaningful").sum() == 4 and q["verdict_0.02"].str.contains("meaningful").sum() == 2)(P[P.comparison == "cocro_m-A7M"]))
chk("S3 vs A7M below 0.01 margin", all(abs(float(P[(P.comparison == "cocro_m-A7M") & (P.cell == c)].mean_diff.iloc[0])) < 0.01 for c in ("S3_M3", "S3_M6")))
chk("B8 only 5 cells (absent in S2_M6)", sorted(P[P.comparison == "cocro_m-B8"].cell) == [c for c in CELLS if c != "S2_M6"])
chk("COCRO-M lowest E among non-exploratory arms in every cell", all(S("cocro_m", c, "E_mean") <= min(S(a, c, "E_mean") for a in ("A0", "A1", "A7", "A7M", "B8", "C1") if not pd.isna(S(a, c, "E_mean"))) for c in CELLS if True))
chk("COCRO-M realises exactly M mutations", all(abs(S("cocro_m", c, "mutations") - int(c[-1])) < 1e-9 for c in CELLS))
chk("B8/C1 leave budget unspent in some cell", any(S(a, c, "mutations") < int(c[-1]) - 0.01 for a in ("B8", "C1") for c in CELLS if not pd.isna(S(a, c, "mutations"))))
chk("per-mutation efficiency highest for COCRO-M in all cells", V["eff_cocro_m_best"] == "yes")
chk("ablation k1 worse in 6/6 significant", V["abl_k1_worse"] == "6")
chk("ablation lap worse in 6/6 significant", V["abl_lap_worse"] == "6")
chk("plug and nb1 no significant effect", V["abl_plug_sig"] == "0" and V["abl_nb1_sig"] == "0")
chk("mfg no significant effect", V["abl_mfg_sig"] == "0")
chk("s1 significant only in 2 and worse", V["abl_s1_sig"] == "2" and V["abl_s1_worse"] == "2")
chk("rollout: 4 exploratory tests, 1 Holm-significant", len(R) == 4 and int((R.holm_p < 0.05).sum()) == 1)
chk("rollout never worse than COCRO-M in point estimate", bool((R.mean_diff < 0).all()))
chk("rollout cost ratio 10-14x", V["roll_cost_ratio"] == "10 to 14")
chk("B8 lower disconnected share than COCRO-M in all 5 cells", all(S("B8", c, "disconnected") < S("cocro_m", c, "disconnected") for c in CELLS if c != "S2_M6"))
chk("B8 shorter recovery than COCRO-M in all 5 cells", all(S("B8", c, "recovery") < S("cocro_m", c, "recovery") for c in CELLS if c != "S2_M6"))
chk("COCRO-M lower disconnected share than A7M in 6/6", all(S("cocro_m", c, "disconnected") < S("A7M", c, "disconnected") for c in CELLS))
chk("C1 or rollout better than COCRO-M on disconnection in some cell", any(S(a, c, "disconnected") < S("cocro_m", c, "disconnected") for a in ("C1", "cocro") for c in CELLS if not pd.isna(S(a, c, "disconnected"))))
chk("COCRO-M decision time below B8 and C1 where run", all(S("cocro_m", c, "ms_per_epoch") < S(a, c, "ms_per_epoch") for a in ("B8", "C1") for c in CELLS if not pd.isna(S(a, c, "ms_per_epoch"))))
chk("12150 runs, 150 seeds, commit", val["n_runs"] == 12150 and V["seeds_tier_A"] == "150" and V["commit_tier_A"] == "d4238a1")
step2 = json.load(open("revision/analysis/R3/step2/rules.json"))
chk("no Step-2 rule adopted; final cocro_m", not any(v["adopt"] for v in step2["rules"].values()) and step2["decision"]["final"] == "cocro_m")
# text checks
abstract = re.search(r"## Abstract\n\n(.*?)\n\n\*\*Keywords", md, re.S).group(1)
chk("abstract <= 250 words", len(abstract.split()) <= 250)
hl = [l[2:] for l in md.split("\n")[:12] if l.startswith("- ")]
chk("five highlights <= 85 characters", len(hl) == 5 and all(len(h) <= 85 for h in hl))
chk("Tier B/C not-run statement present", "not run" in md and "Tier B was started and then stopped" in md)
chk("no unresolved placeholders", "{{" not in md and "<<" not in md)
chk("author list as in V2", "Y. Santhosh Ashish, E. Kishan Kumar, P. Navyambika, Vinay Gupta" in md)
chk("no superiority overclaim words", not re.search(r"\b(outperforms? all|state-of-the-art|significantly better than all|best-in-class|optimal)\b", md.replace("optimal-stopping", "").replace("exact optimum", "").replace("optimum", "")))
print(f"{n} assertions, {len(fails)} failed")
for f in fails:
    print("FAIL:", f)
sys.exit(1 if fails else 0)
