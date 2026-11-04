# Results in Engineering — Guide for Authors check (2026-11-04)

## Official source and how far it could be read
- Official pages located (Elsevier / ScienceDirect), **accessed 2026-11-04**:
  - https://www.elsevier.com/journals/results-in-engineering/2590-1230/guide-for-authors (redirects, HTTP 301, to the ScienceDirect page below)
  - https://www.sciencedirect.com/science/journal/25901230/publish/guide-for-authors
  - https://www.sciencedirect.com/journal/results-in-engineering/publish/guide-for-authors
- **The full text could not be retrieved:** direct fetches (WebFetch and curl) returned HTTP 403 and an empty ScienceDirect shell. What follows rests on **web-search summaries of those official pages** (not verbatim quotations). Items the summaries attributed to *other* Elsevier journals' guides are marked "sister-journal" and are **not verified for Results in Engineering**. Everything marked NOT VERIFIABLE needs the authors to read the live guide (and the submission system's checklist).
- The sample article was not used as a source of requirements.

## Checklist (M = stated as a requirement, R = recommended/encouraged; status after the changes made in this step)
| # | Requirement | M/R | Status | Evidence / location |
|---|---|---|---|---|
| 1 | Abstract: concise, factual, <= 250 words; purpose, principal results, major conclusions | M | **PASS (was FAIL)** | Was 418 words; now 244 (counted on the built Markdown, `## Abstract`, `paper/manuscript_v0.8.md`). Condensed, claims, numbers (placeholders) and the "not a superiority claim" statement kept |
| 2 | Highlights: 3-5 bullets, each <= 85 characters incl. spaces; separate editable file with "highlights" in its name | R ("encouraged") | **PASS (was FAIL)** | Was 6 bullets, 3 over 85 characters; now 5 bullets of 62-82 characters. Separate file: `paper/submission/highlights_v0.8.docx`. The Highlights page is also kept at the front of the manuscript (as in the sample); remove it if the submission system rejects duplicates |
| 3 | Generative-AI use declared at submission; suggested section title "Declaration of generative AI and AI-assisted technologies in the manuscript preparation process", template "During the preparation of this work the author(s) used [TOOL] in order to [REASON]"; disclose AI-generated images in captions; AI cannot be an author | M | **PARTIAL** | Section added with that title and the template wording (back matter before References). Tool/version, the review-and-responsibility sentence and current wording are placeholders for the authors. Figures are script-generated, no AI-image tool; AI is not listed as an author |
| 4 | Acknowledgements: separate section directly before the reference list | M (per summary) | **PASS (was misplaced)** | "Acknowledgements: [TO BE COMPLETED]" is now the last back-matter item before References. Content is an author placeholder |
| 5 | Word submission is single-column (double column only for LaTeX) | M | PASS | `paper/manuscript_v0.8_guide_check.docx` is single column |
| 6 | Tables as editable text, not images | M | PASS | All tables are native Word tables (16 in the DOCX; the algorithm box is a one-cell table) |
| 7 | Every table, image and supplementary file cited in the text | M | PASS | `check_claims_v08.py` figure/table caption-reference assertions pass; no supplementary files are submitted |
| 8 | Manuscript divided into clearly defined sections with headings | M | PASS | Numbered sections 1-10, back matter, references, appendices |
| 9 | References: no strict reference-format requirement; journal style applied at proof | - | PASS (N/A) | Numbered `[n]` list is acceptable; no format change needed |
| 10 | Web references carry at least the full URL and the date last accessed | M (per summary) | **PASS (was FAIL)** | Only one URL-only reference (Holm 1979, JSTOR); "URL accessed 4 November 2026" added to its entry |
| 11 | Unpublished results not placed in the reference list | R | PASS | None cited |
| 12 | Single anonymised peer review: authors' names may appear | - | PASS (N/A) | No blinding needed |
| 13 | Length: no strict limit | - | PASS (N/A) | 37 pages in the proof |
| 14 | Figures supplied as separate files; resolution requirements for line drawings, halftones and combinations | M | **NOT VERIFIABLE** | The numeric requirements were cut off in the summary. Separate files exist: `paper/figures_v0.8/*.png` (1900-3386 px wide) and vector `*.pdf` for every figure. Check the live guide's resolution table before submission |
| 15 | Competing-interests statement | M (sister-journal; **not verified for this journal**) | PARTIAL | Back-matter placeholder plus the end-of-document form (both boxes unticked) |
| 16 | CRediT author statement | not verified | PARTIAL | Placeholder paragraph |
| 17 | Data/research-data statement (the guide has a section on research data and a data statement) | M | PARTIAL | "Data availability statement" present; repository URL/DOI placeholder; large raw outputs are git-ignored |
| 18 | Keywords (count/style) | not retrieved | NOT VERIFIABLE | Six keywords given |
| 19 | Graphical abstract, cover letter, title-page file, line numbers, equation/heading numbering rules, supplementary-material rules, file formats | not retrieved | NOT VERIFIABLE | Not required by anything the summaries showed; check the live guide |
| 20 | Corresponding author and author order consistent with the submission system | M | PARTIAL | Placeholders; authors must complete |

## Changes made in this step (no scientific wording, numbers, citations, figures, tables or E2 data changed)
1. Abstract condensed from 418 to 244 words (placeholders keep every number tied to the E2 CSVs).
2. Highlights reduced to 5 bullets of <= 85 characters; separate `highlights_v0.8.docx` written by `paper/tools/make_highlights_v08.py`.
3. Generative-AI declaration retitled and reworded per the guide's suggested template (author confirmation still required).
4. Acknowledgements moved to directly before the reference list; accessed date added to the one URL-only reference.
5. `paper/tools/export_docx_v08.py` gained an optional output-path argument.
Pre-change copies: `paper/archive_pre_guide/`. `paper/tools/check_claims_v08.py` was run after the changes: **56 assertions passed, 0 failed**.

## File status
`paper/manuscript_v0.8.docx` is currently open in Word (window "manuscript_v0.8 - Compatibility Mode"), so it could not be overwritten (Permission denied). The updated export is `paper/manuscript_v0.8_guide_check.docx` with its proof `paper/manuscript_v0.8_guide_check_proof.pdf` (rendered through the running Word instance, 37 pages, 2 landscape pages). The previous `manuscript_v0.8.docx` and `manuscript_v0.8_proof.pdf` still show the 418-word abstract and 6 highlights. After closing Word, copy the `_guide_check` files over them (or ask me to).
