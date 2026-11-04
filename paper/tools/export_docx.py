"""Convert paper/manuscript.md to paper/manuscript.docx (python-docx). Run: python paper/tools/export_docx.py"""
import re
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, Inches, Cm

BS = "\\\\"   # regex for one literal backslash
TEX = [(BS + "lVert", "‖"), (BS + "rVert", "‖"), (BS + "bar x", "x̄"), (BS + "bar\\{x\\}", "x̄"), (BS + "mathbf 1", "1"),
       (BS + "mathbf\\{1\\}", "1"), (BS + "varepsilon", "ε"), (BS + "sum", "Σ"), (BS + "qquad", "  "), (BS + "quad", "  "), (BS + "kappa", "κ"),
       (BS + "Bigl|" + BS + "Bigr|" + BS + "bigl|" + BS + "bigr|" + BS + "left|" + BS + "right", ""),
       (BS + "ln", "ln"), (BS + "min", "min"), (BS + "max", "max"), (BS + "text\\{([^}]*)\\}", "\\1"),
       (BS + "le(?![a-z])", "≤"), (BS + " ", " "), (BS + ",", " "), (BS, "")]

def tex(t):
    for _ in range(3):
        t = re.sub(BS + "t?frac\\{([^{}]*)\\}\\{([^{}]*)\\}", lambda m: "(" + m.group(1) + ")/(" + m.group(2) + ")", t)
    for a, b in TEX:
        t = re.sub(a, b, t)
    t = re.sub("_\{([^}]*)\}", lambda m: "_" + (m.group(1) if len(m.group(1)) == 1 else "(" + m.group(1) + ")"), t)
    t = re.sub("\^\{([^}]*)\}", lambda m: "^" + (m.group(1) if len(m.group(1)) == 1 else "(" + m.group(1) + ")"), t)
    return t.replace("{", "").replace("}", "")

def runs(par, text, size=None, bold=False):
    text = re.sub(r"\$([^$]+)\$", lambda m: tex(m.group(1)), text)
    for tok in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)", text):
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**") and len(tok) > 4:
            r = par.add_run(tok[2:-2]); r.bold = True
        elif tok.startswith("`") and tok.endswith("`"):
            r = par.add_run(tok[1:-1]); r.font.name = "Consolas"
        elif tok.startswith("*") and tok.endswith("*") and len(tok) > 2:
            r = par.add_run(tok[1:-1]); r.italic = True
        else:
            r = par.add_run(tok)
        if size: r.font.size = Pt(size)
        if bold: r.bold = True

doc = Document()
st = doc.styles["Normal"]; st.font.name = "Times New Roman"; st.font.size = Pt(11)
for s in doc.sections:
    s.left_margin = s.right_margin = Cm(2.2); s.top_margin = s.bottom_margin = Cm(2.2)
lines = open("paper/manuscript.md", encoding="utf-8").read().split("\n")
i = 0
while i < len(lines):
    l = lines[i]
    if not l.strip() or l.strip() == "---":
        i += 1; continue
    if l.startswith("# "):
        h = doc.add_heading(l[2:], 0); h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif l.startswith("### "):
        doc.add_heading(l[4:], 3)
    elif l.startswith("## "):
        doc.add_heading(l[3:], 1)
    elif l.startswith("$$"):
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(tex(l.strip().strip("$")).strip()); r.italic = True
    elif l.startswith("!["):
        m = re.match(r"!\[(.*)\]\((.*)\)", l)
        doc.add_picture("paper/" + m.group(2), width=Inches(6.4))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        p = doc.add_paragraph(); runs(p, m.group(1), size=9, bold=False)
    elif l.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            if not re.match(r"^\|[-| :]+\|$", lines[i]):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
            i += 1
        i -= 1
        nc = len(rows[0]); fs = 9 if nc <= 4 else 7.5 if nc <= 7 else 6.5
        t = doc.add_table(rows=len(rows), cols=nc); t.style = "Table Grid"
        for ri, row in enumerate(rows):
            for ci in range(nc):
                c = t.cell(ri, ci); c.text = ""
                runs(c.paragraphs[0], row[ci] if ci < len(row) else "", size=fs, bold=(ri == 0))
        doc.add_paragraph()
    elif l.startswith("> "):
        p = doc.add_paragraph(); runs(p, l[2:], size=9); p.runs[0].italic = True
    elif re.match(r"^\d+\. ", l):
        p = doc.add_paragraph(style="List Number"); runs(p, re.sub(r"^\d+\. ", "", l))
    elif l.startswith("- "):
        p = doc.add_paragraph(style="List Bullet"); runs(p, l[2:])
    else:
        p = doc.add_paragraph(); runs(p, l)
    i += 1
doc.save("paper/manuscript.docx")
print("saved paper/manuscript.docx")
