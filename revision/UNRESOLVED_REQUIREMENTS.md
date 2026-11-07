# Unresolved requirements and verification issues (after the manuscript revision)

Status key: **COMPLETE** (evidence exists), **PARTIAL**, **NOT DONE** (no experiment or evidence exists; none was launched in this step). Evidence paths are relative to the repository root.

## A. Requirements from the original 26-item brief

| # | Requirement | Status | Evidence / what is missing |
|---|---|---|---|
| 1 | Literature survey | PARTIAL | `paper/manuscript_v0.8.md` sec. 2 covers the six requested topics; support checked at title/metadata level only (see C) |
| 2 | >= 30 references | COMPLETE (metadata-level) | 45 cited, all with Crossref-confirmed metadata except Holm (1979) (DOI unverified) |
| 3 | >= 80% from 2022-2026 | PARTIAL | 36/45 = 80.0%, exactly at the threshold; any added older reference breaks it; claim support not read in full |
| 4 | Proper citation | PARTIAL | numbered, generated from verified metadata; whether each cited paper supports its sentence is unverified beyond titles |
| 5 | Stronger novelty explanation | COMPLETE | sec. 1 (gap, positioning) and sec. 7: framework and evaluation, ingredients not claimed as novel |
| 6 | Explain TCCE-R vs reactive gap | PARTIAL | B6-B5 (selector) is the associated component; mechanism not established; E1 tension unexplained (sec. 6.9) |
| 7 | Component ablations | COMPLETE (within protocol) | B2-B8 evaluated on held-out seeds; B1-B4 instantaneous interpretation is a flagged design assumption; debt-based B1-B4 not evaluated |
| 8 | Stronger baselines | PARTIAL | A1, A7, A7M, A5, B-chain; no hysteresis/EWMA/learned baselines (decision D9) |
| 9 | Matched-budget comparisons | PARTIAL | caps matched (A7M), counts calibrated on average; realised counts differ (Table 7); equal-count subsets exploratory |
| 10 | Direct comparison with A7 | COMPLETE | Tables 4-5, sec. 6.2-6.4: A7 lower than B8 in all six point estimates |
| 11 | Hybrid | COMPLETE | H1 evaluated; not better than A7; design choices D2-D3 stated |
| 12 | Broader graph families | NOT DONE | ER/BA generators exist and are smoke-tested only; no experiment, no density matching (D10) |
| 13 | Larger graph sizes | NOT DONE | n = 40 and 80 only |
| 14 | Additional failure distributions | NOT DONE | shock option exists, unrun; no sustained-outage model |
| 15 | Sensitivity analysis | NOT DONE | no parameter sensitivity experiment (weights, kappa, thresholds, horizon, costs, delay, failure intensity, margin) |
| 16 | Additional resilience metrics | PARTIAL | disconnection frequency/longest, recovery, worst-case, overhead, adaptation rate computed; wasted releases, detection metrics not; time to consensus censored |
| 17 | Formal objective | PARTIAL | J = alpha E + beta R + gamma C + delta S documented as implemented (sec. 4.5), no U, no guarantees; predictor unvalidated beyond E1 (dev seeds) |
| 18 | Reproducible debt formulation | COMPLETE | sec. 4.1-4.2, Table 2, Appendix B |
| 19 | Statistical rigor | COMPLETE (as specified) | paired Wilcoxon, Holm per family, bootstrap CI, r, 0.02 margin, equivalence only with CI; power limits stated |
| 20 | Missing/excluded runs | COMPLETE | no exclusions in E2 (4,500/4,500); v0.7 exclusion stated as historical; Amendment 1 documented |
| 21 | Pseudocode | COMPLETE | Algorithm 1 (B8) and Figure 2 |
| 22 | Architecture/workflow | PARTIAL | Figure 1 is the v0.7 architecture (B8 changes only described in its caption); Figures 2-3 new |
| 23 | Trade-off plots | COMPLETE | Figures 7-9 (generated from result CSVs) |
| 24 | Reproducibility information | COMPLETE | sec. 9, `revision/REPRODUCIBILITY.md` not yet written as one document |
| 25 | Limitations | COMPLETE | sec. 8 |
| 26 | Abstract/discussion/conclusion | COMPLETE | rewritten from E2 outputs; claims asserted by `paper/tools/check_claims_v08.py` (54 assertions pass) |

Also not done: **imperfect-information robustness** (observation noise/delay) was not evaluated; the options exist but would perturb only the trigger statistics.

## B. Scientific issues left open

1. **B6 - B5 vs E1.** The selector step is negative in five conditions (up to 0.030) while E1 found only 0.0016 headroom over the lexicographic first choice; no analysis separates risk filtering, deferral and closed-loop effects.
2. **Calibration limitation.** B8's threshold in S2, M = 6 is 0.0145 (the trigger acts whenever the cooldown allows); calibration used cap 12 while evaluation uses cap M, so realised counts are below calibration means; B5-B7 and H1 inherit B8's threshold and realise different counts than B8.
3. **A7M comparison.** A7M spends its whole budget; B8 - A7M mixes timing and realised budget.
4. **Design assumptions needing confirmation by the supervisor:** B1-B4 instantaneous vs debt-based; H1 phase-1 handling (no debt reset, no feedback) and F = ceil(M/2).
5. **Predictor.** Absolute predicted error is uncalibrated; risk proxy ignores link setup; constants untuned; no ablation of predictor terms.
6. **Analysis not committed.** `experiments/analyze_v08.py`, `revision/analysis/E2/`, the manuscript and its tools are uncommitted by instruction; raw results are git-ignored (hashes recorded, v0.7 backup outside the repository on the same drive).

## C. Citation-verification issues

1. All 36 recent references: **existence and metadata verified via Crossref; claim support not verified beyond title/metadata**. The manuscript uses them only descriptively, but each sentence in sec. 2 should be checked against the paper.
2. Dong (2026), Estrada (2026), Fu (2026), Binh (2026): 2026 records with incomplete volume/page data in Crossref.
3. Holm (1979): no DOI exists in Crossref (guessed DOIs return 404). Scand. J. Statist. 6(2):65-70 and the JSTOR record (stable/4615733) were confirmed through web sources on 2026-11-04, not from the original; no DOI is given in the manuscript.
4. Wilcoxon (1945): DOI confirmed in Crossref (Biometrics Bulletin 1(6):80). Secondary sources (1992 historical chapter, encyclopaedic pages) state it introduced the signed-rank and rank-sum tests; the original was not re-read.
5. Provenance of the original 34-entry recent list (`paper/references/refs_v2_recent.json`) is undocumented; two entries were added by Crossref search in this step.
6. A brief, non-exhaustive Crossref keyword search (six queries) surfaced no relevant reference on counterfactual evaluation of topology control; this is a limit of the search, not evidence that none exists, and the gap is unverified. Mutation-budget coverage is thin (two references).
7. The "provided sample article" for style guidance was **not found** in the repository or session; the style follows the existing v0.7 manuscript and a generic IMRaD layout.
8. A similarity/plagiarism screen has not been run; the journal's AI-assistance policy has not been checked.

## D. Submission logistics (not scientific)

Author names, affiliations, funding, competing interests, contributions, repository URL/DOI, journal template conversion, and a human proofread of the `.docx` (it was rendered through Word to a 30-page PDF and checked by text extraction plus sampled and contact-sheet page images, not page by page at full resolution; wide tables use 6.5-7.5 pt text).

## E. Format conformance (sample article) - what is and is not established
**Matched to the sample article (observed from the sample PDF):** see "Formatting pass" in `revision/REVISION_SUMMARY.md`.

**Official requirements (partially verified, 2026-11-04):** the official Guide for Authors was located (https://www.sciencedirect.com/journal/results-in-engineering/publish/guide-for-authors, also reachable from https://www.elsevier.com/journals/results-in-engineering/2590-1230/guide-for-authors) but its full text could not be retrieved (HTTP 403); requirements were taken from web-search summaries of those pages. Result and the per-item checklist: `revision/GUIDE_FOR_AUTHORS_CHECK.md`. Corrected: abstract (418 -> 244 words, limit 250), highlights (5 bullets <= 85 characters plus a separate file), generative-AI declaration section, acknowledgements placement, access date for the one URL-only reference. The DOCX still must **not** be described as compliant with an official template, because many items are NOT VERIFIABLE until the authors read the live guide.

**Cannot be determined from a published article and need the Guide for Authors / editor:** length and word limits; highlight count and character limits (the six highlights written here are not checked against any limit); keyword count; whether a graphical abstract, CRediT statement, generative-AI declaration wording or declaration-of-interests form is mandatory and in what form; required file types, figure resolution and font embedding; whether tables/figures must be inline or separate; reference style requirements (numbered list was copied from the sample); line numbering; title-page/anonymisation rules; appendix placement (the sample has no appendix; ours follows the reference list).

**Still needing author input (placeholders, nothing invented):** author names and affiliations, corresponding author, funding, competing-interest selection (both boxes unticked), CRediT roles, acknowledgements, repository URL/DOI.

**Formatting limitations of the generated DOCX:** wide tables use 8.5-9.5 pt text; two tables are on landscape pages (the sample has none); Fig. 6 and Fig. 9 have small internal text at print width; Table 6 uses `*`/`**` significance markers that some Markdown viewers italicise; page numbers are our addition; the DOCX was proofread through a Word-rendered PDF with contact sheets and zoomed pages, not page by page at full resolution.

**Remaining submission blockers (updated):** author/affiliation/funding/interest/CRediT details; official Guide-for-Authors check (limits, highlights, declarations); Holm DOI and Wilcoxon attribution; human verification of the 36 recent references beyond titles; repository URL/DOI; commit of the analysis, scripts and manuscript; similarity screen; the scientific items in sections A-C that no experiment has addressed (sensitivity analysis, other graph families, larger sizes, other failure laws, imperfect-information tests).

**Update after the Guide-for-Authors step (2026-11-04):**
- Still NOT VERIFIABLE from what could be retrieved: figure resolution numbers, keyword count/style, graphical abstract, cover letter, title-page file, line numbers, equation/heading numbering, supplementary-material rules, file formats, and whether a competing-interests form, CRediT statement and the exact data-statement wording are mandatory for this journal.
- Author input still required: author names/affiliations/corresponding author, funding, competing-interests selection, CRediT roles, acknowledgements, generative-AI tool/version and responsibility wording, repository URL/DOI.
- **File blocker:** `paper/manuscript_v0.8.docx` is open in Word and locked; the updated files are `paper/manuscript_v0.8_guide_check.docx` and `paper/manuscript_v0.8_guide_check_proof.pdf` and must be copied over the standard names once Word is closed.

**Synchronisation check (2026-11-04):** `paper/manuscript_v0.8.docx` is still locked by an open Word window (owner file `~$nuscript_v0.8.docx` present), so the standard names were NOT updated. Backups of the standard files: `paper/archive_pre_sync_20261104/`. Latest verified files: `paper/manuscript_v0.8_guide_check.docx` and `paper/manuscript_v0.8_guide_check_proof.pdf` (244-word abstract, 5 highlights, 56 claims assertions pass).

## Final submission metadata still required from the authors (2026-11-07; nothing below was invented)
Placeholders in `paper/manuscript_v0.8.md` / template (search for "TO BE COMPLETED"): author names (2 slots), affiliations (2), corresponding author name and e-mail,
funding statement, competing-interests statement and the two unticked boxes of the Declaration of interests form, CRediT author contributions, acknowledgements,
repository URL/DOI (data availability), public code link, and confirmation of the generative-AI declaration (exact tool/version, review-and-responsibility sentence, current journal wording).
Other open items: the "Draft note" line under the author block must be removed before submission; Holm (1979) has no DOI (JSTOR URL, accessed date given) and is not machine-verified;
the 36 references from 2022-2026 are verified for existence/metadata only (claim support not checked); publisher-side checks that could not be done (Guide for Authors returned HTTP 403): figure resolution numbers, keyword rules, graphical abstract, cover letter, title-page file.
Scientific scope not done in Revision 2 (disclosed in Section 6.11 and Limitations): calibrated uncertainty-aware prediction, delayed credit assignment, rewire/defer/reserve optimisation, long-horizon selector, theory, ER/BA/WS and larger graphs, other failure laws, sensitivity, ledger ablations, scalability.
