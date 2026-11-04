"""Assemble paper/manuscript.md from manuscript_template.md, generated tables and the verified reference list.
Run: python paper/tools/build_manuscript.py"""
import re

TABLE1 = """| Arm | Name | Mutation attempted when | Stress / state used |
|---|---|---|---|
| A0 | Static | never (reference; defines κ, τ, recovery anchors) | — |
| A1 | Reactive | E_k > h | instantaneous E |
| A2 | Moving average | 4-epoch moving average of E > h | E |
| A3 | CUSUM-E | D > Θ, with s = E and reference κ_E | E (accumulated) |
| A4 | CUSUM-ECV | D > Θ, with s = 0.5E + 0.3C + 0.2V, reference κ_s | E, C, V (accumulated), fixed Θ |
| A5 | Full TCCE-R | as A4, with adaptive Θ and counterfactual feedback | E, C, V, adaptive Θ |
| A6 | Random timing | at random epochs (gaps ≥ 2), per-seed count from calibration distribution | none (state-blind) |
| A7 | Front-loaded | at epochs 0, 2, 4, … until the per-seed count is reached | none (state-blind) |

*Table 1. Compared arms. All share the cooldown of 2 epochs, cap M, one attempt per epoch, the same selector, safety gate and strict edge budget.*
"""
s = open("paper/manuscript_template.md", encoding="utf-8").read()
s = s.replace("{{T:table1_arms}}", TABLE1)
s = s.replace("{{REFERENCES}}", open("paper/references/references_formatted_authoryear.md", encoding="utf-8").read())
def sub(m):
    return open(f"paper/tables/{m.group(1)}.md", encoding="utf-8").read()
s = re.sub(r"\{\{T:(\w+)\}\}", sub, s)
# author-year in-text citations (keys -> "Author Year"), reference-list keys dropped
CITE = {"Barnett2005": "Barnett 2005", "ChanAkoglu2016": "Chan and Akoglu 2016", "Dimarogonas2012": "Dimarogonas et al. 2012",
        "Efron1979": "Efron 1979", "Fiedler1973": "Fiedler 1973", "GencataMukherjee2003": "Gençata and Mukherjee 2003",
        "Gencata2003Thesis": "Gençata 2003", "GhoshBoyd2006": "Ghosh and Boyd 2006", "GrossBlasius2008": "Gross and Blasius 2008",
        "Holm1979": "Holm 1979", "Jadbabaie2003": "Jadbabaie et al. 2003", "KarMoura2008": "Kar and Moura 2008",
        "KarMoura2009": "Kar and Moura 2009", "Lakens2017": "Lakens 2017", "LeBlanc2013": "LeBlanc et al. 2013",
        "Neumayer2011": "Neumayer et al. 2011", "OlfatiSaberMurray2004": "Olfati-Saber and Murray 2004",
        "OlfatiSaberFaxMurray2007": "Olfati-Saber et al. 2007", "Page1954": "Page 1954", "Quattrociocchi2014": "Quattrociocchi et al. 2014",
        "Santi2005": "Santi 2005", "Sterbenz2010": "Sterbenz et al. 2010", "Sydney2013": "Sydney et al. 2013",
        "Tabuada2007": "Tabuada 2007", "Wilcoxon1945": "Wilcoxon 1945", "XiaoBoyd2004": "Xiao and Boyd 2004",
        "XiaoBoydLall2005": "Xiao et al. 2005", "Zavlanos2011": "Zavlanos et al. 2011"}
head, refs = s.split("## References")
refs, tail = refs.split("## Appendices")
refs = re.sub(r"^- \[\w+\] ", "- ", refs, flags=re.M)
def cite(m):
    keys = [k.strip().split(",")[0] for k in m.group(1).split(";")]
    if not all(k in CITE for k in keys):
        return m.group(0)
    return "(" + "; ".join(CITE[k] for k in keys) + ")"
head = re.sub(r"\[([A-Za-z0-9]+(?:[;,][^\]]*)?)\]", cite, head)
head = re.sub(r"\(Ghosh and Boyd 2006, eq\. 7\)", "(Ghosh and Boyd 2006, eq. 7)", head)
s = head + "## References" + refs + "## Appendices" + tail
open("paper/manuscript.md", "w", encoding="utf-8").write(s)
print("manuscript.md written,", len(s.split()), "words; unresolved markers:", s.count("UNRESOLVED"))
