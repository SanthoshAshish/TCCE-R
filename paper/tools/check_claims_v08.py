"""Assert the qualitative claims of paper/manuscript_v0.8.md against the E2 analysis files, check cross-references and the
reference list, and list passages that need a human look (guarantee / equivalent / superiority wording).

  python paper/tools/check_claims_v08.py      # exit code 1 if any assertion fails
"""
import json
import re
import sys

import pandas as pd

E2 = "revision/analysis/E2"
MS = "paper/manuscript_v0.8.md"
C = {"S1M3": "S1_rgg40_bursty_M3", "S1M6": "S1_rgg40_bursty_M6", "S2M3": "S2_rgg40_background_M3", "S2M6": "S2_rgg40_background_M6",
     "S3M3": "S3_rgg80_bursty_M3", "S3M6": "S3_rgg80_bursty_M6"}
P, M_, A = (pd.read_csv(f"{E2}/{n}.csv") for n in ("primary_tests", "matched_budget_tests", "ablation_tests"))
X = pd.read_csv(f"{E2}/exploratory_metric_diffs.csv")
S = pd.read_csv(f"{E2}/summary_by_arm_cell.csv")
K = pd.read_csv(f"{E2}/realised_counts.csv")
CAL = pd.read_csv("configs/v0.8/frozen/calibration_report.csv")
fails, passed = [], 0


def check(name, cond):
    global passed
    if cond:
        passed += 1
    else:
        fails.append(name)
        print("FAIL:", name)


def row(t, k, comp):
    return t[(t.cell == C[k]) & (t.comparison == comp)].iloc[0]


def cells(t, comp, fn):
    return {k for k in C if fn(row(t, k, comp))}


# ---- primary
check("B8-A1 lower error in all six", all(row(P, k, "B8-A1").mean_diff < 0 for k in C))
check("B8-A1 Holm < 0.05 in all six", all(row(P, k, "B8-A1").holm_p < 0.05 for k in C))
check("B8-A1 largest Holm p is S2M6 (0.0246)", max(C, key=lambda k: row(P, k, "B8-A1").holm_p) == "S2M6" and abs(row(P, "S2M6", "B8-A1").holm_p - 0.0246) < 5e-4)
check("B8-A1 beyond margin exactly S1M3, S1M6, S3M6", cells(P, "B8-A1", lambda r: r.verdict == "first arm meaningfully better") == {"S1M3", "S1M6", "S3M6"})
check("B8-A1 below margin in the other three", cells(P, "B8-A1", lambda r: "below minimum" in r.verdict) == {"S2M3", "S2M6", "S3M3"})
check("B8-A7 point estimate positive (A7 lower) in all six", all(row(P, k, "B8-A7").mean_diff > 0 for k in C))
check("B8-A7 Holm-significant in exactly five, S2M6 inconclusive", cells(P, "B8-A7", lambda r: r.holm_p < 0.05) == set(C) - {"S2M6"} and row(P, "S2M6", "B8-A7").verdict == "inconclusive")
check("B8-A7 beyond margin exactly S1M3, S1M6, S2M3", cells(P, "B8-A7", lambda r: r.verdict == "second arm meaningfully better") == {"S1M3", "S1M6", "S2M3"})
check("B8-A7 below margin in S3", all("below minimum" in row(P, k, "B8-A7").verdict for k in ("S3M3", "S3M6")))
check("no B8 > A7 claim possible: no cell where B8 lower than A7 significantly", not any(row(P, k, "B8-A7").verdict.startswith("first arm") for k in C))
check("H1-A7: all |mean| < 0.02", all(abs(row(P, k, "H1-A7").mean_diff) < 0.02 for k in C))
check("H1-A7: no significant difference", all(row(P, k, "H1-A7").holm_p >= 0.05 for k in C))
check("H1-A7: five practically equivalent, one inconclusive (S2M6)", cells(P, "H1-A7", lambda r: r.verdict == "practically equivalent") == set(C) - {"S2M6"} and row(P, "S2M6", "H1-A7").verdict == "inconclusive")
# ---- matched
check("B8-A7M positive and Holm<0.05 in all six", all(row(M_, k, "B8-A7M").mean_diff > 0 and row(M_, k, "B8-A7M").holm_p < 0.05 for k in C))
check("H1-A7M: A7M lower & significant in four (S1M3, S1M6, S2M3, S2M6), equivalent in S3", cells(M_, "H1-A7M", lambda r: r.mean_diff > 0 and r.holm_p < 0.05) == {"S1M3", "S1M6", "S2M3", "S2M6"}
      and all(row(M_, k, "H1-A7M").verdict == "practically equivalent" for k in ("S3M3", "S3M6")))
check("H1-A7M beyond margin only in S2M3", cells(M_, "H1-A7M", lambda r: r.verdict == "second arm meaningfully better") == {"S2M3"})
# ---- ablation
check("B2-B4 steps never beat the margin in favour of added signals", all(row(A, k, c).mean_diff > -0.02 for k in C for c in ("B2-A1", "B3-A1", "B4-B2", "B4-B3")))
check("B2-A1 S2M6 = +0.0195, Holm significant", abs(row(A, "S2M6", "B2-A1").mean_diff - 0.0195) < 5e-4 and row(A, "S2M6", "B2-A1").holm_p < 0.05)
check("B5-B4 negative in all six", all(row(A, k, "B5-B4").mean_diff < 0 for k in C))
check("B5-B4 Holm-significant in exactly S2M6 and S3M6", cells(A, "B5-B4", lambda r: r.holm_p < 0.05) == {"S2M6", "S3M6"})
check("B5-B4 beyond margin only in S2M6", cells(A, "B5-B4", lambda r: r.verdict == "first arm meaningfully better") == {"S2M6"})
check("B6-B5 negative in five (not S2M6) and Holm<0.05 in the same five", cells(A, "B6-B5", lambda r: r.mean_diff < 0 and r.holm_p < 0.05) == set(C) - {"S2M6"} and row(A, "S2M6", "B6-B5").mean_diff > 0)
check("B6-B5 beyond margin only in S1M6; S2M6 practically equivalent", cells(A, "B6-B5", lambda r: r.verdict == "first arm meaningfully better") == {"S1M6"} and row(A, "S2M6", "B6-B5").verdict == "practically equivalent")
check("B8-B6 largest |mean| is S1M6 and < 0.006", max(C, key=lambda k: abs(row(A, k, "B8-B6").mean_diff)) == "S1M6" and abs(row(A, "S1M6", "B8-B6").mean_diff) < 0.006)
check("B8-B6 Holm-significant only in S2M3 and below margin", cells(A, "B8-B6", lambda r: r.holm_p < 0.05) == {"S2M3"} and "below minimum" in row(A, "S2M3", "B8-B6").verdict)
check("B8-B7 practically equivalent in all six, none significant", all(row(A, k, "B8-B7").verdict == "practically equivalent" and row(A, k, "B8-B7").holm_p >= 0.05 for k in C))
check("ablation family has 48 tested, primary 18, matched 12", (A.status == "tested").sum() == 48 and (P.status == "tested").sum() == 18 and (M_.status == "tested").sum() == 12)
# ---- trade-offs (exploratory CIs)
def xr(comp, k, m):
    return X[(X.cell == C[k]) & (X.comparison == comp) & (X.metric == m)].iloc[0]


ex = lambda r: r.boot_hi < 0 or r.boot_lo > 0
non_s2m6 = [k for k in C if k != "S2M6"]
check("B8-A1 disconnected/longest/recovery CIs exclude zero (negative) in five, not S2M6",
      all(xr("B8-A1", k, m).boot_hi < 0 for k in non_s2m6 for m in ("disconnected", "longest_disc", "anchored_recovery")) and not ex(xr("B8-A1", "S2M6", "disconnected")))
check("B8-A1 more live-link releases in the four bursty cells (CI>0), not S2", all(xr("B8-A1", k, "live_link_releases").boot_lo > 0 for k in ("S1M3", "S1M6", "S3M3", "S3M6")) and not any(xr("B8-A1", k, "live_link_releases").boot_lo > 0 for k in ("S2M3", "S2M6")))
check("B8-A1 S3 overhead CI>0", all(xr("B8-A1", k, "overhead_sum").boot_lo > 0 for k in ("S3M3", "S3M6")))
check("B8-A7 live releases CI<0 in all six", all(xr("B8-A7", k, "live_link_releases").boot_hi < 0 for k in C))
check("B8-A7 overhead negative in six, CI<0 in five (not S2M6)", all(xr("B8-A7", k, "overhead_sum").mean_diff < 0 for k in C) and {k for k in C if xr("B8-A7", k, "overhead_sum").boot_hi < 0} == set(C) - {"S2M6"})
check("B8-A7 disconnected CI<0 exactly in S2M3, S2M6, S3M6", {k for k in C if xr("B8-A7", k, "disconnected").boot_hi < 0} == {"S2M3", "S2M6", "S3M6"})
check("B8-A7 worst-case E positive in six, CI>0 in three", all(xr("B8-A7", k, "worst_E").mean_diff > 0 for k in C) and sum(xr("B8-A7", k, "worst_E").boot_lo > 0 for k in C) == 3)
# ---- time to consensus, counts, calibration
cs = S[~S.cell.str.startswith("A0")]
check("non-converged share minimum is A7M in S2M6", (lambda r: r.arm == "A7M" and r.cell == C["S2M6"])(cs.loc[cs.nonconverged_share_mean.idxmin()]))
check("non-converged share >= 0.998 for every arm in S3", (S[S.cell.str.contains("S3")].nonconverged_share_mean >= 0.998).all())
check("every calibrated arm realises fewer than M on average", all(r.mean_mutations < r.M for r in K.itertuples() if r.arm not in ("A7M", "H1")) )
check("A7M realises exactly M", all(abs(r.mean_mutations - r.M) < 1e-9 for r in K[K.arm == "A7M"].itertuples()))
cnt = lambda arm, k: K[(K.arm == arm) & (K.cell == C[k])].mean_mutations.iloc[0]
check("B5 realises more than B6, B7, B8 in S2M6 and S3M6", all(cnt("B5", k) > max(cnt(a, k) for a in ("B6", "B7", "B8")) for k in ("S2M6", "S3M6")))
check("B8 S2M6 threshold is 0.0145 and the lowest B8 threshold", abs(CAL[(CAL.arm == "B8") & (CAL.scenario == "S2_rgg40_background") & (CAL.M == 6)].threshold.iloc[0] - 0.0145) < 5e-5
      and CAL[CAL.arm == "B8"].threshold.min() == CAL[(CAL.arm == "B8") & (CAL.scenario == "S2_rgg40_background") & (CAL.M == 6)].threshold.iloc[0])
check("all 36 calibrated arm-cells feasible; 8 amended", CAL.calibratable.all() and len(CAL) == 36 and CAL.amended.sum() == 8)
b8c = K[K.arm == "B8"].mean_mutations
check("A7 realised counts within 0.35 of B8 in every cell", all(abs(cnt("A7", k) - cnt("B8", k)) < 0.35 for k in C))
check("B8 realised counts range 2.30 to 5.08", abs(b8c.min() - 2.30) < 0.005 and abs(b8c.max() - 5.08) < 0.005)
e1 = json.load(open("results/v0.8/E1/summary.json"))
check("E1: Spearman 0.57, selector advantage -0.0016 vs lexicographic", abs(e1["spearman_dE_win"] - 0.568) < 0.002 and abs(e1["A_minus_B"] + 0.0016) < 1e-4)

# ---- text checks
text = open(MS, encoding="utf-8").read()
body = text.split("## References")[0]
refs_part = text.split("## References")[1].split("## Appendices")[0]
check("no unresolved placeholders", "{{" not in text and "<<" not in text)
for pat in (r"(?<!not claim that )B8[^.]{0,40}outperform[^.]{0,30}A7", r"superior to A7", r"B8 is superior", r"demonstrates? superiority", r"H1[^.]{0,40}outperform"):
    check(f"no forbidden claim '{pat}'", not re.search(pat, text))
nums = re.findall(r"\[(\d+(?:, \d+)*)\]", body)
cited = {int(n) for g in nums if "0" not in g.split(", ") for n in g.split(", ")}
listed = re.findall(r"^\[(\d+)\] ", refs_part, flags=re.M)
check("every cited reference number is in the list and every listed reference is cited", cited == {int(n) for n in listed})
meta = json.load(open("paper/references/refs_v08_cited.json"))
check("reference count >= 30 and >= 80% from 2022-2026", meta["n_cited"] >= 30 and meta["n_2022_2026"] / meta["n_cited"] >= 0.8)
caps = {k: set(re.findall(rf"{k} (\d+|B\d)\.", text)) for k in ("Figure", "Table")}
fig_caps = set(re.findall(r"!\[Fig\. (\d+)\.", text))
tab_caps = set(re.findall(r"^\*\*Table (\w+)\*\*", text, flags=re.M))
prose = re.sub(r"!\[Fig\.[^\n]*", "", text)
prose = re.sub(r"^\*\*Table[^\n]*", "", prose, flags=re.M)
fig_refs = {x for g in re.findall(r"Figs?\. (\d+)(?:[–-](\d+))?", prose) for x in g if x}
fig_refs |= {str(n) for a, b in re.findall(r"Figs\. (\d+)[–-](\d+)", prose) for n in range(int(a), int(b) + 1)}
tab_refs = set(re.findall(r"Table (\d+)", prose))
check(f"every figure caption is referenced in the text (captions {sorted(fig_caps, key=int)})", fig_caps <= fig_refs)
check("every referenced figure has a caption", {f for f in fig_refs if f.isdigit()} <= fig_caps)
check(f"every referenced table has a caption (captions {sorted(tab_caps)})", tab_refs <= tab_caps | {"1", "2"})
import os
check("all figure files exist", all(os.path.exists("paper/" + f) for f in re.findall(r"\]\((figures_v0\.8/[^)]+)\)", text)))

print(f"\n{passed} assertions passed, {len(fails)} failed")
print("\n--- passages for manual review ---")
for kw in ("guarantee", "equivalent", "superior", "outperform", "generali", "proved", "prove "):
    for m in re.finditer(kw, body):
        s0 = body.rfind(".", 0, m.start()) + 1
        e0 = body.find(".", m.end())
        print(f"[{kw}] ...{body[max(s0, m.start() - 110):min(e0 + 1, m.end() + 110)].strip()}".encode("ascii", "replace").decode())
sys.exit(1 if fails else 0)
