# Revision summary (manuscript v0.8)

**Authoritative revised manuscript:** `paper/manuscript_v0.8.md` (also `paper/manuscript_v0.8.docx`), generated from `paper/manuscript_v0.8_template.md` by `paper/tools/build_manuscript_v08.py`. The v0.7 manuscript, template and docx are unchanged in `paper/` and copied to `paper/archive_v0.7/`. Raw E2 and v0.7 outputs were not touched.

## How it was produced
- Every result-dependent number is a placeholder resolved from `revision/analysis/E2/*.csv` (and `results/v0.8/E1/summary.json` for the predictor validation); tables are generated from the same files (`paper/tables_v08/`).
- `paper/tools/check_claims_v08.py` asserts the qualitative claims against those files (54 assertions, all pass), checks that every figure/table caption is referenced and every referenced figure exists, that citations match the reference list, that the recency/count target holds, and lists guarantee/equivalence/superiority wording for review.
- References: 45 cited, 36 (80.0%) from 2022-2026; metadata verified against Crossref by `paper/tools/verify_refs_v08.py`; audit in `revision/literature/LITERATURE_AUDIT_v08.md`.
- Figures: E2 figures copied unchanged from `revision/analysis/E2/figures/`; new schematics (`paper/tools/make_figs_v08.py`): study workflow and B8 procedure; Figure 1 is the v0.7 architecture figure.

## What changed scientifically in the text
- New title and framing: *when* does resilience-aware adaptation help, framework + evaluation, no superiority claim.
- Claims now follow the evidence: B8 < A1 in all six conditions (Holm-significant, beyond the 0.02 margin in three); A7 < B8 in all six point estimates (inconclusive in S2 M6); A7M < B8 in all six; H1 not distinguishable from A7; B2-B4 no gain; B8-B6 and B8-B7 no measurable benefit; B6-B5 consistent with a selector contribution but unexplained against E1; trade-offs against A1 and A7 reported as exploratory; time to consensus censored; S2 M6 calibration limitation and cap-12-vs-M explicit; scope limited (no generalisation, centralised, no sensitivity analysis).
- Method sections now define the debt, normalisation, weights, reset, adaptive threshold, both feedback rules, the safety gate, the predictive objective as implemented (no uncertainty term, no guarantees), the arms (incl. B1-B4 interpretation and H1), calibration with Amendment 1, seed separation and statistics.
- Corrected statements from earlier drafts: A7 beat A5 in 6 (not 5) cells in v0.7; the historical A1 S3 M3 exclusion is noted as not applying to E2.

## Checks performed
- 53 claim assertions pass; all 10 figures and 15 tables resolve; `.docx` exported (10 images, 15 tables).
- The E2 analysis itself was validated before use (4,500 runs, 0 problems) and two headline differences were recomputed independently from raw CSVs.
- Not performed: re-running tests (no code in `tccer/` or `experiments/` changed in this step), visual proofreading of the `.docx`, full-text verification of cited papers.

## Open items
See `revision/UNRESOLVED_REQUIREMENTS.md`: sensitivity analysis, other graph families, larger sizes, other failure laws, imperfect-information experiments, wasted-release metrics, literature claim-support verification, Holm DOI, authorship/journal logistics. Nothing was committed.

## Final pre-submission QC pass (2026-11-04)
Pre-QC copies: `paper/archive_pre_qc/`. Corrections made:
- **References.** Holm (1979) and Wilcoxon (1945) checked by web search/Crossref: Holm has no DOI (none given; bibliographic details from web sources); Wilcoxon's DOI confirmed and its signed-rank attribution rests on secondary sources. Flags in the reference list, the References note and the audit were updated accordingly.
- **Claims attached to the 36 recent references** were narrowed to what their titles state (e.g. "consensus, flocking and distributed-optimisation algorithms", "addresses connectivity preservation, restoration and robustness", power-distribution settings named); the sentence that attributed a design property ("the topology is given") to the event-triggered works was replaced by a statement about our own controller. The counterfactual-literature gap is now described as unverified (brief, non-exhaustive search).
- **Counts preserved:** 45 references, 36 from 2022-2026 (80.0%).
- **Statistics text:** the accumulation comparison (B5 vs B4) now states it is Holm-significant in two conditions (S2 M6, S3 M6) and beyond the margin only in S2 M6; two further assertions (B5-B4, A7 vs B8 counts) added to `paper/tools/check_claims_v08.py` (56 pass).
- **DOCX defects found by rendering the exported file in Word and fixed in the exporter/template:** Greek macros in the displayed objective (alpha, beta ...) were printed as words; subscripts/superscripts were literal underscores and carets; the Markdown parser italicised the text between two "a*" occurrences (renamed a_opt); the reference list was auto-numbered 9-53 instead of 1-45 (continuing the Limitations list), which would have broken every in-text citation (now literal numbers); table header rows did not repeat across pages (now repeat); the 5-panel primary forest figure was illegible at print width (re-laid out in 3 columns from the same CSV data; `paper/figures_v0.8/` only, the analysis outputs are unchanged); ceiling brackets rendered as plain brackets (now ceil(M/2)).
- **Integrity checks:** all 895 decimal numbers in the Markdown also occur in the DOCX; title identical; 10 figures and 15 tables in the DOCX match 10 figure and 10 table captions plus appendix tables; v0.7 manuscript files byte-identical to their archive copies; E2 input hashes unchanged; repository HEAD still e16a208 (only README.md modified, nothing staged or committed).

## Formatting pass against the sample article (2026-11-04)
**Sample used:** `paper/1-s2.0-S2590123026045627-main.pdf` (an Elsevier *Results in Engineering* "Journal Pre-proof" PDF, 39 pages). The file named `...-main_2.pdf` in the request does not exist; this is the only sample PDF in `paper/`. Nothing was copied from its text or science. Pre-change copies: `paper/archive_pre_format/`.

**Conventions measured/observed in the sample and now matched in the exported DOCX** (`paper/tools/export_docx_v08.py`, `paper/manuscript_v0.8_template.md`, `paper/tools/build_manuscript_v08.py`):
- A4 page, Times New Roman 12 pt, 1.5 line spacing (measured 20.7 pt pitch), margins about 2.1 cm, justified body text.
- Highlights page before the title page (bullets); bold 14 pt centred title; centred author block with numbered affiliations and a corresponding-author mark (placeholders only).
- One-paragraph abstract (the structured Purpose/Methods/Results/Conclusion labels were removed, wording unchanged) followed by a bold "Keywords:" line.
- Bold numbered headings "1. Introduction", "3.1. ..."; section titles "Literature Survey" and a Limitations section before the Conclusion.
- Numbered display equations with the number at the right margin (Eq. 1-3, cited in the text).
- Table captions above tables ("Table N text", bold label), rule-only tables (top, header and bottom rules), repeating header rows; figure captions below ("Fig. N. text") and in-text "Fig. N"; Tables 7 and 8 were swapped so numbering follows the order of appearance.
- Unnumbered labelled back matter (Funding, Data availability, ...) after the Conclusion, a numbered reference list "[n] Surname, I., YEAR. Title. Venue, vol(issue), pp. DOI" in order of first citation, and a "Declaration of interests" check-box form at the end (both boxes left unticked).
- Wide tables (Table 1, Table 7) are set on landscape pages; page numbers added in the footer (the sample's page numbers belong to the publisher's proof, so this is our choice).

**Not reproduced (publisher-added in the sample):** cover page, "Journal Pre-proof" banner, watermark, DOI/PII block.

**Validation actually run after the changes:** `paper/tools/check_claims_v08.py` 56 assertions pass (it now also checks the "Fig." / "**Table N**" caption and "[n]" reference conventions); E2 numbers unchanged (all 895 decimal tokens of the Markdown occur in the DOCX; 90 E2 input hashes unchanged); DOCX exported and rendered through Word to `paper/manuscript_v0.8_proof.pdf` (38 pages, 2 landscape). Checked in the render: title/abstract page, heading hierarchy, equations, Table 1/2/7 pages, figure pages, reference list, declaration form (contact sheets of all pages plus zoomed pages); automated checks for empty pages, orphaned headings and leftover markup. Defects found and fixed in this pass: an orphaned heading before a landscape table (text moved ahead of the table), a table caption separated from its header row, justified lines stretched by code-font paths, and a raw summation formula in the prose.

## Guide-for-Authors step (2026-11-04)
See `revision/GUIDE_FOR_AUTHORS_CHECK.md`: the official guide was located but could not be fetched in full (HTTP 403); checks rest on search summaries. Changes: abstract 418 -> 244 words, highlights 5 bullets <= 85 characters plus `paper/submission/highlights_v0.8.docx`, generative-AI declaration retitled, acknowledgements before the references, access date on the one URL-only reference. `check_claims_v08.py`: 56 assertions pass after the changes. Updated DOCX/proof are `paper/manuscript_v0.8_guide_check.docx` / `paper/manuscript_v0.8_guide_check_proof.pdf` because the standard-named DOCX is open in Word.
