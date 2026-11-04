"""Assert the manuscript's headline numeric claims against the frozen analysis CSVs. Run: python paper/tools/check_claims.py"""
import pandas as pd
A = "results/v0.7/eval/analysis"
p = pd.read_csv(f"{A}/primary_tests.csv"); t = p[p.status == "tested"]
s = pd.read_csv(f"{A}/secondary_tests.csv"); ts = s[s.status == "tested"]
ok = []
def chk(name, cond): ok.append((name, bool(cond))); print(("PASS " if cond else "FAIL ") + name)
a57 = t[t.comparison == "A5-A7"]; a51 = t[t.comparison == "A5-A1"]
chk("primary tested = 11 of 12", len(t) == 11 and len(p) == 12)
chk("secondary tested = 38 of 42", len(ts) == 38 and len(s) == 42)
chk("A5-A7: 6 conditions, all dE>0.02 (A7 lower)", len(a57) == 6 and (a57.mean_diff > 0.02).all())
chk("A5-A7 range 0.0244..0.0756", abs(a57.mean_diff.min() - 0.0244) < 5e-5 and abs(a57.mean_diff.max() - 0.0756) < 5e-5)
chk("A5-A7 Holm p <= 0.0031 (rounded)", a57.holm_p.max() < 0.00315)
chk("A5-A7 CI lower bound below 0.02 in exactly 2 conditions", (a57.boot_lo < 0.02).sum() == 2)
chk("A5-A1: 5 evaluable, 4 practically equivalent", len(a51) == 5 and a51.verdict.str.startswith("practically equivalent").sum() == 4)
x = a51[a51.cell == "S2_rgg40_background_M3"]
chk("A5-A1 S2 M3: +0.0105, p 0.033, below margin", len(x) == 1 and abs(x.mean_diff.iloc[0] - 0.0105) < 5e-5 and abs(x.holm_p.iloc[0] - 0.033) < 5e-4)
for c, n in (("A5-A4", 6), ("A3-A1", 5), ("A7-A1", 5)):
    chk(f"{c} evaluable={n}", (ts.comparison == c).sum() == n)
chk("A5-A4 all practically equivalent", ts[ts.comparison == "A5-A4"].verdict.str.startswith("practically equivalent").all())
chk("A7-A1 all A7 meaningfully better", ts[ts.comparison == "A7-A1"].verdict.str.startswith("first arm meaningfully").all())
fb = pd.read_csv(f"{A}/feedback_quality.csv")
chk("feedback success 72.7..84.9%", abs(fb.fb_success.min() - .727) < 5e-4 and abs(fb.fb_success.max() - .849) < 5e-4)
print("ALL PASS" if all(v for _, v in ok) else "SOME FAILED")
