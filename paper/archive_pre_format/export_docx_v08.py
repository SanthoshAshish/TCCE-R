"""Convert paper/manuscript_v0.8.md to paper/manuscript_v0.8.docx (python-docx). Run: python paper/tools/export_docx.py"""
import re
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, Inches, Cm

BS = "\\\\"   # regex for one literal backslash
TEX = [(BS + "lVert", "‖"), (BS + "rVert", "‖"), (BS + "bar x", "x̄"), (BS + "bar\\{x\\}", "x̄"), (BS + "mathbf 1", "1"),
       (BS + "mathbf\\{1\\}", "1"), (BS + "varepsilon", "ε"), (BS + "sum", "Σ"), (BS + "qquad", "  "), (BS + "quad", "  "), (BS + "kappa", "κ"), (BS + "alpha", "α"), (BS + "beta", "β"), (BS + "gamma", "γ"), (BS + "delta", "δ"), (BS + "Theta", "Θ"),
       (BS + "cdot", "·"), (BS + "ldots", "…"),
       (BS + "Bigl|" + BS + "Bigr|" + BS + "bigl|" + BS + "bigr|" + BS + "left|" + BS + "right", ""),
       (BS + "ln", "ln"), (BS + "min", "min"), (BS + "max", "max"), (BS + "text\\{([^}]*)\\}", "\\1"),
       (BS + "le(?![a-z])", "≤"), (BS + "ge(?![a-z])", "≥"), (BS + " ", " "), (BS + ",", " "), (BS, "")]

def tex(t):
    for _ in range(3):
        t = re.sub(BS + "t?frac\\{([^{}]*)\\}\\{([^{}]*)\\}", lambda m: "(" + m.group(1) + ")/(" + m.group(2) + ")", t)
    for a, b in TEX:
        t = re.sub(a, b, t)
    t = re.sub("_\{([^}]*)\}", lambda m: "_" + (m.group(1) if len(m.group(1)) == 1 else "(" + m.group(1) + ")"), t)
    t = re.sub("\^\{([^}]*)\}", lambda m: "^" + (m.group(1) if len(m.group(1)) == 1 else "(" + m.group(1) + ")"), t)
    return t.replace("{", "").replace("}", "")

SUB = re.compile(r"(?<![A-Za-z0-9_])([A-Za-zΘΔκθλεαβγδ])_(\{[^}]*\}|\([^)]*\)|[A-Za-z0-9]{1,5})")


def emit(par, s, size=None, bold=False, italic=False, code=False):
    pos = 0
    pieces = []
    if not code:
        for m in SUB.finditer(s):
            pieces.append((s[pos:m.start()] + m.group(1), False))
            sub = m.group(2)
            if sub[0] in "{(":
                sub = sub[1:-1]
            pieces.append((sub, True))
            pos = m.end()
    pieces.append((s[pos:], False))
    out = []                                              # second pass: ^{...} / ^x superscripts in the plain pieces
    for txt, is_sub in pieces:
        if is_sub or code:
            out.append((txt, is_sub, False))
            continue
        pos = 0
        for m in re.finditer(r"\^(\{[^}]*\}|[A-Za-z0-9]{1,3})", txt):
            out.append((txt[pos:m.start()], False, False))
            sup = m.group(1)
            out.append((sup[1:-1] if sup[0] == "{" else sup, False, True))
            pos = m.end()
        out.append((txt[pos:], False, False))
    for txt, is_sub, is_sup in out:
        if not txt:
            continue
        r = par.add_run(txt)
        r.font.subscript = is_sub or None
        r.font.superscript = is_sup or None
        r.bold = bold or None
        r.italic = italic or None
        if code:
            r.font.name = "Consolas"
        if size:
            r.font.size = Pt(size)


def runs(par, text, size=None, bold=False):
    text = re.sub(r"\$([^$]+)\$", lambda m: tex(m.group(1)), text)
    for tok in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)", text):
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**") and len(tok) > 4:
            emit(par, tok[2:-2], size, True)
        elif tok.startswith("`") and tok.endswith("`"):
            emit(par, tok[1:-1], size, bold, code=True)
        elif tok.startswith("*") and tok.endswith("*") and len(tok) > 2:
            emit(par, tok[1:-1], size, bold, italic=True)
        else:
            emit(par, tok, size, bold)


def repeat_header(row):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)


doc = Document()
st = doc.styles["Normal"]; st.font.name = "Times New Roman"; st.font.size = Pt(11)
for s in doc.sections:
    s.left_margin = s.right_margin = Cm(2.2); s.top_margin = s.bottom_margin = Cm(2.2)
lines = open("paper/manuscript_v0.8.md", encoding="utf-8").read().split("\n")
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
        emit(p, tex(l.strip().strip("$")).strip(), None, False, italic=True)
    elif l.startswith("!["):
        m = re.match(r"!\[(.*)\]\((.*)\)", l)
        doc.add_picture("paper/" + m.group(2), width=Inches(6.4))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        p = doc.add_paragraph(); runs(p, m.group(1), size=9, bold=False)
    elif l.startswith("```"):
        i += 1
        block = []
        while i < len(lines) and not lines[i].startswith("```"):
            block.append(lines[i])
            i += 1
        p = doc.add_paragraph()
        for k, bl in enumerate(block):
            r = p.add_run(bl)
            r.font.name = "Consolas"
            r.font.size = Pt(7.5)
            if k < len(block) - 1:
                r.add_break()
    elif l.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            if not re.match(r"^\|[-| :]+\|$", lines[i]):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
            i += 1
        i -= 1
        nc = len(rows[0]); fs = 9 if nc <= 4 else 7.5 if nc <= 7 else 6.5
        t = doc.add_table(rows=len(rows), cols=nc); t.style = "Table Grid"
        repeat_header(t.rows[0])
        for ri, row in enumerate(rows):
            for ci in range(nc):
                c = t.cell(ri, ci); c.text = ""
                runs(c.paragraphs[0], row[ci] if ci < len(row) else "", size=fs, bold=(ri == 0))
        doc.add_paragraph()
    elif l.startswith("> "):
        p = doc.add_paragraph(); runs(p, l[2:], size=9); p.runs[0].italic = True
    elif re.match(r"^\d+\. ", l):
        # literal numbers with a hanging indent: Word auto-numbering would continue across lists and make the reference
        # numbers differ from the in-text citations
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.9)
        p.paragraph_format.first_line_indent = Cm(-0.9)
        runs(p, l)
    elif l.startswith("- "):
        p = doc.add_paragraph(style="List Bullet"); runs(p, l[2:])
    else:
        p = doc.add_paragraph(); runs(p, l)
    i += 1
doc.save("paper/manuscript_v0.8.docx")
print("saved paper/manuscript_v0.8.docx")
