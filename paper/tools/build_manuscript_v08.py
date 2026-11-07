"""Assemble paper/manuscript_v0.8.md from paper/manuscript_v0.8_template.md, the E2 analysis CSV/JSON files and the verified
reference metadata. Every number that depends on results is read from revision/analysis/E2 (or results/v0.8/E1) by a
placeholder; nothing result-dependent is typed by hand.

  python paper/tools/build_manuscript_v08.py

Placeholders (all resolved or the build fails):
  {{T:name}}                              generated table
  {{v:table|cell|comp|field|fmt}}         one value; table in primary|matched|ablation|continuity, cell like S1M3
  {{ci:table|cell|comp}}                  "mean diff [lo, hi]" (4 decimals)
  {{p:table|cell|comp}}                   Holm-adjusted p (continuity: unadjusted Wilcoxon p, labelled in text)
  {{rng:table|comp|field|fmt}}            "min to max" over the six cells
  {{cnt:table|comp|substring}}            number of cells whose verdict contains the substring
  {{s:arm|cell|field|fmt}}                value from summary_by_arm_cell.csv
  {{c:arm|cell|field|fmt}}                value from realised_counts.csv
  {{x:comp|cell|metric}}                  "mean [lo, hi]" (3 decimals) of an exploratory metric difference
  {{xr:comp|metric|fmt}}                  "min to max" of the exploratory mean difference over the six cells
  {{e1:key|fmt}}, {{e1ci:key|fmt}}, {{e1w:mean|median|pos}}   E1 predictor validation (development seeds)
  {{R:slug;slug}}                         numbered citation(s); the reference list is generated from the cited slugs
fmt: d0..d4 = fixed decimals (unicode minus), s = string.
"""
import html
import json
import os
import re
import unicodedata

import numpy as np
import pandas as pd

E2 = "revision/analysis/E2"
E1 = "results/v0.8/E1"
FROZEN = "configs/v0.8/frozen"
TEMPLATE = "paper/manuscript_v0.8_template.md"
OUT = "paper/manuscript_v0.8.md"
TABLE_DIR = "paper/tables_v08"
MINUS = "−"
CELL = {"S1M3": "S1_rgg40_bursty_M3", "S1M6": "S1_rgg40_bursty_M6", "S2M3": "S2_rgg40_background_M3",
        "S2M6": "S2_rgg40_background_M6", "S3M3": "S3_rgg80_bursty_M3", "S3M6": "S3_rgg80_bursty_M6"}
CELLS = list(CELL.values())
SHORT = {v: k for k, v in CELL.items()}
CELL_NAME = {"S1M3": "S1, M = 3", "S1M6": "S1, M = 6", "S2M3": "S2, M = 3", "S2M6": "S2, M = 6", "S3M3": "S3, M = 3", "S3M6": "S3, M = 6"}
VERDICT = {"first arm meaningfully better": "first lower, beyond margin",
           "first arm better, below minimum meaningful effect": "first lower, below margin",
           "second arm meaningfully better": "second lower, beyond margin",
           "second arm better, below minimum meaningful effect": "second lower, below margin",
           "practically equivalent": "practically equivalent", "inconclusive": "inconclusive"}
ARM_ORDER = ["A1", "A5", "A7", "A7M", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "H1"]

PRIM = pd.read_csv(f"{E2}/primary_tests.csv")
MATCH = pd.read_csv(f"{E2}/matched_budget_tests.csv")
ABL = pd.read_csv(f"{E2}/ablation_tests.csv")
CONT = pd.read_csv(f"{E2}/exploratory_continuity_tests.csv")
SUMM = pd.read_csv(f"{E2}/summary_by_arm_cell.csv")
COUNTS = pd.read_csv(f"{E2}/realised_counts.csv")
XD = pd.read_csv(f"{E2}/exploratory_metric_diffs.csv")
EQC = pd.read_csv(f"{E2}/equal_count_tests.csv")
TABLES = {"primary": PRIM, "matched": MATCH, "ablation": ABL, "continuity": CONT}
CAL = pd.read_csv(f"{FROZEN}/calibration_report.csv")


def fmt(x, f):
    if f.isdigit():
        f = "d" + f
    if f == "s":
        return str(x)
    if f.startswith("p"):
        return f"{100 * x:.{int(f[1:])}f}%"
    if f == "n0":
        return f"{int(round(x)):,}"
    if f.startswith("a"):
        return fmt(abs(x), "d" + f[1:])
    n = int(f[1:])
    s = f"{abs(x):.{n}f}"
    return (MINUS if x < 0 and float(s) != 0 else "") + s


def fp(p):
    return "< 0.0001" if p < 1e-4 else f"{p:.4f}"


def rowof(tab, cell, comp):
    t = TABLES[tab]
    r = t[(t.cell == CELL[cell]) & (t.comparison == comp)]
    if len(r) != 1:
        raise KeyError(f"{tab}|{cell}|{comp}: {len(r)} rows")
    return r.iloc[0]


# ------------------------------------------------------------------------------------------------ tables
def vlab(v):
    return VERDICT.get(v, v)


def test_table(df, comps=None):
    rows = []
    for _, r in df[df.status == "tested"].iterrows():
        if comps and r.comparison not in comps:
            continue
        rows.append(f"| {CELL_NAME[SHORT[r.cell]]} | {r.comparison.replace('-', ' − ')} | {fmt(r.mean_diff, 'd4')} [{fmt(r.boot_lo, 'd4')}, {fmt(r.boot_hi, 'd4')}] | "
                    f"{fmt(r.rank_biserial, 'd2')} | {fp(r.holm_p)} | {vlab(r.verdict)} |")
    return ("| Cell | Comparison (first − second) | ΔE [95% bootstrap CI] | r (rank-biserial) | Holm p | Assessment (margin 0.02) |\n"
            "|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n")


def table_means():
    rows = []
    for arm in ARM_ORDER:
        cells = []
        for c in CELLS:
            r = SUMM[(SUMM.cell == c) & (SUMM.arm == arm)].iloc[0]
            cells.append(f"{r.E_mean:.3f} [{r.E_ci_lo:.3f}, {r.E_ci_hi:.3f}]")
        rows.append(f"| {arm} | " + " | ".join(cells) + " |")
    st = []
    for s in ("S1_rgg40_bursty", "S2_rgg40_background", "S3_rgg80_bursty"):
        st.append(SUMM[(SUMM.cell == f"A0_{s}")].E_mean.iloc[0])
    rows.append(f"| A0 Static | {st[0]:.3f} | {st[0]:.3f} | {st[1]:.3f} | {st[1]:.3f} | {st[2]:.3f} | {st[2]:.3f} |")
    return ("| Arm | " + " | ".join(CELL_NAME[k] for k in CELL) + " |\n|---|" + "---|" * 6 + "\n" + "\n".join(rows) + "\n")


def table_ablation_compact():
    steps = [("B2", "A1"), ("B3", "A1"), ("B4", "B2"), ("B4", "B3"), ("B5", "B4"), ("B6", "B5"), ("B8", "B6"), ("B8", "B7")]
    what = {"B2-A1": "adding C (bridge fraction) to E, instantaneous", "B3-A1": "adding V (volatility) to E, instantaneous",
            "B4-B2": "adding V to E + C", "B4-B3": "adding C to E + V", "B5-B4": "accumulation (debt) instead of instantaneous trigger; B5 uses B8's Θ₀",
            "B6-B5": "predictive selector instead of lexicographic first choice (same Θ₀)", "B8-B6": "adaptive Θ with counterfactual feedback (same Θ₀)",
            "B8-B7": "counterfactual instead of legacy before/after feedback (same Θ₀)"}
    rows = []
    for x, y in steps:
        comp = f"{x}-{y}"
        cells = []
        for k in CELL:
            r = rowof("ablation", k, comp)
            mark = "" if r.holm_p >= 0.05 else ("**" if abs(r.mean_diff) >= 0.02 else "*")
            cells.append(f"{fmt(r.mean_diff, 'd4')}{mark}")
        rows.append(f"| {comp.replace('-', ' − ')} | {what[comp]} | " + " | ".join(cells) + " |")
    return ("| Step (first − second) | Component changed | " + " | ".join(CELL_NAME[k] for k in CELL) + " |\n|---|---|" + "---|" * 6 + "\n" + "\n".join(rows) + "\n")


def table_counts():
    rows = []
    for arm in ARM_ORDER:
        cells = []
        for c in CELLS:
            r = COUNTS[(COUNTS.cell == c) & (COUNTS.arm == arm)].iloc[0]
            cells.append(f"{r.mean_mutations:.2f}")
        rows.append(f"| {arm} | " + " | ".join(cells) + " |")
    return ("| Arm | " + " | ".join(CELL_NAME[k] for k in CELL) + " |\n|---|" + "---|" * 6 + "\n" + "\n".join(rows) + "\n")


def table_tradeoff():
    mets = [("disconnected", "Δ disconnected fraction", 3), ("longest_disc", "Δ longest disconnection (epochs)", 2),
            ("anchored_recovery", "Δ anchored recovery (epochs)", 2), ("worst_E", "Δ worst-case E", 3),
            ("live_link_releases", "Δ live-link releases", 2), ("overhead_sum", "Δ pending link-epochs + live releases", 2)]
    rows = []
    for comp in ("B8-A1", "B8-A7", "H1-A7"):
        for k in CELL:
            cells = []
            for m, _, nd in mets:
                r = XD[(XD.cell == CELL[k]) & (XD.comparison == comp) & (XD.metric == m)].iloc[0]
                cells.append(f"{fmt(r.mean_diff, f'd{nd}')} [{fmt(r.boot_lo, f'd{nd}')}, {fmt(r.boot_hi, f'd{nd}')}]")
            rows.append(f"| {comp.replace('-', ' − ')} | {CELL_NAME[k]} | " + " | ".join(cells) + " |")
    return ("| Comparison | Cell | " + " | ".join(n for _, n, _ in mets) + " |\n|---|---|" + "---|" * len(mets) + "\n" + "\n".join(rows) + "\n")


def table_nonconv():
    rows = []
    for arm in ("A1", "A5", "A7", "A7M", "B8", "H1"):
        cells = [f"{SUMM[(SUMM.cell == c) & (SUMM.arm == arm)].nonconverged_share_mean.iloc[0]:.3f}" for c in CELLS]
        rows.append(f"| {arm} | " + " | ".join(cells) + " |")
    st = [SUMM[SUMM.cell == f"A0_{s}"].nonconverged_share_mean.iloc[0] for s in ("S1_rgg40_bursty", "S2_rgg40_background", "S3_rgg80_bursty")]
    rows.append(f"| A0 Static | {st[0]:.3f} | {st[0]:.3f} | {st[1]:.3f} | {st[1]:.3f} | {st[2]:.3f} | {st[2]:.3f} |")
    return ("| Arm | " + " | ".join(CELL_NAME[k] for k in CELL) + " |\n|---|" + "---|" * 6 + "\n" + "\n".join(rows) + "\n")


def table_calibration():
    rows = []
    for _, r in CAL[CAL.arm.isin(["A1", "A5", "B2", "B3", "B4", "B8"])].sort_values(["scenario", "M", "arm"]).iterrows():
        am = "amended" if r.amended else ""
        p1 = "" if not r.amended else f"{r.pass1_threshold:.4f} ({r.pass1_mean_count:.2f}{', excluded' if not r.pass1_calibratable else ''})"
        rows.append(f"| {r.scenario.split('_')[0]} | {r.M} | {r.arm} | {r.threshold:.4f} | {r.calibration_mean_count:.2f} | {am} | {p1} |")
    return ("| Scenario | M | Arm | Final threshold (h or Θ₀) | Calibration mean count | Amendment 1 | Pass 1 threshold (count) |\n|---|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n")


def table_equal_count():
    rows = []
    for _, r in EQC.iterrows():
        if pd.isna(r.mean_diff):
            continue
        rows.append(f"| {CELL_NAME[SHORT[r.cell]]} | {r.comparison.replace('-', ' − ')} | {int(r.n_equal_count_seeds)} | {fmt(r.mean_diff, 'd4')} [{fmt(r.boot_lo, 'd4')}, {fmt(r.boot_hi, 'd4')}] |")
    return "| Cell | Comparison | Seeds with equal realised counts | ΔE [95% bootstrap CI] (exploratory) |\n|---|---|---|---|\n" + "\n".join(rows) + "\n"


def table_continuity():
    rows = []
    for _, r in CONT[CONT.status == "tested"].iterrows():
        rows.append(f"| {CELL_NAME[SHORT[r.cell]]} | {r.comparison.replace('-', ' − ')} | {fmt(r.mean_diff, 'd4')} [{fmt(r.boot_lo, 'd4')}, {fmt(r.boot_hi, 'd4')}] | {fp(r.wilcoxon_p)} |")
    return "| Cell | Comparison | ΔE [95% bootstrap CI] | Wilcoxon p (unadjusted, exploratory) |\n|---|---|---|---|\n" + "\n".join(rows) + "\n"


def table_hist():
    return open("paper/tables/table3_primary.md", encoding="utf-8").read()


NL = chr(10)


def md(header, rows):
    return ("| " + " | ".join(header) + " |" + NL + "|" + "---|" * len(header) + NL +
            NL.join("| " + " | ".join(r) + " |" for r in rows) + NL)


def table_design():
    rows = [("A0 Static", "static", "never", "-", "-", "-", "no (reference)"),
            ("A1 Reactive (B1)", "v06_reactive", "E_k > h", "lexicographic first choice", "fixed h", "-", "yes (h)"),
            ("A5 TCCE-R (v0.7)", "v06_tccer", "D_k > Θ (E, C, V debt)", "lexicographic first choice", "adaptive Θ", "counterfactual", "yes (Θ₀)"),
            ("A7 Front-loaded", "v06_front", "epochs 0, 2, 4, … until the intended count", "lexicographic first choice", "-", "-", "count PMF from calibrated arms"),
            ("A7M Front-loaded, exact M", "v06_front (no PMF)", "epochs 0, 2, …, 2(M−1)", "lexicographic first choice", "-", "-", "no"),
            ("B2 E + C", "v08_b2", "(0.5E + 0.3C)/0.8 > h", "lexicographic first choice", "fixed h", "-", "yes (h)"),
            ("B3 E + V", "v08_b3", "(0.5E + 0.2V)/0.7 > h", "lexicographic first choice", "fixed h", "-", "yes (h)"),
            ("B4 E + C + V", "v08_b4", "0.5E + 0.3C + 0.2V > h", "lexicographic first choice", "fixed h", "-", "yes (h)"),
            ("B5 debt (= A4)", "v06_cusum_ecv", "D_k > Θ (E, C, V debt)", "lexicographic first choice", "fixed Θ = B8's Θ₀", "-", "no (inherits B8)"),
            ("B6 debt + predictive", "v08_rcpr_fixed", "D_k > Θ", "predictive, risk-filtered (Sec. 4.5)", "fixed Θ = B8's Θ₀", "-", "no (inherits B8)"),
            ("B7 B8, legacy feedback", "v08_rcpr_legacy", "D_k > Θ", "predictive", "adaptive Θ", "legacy before/after", "no (inherits B8)"),
            ("B8 predictive controller", "v08_rcpr", "D_k > Θ", "predictive", "adaptive Θ", "counterfactual", "yes (Θ₀)"),
            ("H1 Hybrid-FrontRisk", "v08_hybrid", "phase 1: A7-style, F = ceil(M/2); then as B8", "lexicographic (phase 1), predictive (phase 2)", "adaptive Θ (phase 2)", "counterfactual (phase 2)", "no (inherits B8)")]
    return md(["Arm", "Code policy", "Attempt when", "Candidate selection", "Threshold", "Feedback", "Calibrated"], rows)


def table_params():
    rows = [("S1", "RGG, n = 40", "initial radius 0.22, range 0.32", "p_fail 0.005, p_repair 0.10", "bursts: rate 0.10, radius 0.15, 2–6 epochs"),
            ("S2", "RGG, n = 40", "as S1", "p_fail 0.01, p_repair 0.10", "none"),
            ("S3", "RGG, n = 80", "radii × √(40/80): 0.1556, 0.2263", "as S1", "as S1"),
            ("all", "80 epochs × 60 rounds", "ε = 0.01; p_transient 0.05", "setup delay d = 2; cooldown 2", "strict edge budget; budgets M ∈ {3, 6}")]
    t1 = md(["Scenario", "Graph", "Radii", "Background failures", "Bursts / budget"], rows)
    prm = [("stress weights (E, C, V)", "0.5, 0.3, 0.2 (A3: 1, 0, 0)"), ("debt reference κ", "median stress over connected Static epochs, calibration seeds"),
           ("Θ adaptation", "×0.9 on success, ×1.25 on failure, bounds [Θ₀/4, 4Θ₀]"), ("feedback window", "d + 3 = 5 epochs"),
           ("safety gate", "cooldown 5, degree ≤ 10, λ₂ floor R_min = 0.05, components non-increasing"),
           ("predictor", "H = 5, hazard window 10 (priors 0.02, 0.10, weight 20), shortlist ≤ 10 of the first 30"),
           ("objective", "(α, β, γ, δ) = (1, 0.5, 0.05, 1); costs 0.25 / +0.75; risk tolerance 0.20")]
    t2 = md(["Parameter", "Value (implemented defaults; not tuned)"], prm)
    return t1 + NL + t2



def build_tables():
    return {"design": table_design(), "params": table_params(), "primary": test_table(PRIM), "matched": test_table(MATCH), "ablation_full": test_table(ABL), "ablation": table_ablation_compact(),
            "means": table_means(), "counts": table_counts(), "tradeoff": table_tradeoff(), "nonconv": table_nonconv(),
            "calibration": table_calibration(), "equal_count": table_equal_count(), "continuity": table_continuity(), "hist": table_hist()}


# ------------------------------------------------------------------------------------------------ E1
def e1_vals():
    s = json.load(open(f"{E1}/summary.json", encoding="utf-8"))
    c = pd.read_csv(f"{E1}/candidates.csv")
    w = []
    from scipy.stats import spearmanr
    for _, g in c.groupby(["scenario", "seed", "epoch"]):
        if len(g) >= 5 and g.pred_dE_win.nunique() > 1 and g.real_dE.nunique() > 1:
            w.append(spearmanr(g.pred_dE_win, g.real_dE).correlation)
    w = np.array(w)
    s["_w"] = {"mean": float(w.mean()), "median": float(np.median(w)), "pos": float((w > 0).mean()), "n": int(len(w))}
    return s


E1S = e1_vals()


# ------------------------------------------------------------------------------------------------ references
def asc(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def initials(given):
    return "".join(p[0] + "." for p in re.split(r"[ \-]+", given.strip()) if p)


def fmt_authors(names):
    """'Shuo Zhang', 'Jinhai Liu' -> 'Zhang, S., Liu, J.' (sample style: 'A, B and C'); at most eight authors, then 'et al.'"""
    out = []
    for n in names[:8]:
        parts = n.split()
        out.append(f"{parts[-1]}, {initials(' '.join(parts[:-1]))}" if len(parts) > 1 else n)
    if len(names) > 8:
        return ", ".join(out) + " et al."
    return out[0] if len(out) == 1 else ", ".join(out[:-1]) + " and " + out[-1]


def old_to_sample_style(txt):
    """'Xiao L, Boyd S (2004) Title. Venue 53(1):65-78. URL' -> 'Xiao, L. and Boyd, S., 2004. Title. Venue, 53(1), pp.65-78. URL'"""
    txt = txt.replace("  [DOI NOT VERIFIED]", "")
    m = re.match(r"^(?P<auth>.+?) \((?P<year>\d{4})\) (?P<rest>.*)$", txt)
    if not m:
        return txt
    names = []
    for a in m.group("auth").split(", "):
        if " " in a:
            fam, ini = a.rsplit(" ", 1)
            names.append(f"{fam}, " + "".join(c + "." for c in ini))
        else:
            names.append(a)
    auth = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    rest = re.sub(r"(\d+)(\(\d+(?:-\d+)?\))?:(\d[\d\u2013\-]*)", lambda k: f"{k.group(1)}{k.group(2) or ''}, pp.{k.group(3)}", m.group("rest"))
    rest = re.sub(r"(\w) (\d+(?:\(\d+(?:-\d+)?\))?, pp\.)", lambda k: k.group(1) + ", " + k.group(2), rest)   # comma between venue and volume
    return f"{auth}, {m.group('year')}. {rest}"


def load_refs():
    refs = {}
    for e in json.load(open("paper/references/refs_v08_recent_final.json", encoding="utf-8")):
        vol = f"{e['volume']}" if e.get("volume") else ""
        iss = f"({e['issue']})" if e.get("issue") else ""
        pg = f":{e['pages']}" if e.get("pages") else ""
        vp = ", ".join(x for x in (f"{vol}{iss}" if vol else "", f"pp.{e['pages']}" if e.get("pages") and "-" in str(e["pages"]) else (f"p.{e['pages']}" if e.get("pages") else "")) if x)
        refs[e["slug"]] = {"year": e["crossref_year"], "text": f"{fmt_authors(e['authors'])}, {e['crossref_year']}. {html.unescape(e['crossref_title'])}. "
                           f"{html.unescape(e['crossref_venue'])}{', ' + vp if vp else ''}. https://doi.org/{e['doi']}", "kind": "recent"}
    old = {}
    for line in open("paper/references/references_formatted_authoryear.md", encoding="utf-8"):
        m = re.match(r"- \[(\w+)\] (.*)", line.strip())
        if m:
            old[m.group(1)] = m.group(2)
    for k in ("XiaoBoyd2004", "Fiedler1973", "OlfatiSaberMurray2004", "GhoshBoyd2006", "Page1954", "Wilcoxon1945", "Holm1979", "Efron1979", "Lakens2017"):
        txt = old[k]
        year = int(re.search(r"\((\d{4})\)", txt).group(1))
        flag = {"Holm1979": " [no DOI found; URL accessed 4 November 2026; see note above]", "Wilcoxon1945": " [see note above]"}.get(k, "")
        refs[k] = {"year": year, "text": old_to_sample_style(txt) + flag, "kind": "foundational"}
    return refs


REFS = load_refs()
CITED = []


def cite(m):
    slugs = [s.strip() for s in m.group(1).split(";")]
    nums = []
    for s in slugs:
        if s not in REFS:
            raise KeyError(f"unknown reference slug {s}")
        if s not in CITED:
            CITED.append(s)
        nums.append(CITED.index(s) + 1)
    return "[" + ", ".join(map(str, sorted(nums))) + "]"


# ------------------------------------------------------------------------------------------------ placeholders
def resolve(m):
    kind, _, arg = m.group(1).partition(":")
    a = arg.split("|")
    if kind == "T":
        return TABLE_TEXT[arg]
    if kind == "F":                       # Revision 2: generated section/appendix text (paper/tools/make_r2_section.py)
        return open(f"{TABLE_DIR}/{arg}.md", encoding="utf-8").read().strip()
    if kind == "v":
        return fmt(float(rowof(a[0], a[1], a[2])[a[3]]), a[4])
    if kind == "ci":
        r = rowof(a[0], a[1], a[2])
        return f"{fmt(r.mean_diff, 'd4')} [{fmt(r.boot_lo, 'd4')}, {fmt(r.boot_hi, 'd4')}]"
    if kind == "p":
        r = rowof(a[0], a[1], a[2])
        return fp(r.wilcoxon_p if a[0] == "continuity" else r.holm_p)
    if kind == "rng":
        t = TABLES[a[0]]
        v = t[(t.comparison == a[1]) & (t.status == "tested")][a[2]].astype(float)
        return f"{fmt(v.min(), a[3])} to {fmt(v.max(), a[3])}"
    if kind == "cnt":
        t = TABLES[a[0]]
        return str(int(t[(t.comparison == a[1]) & t.verdict.fillna("").str.contains(a[2], regex=False)].shape[0]))
    if kind == "s":
        r = SUMM[(SUMM.cell == CELL.get(a[1], a[1])) & (SUMM.arm == a[0])].iloc[0]
        return fmt(float(r[a[2]]), a[3])
    if kind == "c":
        r = COUNTS[(COUNTS.cell == CELL[a[1]]) & (COUNTS.arm == a[0])].iloc[0]
        return fmt(float(r[a[2]]), a[3])
    if kind == "crng":
        v = COUNTS[COUNTS.arm == a[0]][a[1]].astype(float)
        return f"{fmt(v.min(), a[2])} to {fmt(v.max(), a[2])}"
    if kind == "x":
        r = XD[(XD.cell == CELL[a[1]]) & (XD.comparison == a[0]) & (XD.metric == a[2])].iloc[0]
        nd = 3
        return f"{fmt(r.mean_diff, f'd{nd}')} [{fmt(r.boot_lo, f'd{nd}')}, {fmt(r.boot_hi, f'd{nd}')}]"
    if kind == "xr":
        v = XD[(XD.comparison == a[0]) & (XD.metric == a[1])].mean_diff.astype(float)
        return f"{fmt(v.min(), a[2])} to {fmt(v.max(), a[2])}"
    if kind == "CAL":
        r = CAL[(CAL.arm == a[0]) & (CAL.scenario == CELL[a[1]].rsplit("_M", 1)[0]) & (CAL.M == int(a[1][-1]))].iloc[0]
        return f"Θ₀ = {r.threshold:.4f}"
    if kind == "e1":
        return fmt(float(E1S[a[0]]), a[1])
    if kind == "e1ci":
        v = E1S[a[0]]
        return f"[{fmt(float(v[0]), a[1])}, {fmt(float(v[1]), a[1])}]"
    if kind == "e1w":
        return fmt(E1S["_w"][a[0]], a[1] if len(a) > 1 else "d2")
    raise KeyError(kind)


TABLE_TEXT = build_tables()


def main():
    os.makedirs(TABLE_DIR, exist_ok=True)
    for k, v in TABLE_TEXT.items():
        open(f"{TABLE_DIR}/{k}.md", "w", encoding="utf-8").write(v)
    s = open(TEMPLATE, encoding="utf-8").read()
    s = re.sub(r"\{\{R:([^}]*)\}\}", cite, s)                      # citations first, numbered by first appearance
    s = re.sub(r"\{\{([^{}]*)\}\}", resolve, s)
    left = re.findall(r"\{\{[^}]*\}\}", s)
    if left:
        raise SystemExit(f"unresolved placeholders: {left[:5]}")
    refs_md = "\n".join(f"[{i}] {REFS[k]['text']}" for i, k in enumerate(CITED, 1))
    s = s.replace("<<REFERENCES>>", refs_md)
    n_recent = sum(1 for k in CITED if REFS[k]["year"] >= 2022)
    s = s.replace("<<REFSTATS>>", f"{len(CITED)} references are cited; {n_recent} ({100 * n_recent / len(CITED):.0f}%) are from 2022-2026")
    open(OUT, "w", encoding="utf-8").write(s)
    json.dump({"cited": CITED, "n_cited": len(CITED), "n_2022_2026": n_recent}, open("paper/references/refs_v08_cited.json", "w"), indent=1)
    print(f"wrote {OUT}: {len(s.split())} words, {len(CITED)} references ({n_recent} from 2022-2026)")


if __name__ == "__main__":
    main()
