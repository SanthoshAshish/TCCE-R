"""Convert paper/manuscript_v0.8.md to paper/manuscript_v0.8.docx (python-docx).   python paper/tools/export_docx_v08.py

Layout conventions taken from the sample article (an Elsevier 'Journal Pre-proof' PDF, Results in Engineering), measured from the PDF:
A4, Times New Roman 12 pt, 1.5 line spacing, left/right margins about 2.1 cm, justified body text, bold 14 pt centred title,
centred author/affiliation block with a corresponding-author mark, a Highlights page before the title page, one-paragraph
abstract and a 'Keywords:' line, bold numbered headings 'N. Title' / 'N.M. Title', equations centred with the number at the
right margin, table captions ABOVE tables ('Table N text'), figure captions BELOW figures ('Fig. N. text'), numbered
references '[n] Surname, I., YEAR. Title. Venue, vol(issue), pp.' and a 'Declaration of interests' form at the end.
Not reproduced (publisher-added in the sample): the cover page, 'Journal Pre-proof' banner, watermark, page furniture.
This is NOT an official journal template.
"""
import re

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from PIL import Image

BS = "\\\\"   # regex for one literal backslash
TEX = [(BS + "lVert", "‖"), (BS + "rVert", "‖"), (BS + "bar x", "x̄"), (BS + "bar\\{x\\}", "x̄"), (BS + "mathbf 1", "1"),
       (BS + "mathbf\\{1\\}", "1"), (BS + "varepsilon", "ε"), (BS + "sum", "Σ"), (BS + "qquad", "  "), (BS + "quad", "  "),
       (BS + "kappa", "κ"), (BS + "alpha", "α"), (BS + "beta", "β"), (BS + "gamma", "γ"), (BS + "delta", "δ"), (BS + "Theta", "Θ"),
       (BS + "cdot", "·"), (BS + "ldots", "…"),
       (BS + "Bigl|" + BS + "Bigr|" + BS + "bigl|" + BS + "bigr|" + BS + "left|" + BS + "right", ""),
       (BS + "ln", "ln"), (BS + "min", "min"), (BS + "max", "max"), (BS + "text\\{([^}]*)\\}", "\\1"),
       (BS + "le(?![a-z])", "≤"), (BS + "ge(?![a-z])", "≥"), (BS + " ", " "), (BS + ",", " "), (BS, "")]


def tex(t):
    for _ in range(3):
        t = re.sub(BS + "t?frac\\{([^{}]*)\\}\\{([^{}]*)\\}", lambda m: "(" + m.group(1) + ")/(" + m.group(2) + ")", t)
    for a, b in TEX:
        t = re.sub(a, b, t)
    t = re.sub(r"_\{([^}]*)\}", lambda m: "_" + (m.group(1) if len(m.group(1)) == 1 else "(" + m.group(1) + ")"), t)
    t = re.sub(r"\^\{([^}]*)\}", lambda m: "^" + (m.group(1) if len(m.group(1)) == 1 else "(" + m.group(1) + ")"), t)
    return t.replace("{", "").replace("}", "")


SUB = re.compile(r"(?<![A-Za-z0-9_])([A-Za-zΘΔκθλεαβγδ])_(\{[^}]*\}|\([^)]*\)|[A-Za-z0-9]{1,5})")
FONT = "Times New Roman"
TEXT_W = 16.8      # cm between the margins


def set_run_font(r, size=None, bold=None, italic=None, code=False, sub=None, sup=None):
    r.font.name = "Consolas" if code else FONT
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Consolas" if code else FONT)
    if size:
        r.font.size = Pt(size)
    r.bold = bold or None
    r.italic = italic or None
    r.font.subscript = sub or None
    r.font.superscript = sup or None


def emit(par, s, size=None, bold=False, italic=False, code=False):
    pos, pieces = 0, []
    if not code:
        for m in SUB.finditer(s):
            pieces.append((s[pos:m.start()] + m.group(1), False))
            sub = m.group(2)
            pieces.append((sub[1:-1] if sub[0] in "{(" else sub, True))
            pos = m.end()
    pieces.append((s[pos:], False))
    out = []
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
        if txt:
            set_run_font(par.add_run(txt), size, bold, italic, code, is_sub, is_sup)


def runs(par, text, size=None, bold=False, italic=False):
    text = re.sub(r"\$([^$]+)\$", lambda m: tex(m.group(1)), text)
    for tok in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)", text):
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**") and len(tok) > 4:
            emit(par, tok[2:-2], size, True, italic)
        elif tok.startswith("`") and tok.endswith("`"):
            emit(par, tok[1:-1], size, bold, italic, code=True)
        elif tok.startswith("*") and tok.endswith("*") and len(tok) > 2:
            emit(par, tok[1:-1], size, bold, True)
        else:
            emit(par, tok, size, bold, italic)


def fmt_par(p, align=WD_ALIGN_PARAGRAPH.JUSTIFY, spacing=1.5, after=4, before=0, keep_next=False):
    pf = p.paragraph_format
    p.alignment = align
    pf.line_spacing = spacing
    pf.space_after = Pt(after)
    pf.space_before = Pt(before)
    pf.keep_with_next = keep_next


def border(el_parent, tag, val="single", sz=6):
    b = OxmlElement(tag)
    b.set(qn("w:val"), val)
    b.set(qn("w:sz"), str(sz))
    b.set(qn("w:space"), "0")
    b.set(qn("w:color"), "000000")
    el_parent.append(b)


def table_rules(t, nc_header=True):
    """Booktabs-like: rule above the table, rule under the header row, rule below the table; no vertical rules."""
    tblPr = t._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    border(borders, "w:top", sz=8)
    border(borders, "w:bottom", sz=8)
    tblPr.append(borders)
    for c in t.rows[0].cells:
        tcPr = c._tc.get_or_add_tcPr()
        tb = OxmlElement("w:tcBorders")
        border(tb, "w:bottom", sz=4)
        tcPr.append(tb)


def repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def no_split(row):
    trPr = row._tr.get_or_add_trPr()
    trPr.append(OxmlElement("w:cantSplit"))


def setup_section(sec, landscape=False):
    sec.orientation = WD_ORIENT.LANDSCAPE if landscape else WD_ORIENT.PORTRAIT
    sec.page_width, sec.page_height = (Cm(29.7), Cm(21.0)) if landscape else (Cm(21.0), Cm(29.7))
    sec.left_margin = sec.right_margin = Cm(2.1)
    sec.top_margin = sec.bottom_margin = Cm(2.3)


def add_page_number(sec):
    p = sec.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for kind, txt in (("begin", None), (None, "PAGE"), ("end", None)):
        r = p.add_run()
        set_run_font(r, 10)
        if kind:
            f = OxmlElement("w:fldChar")
            f.set(qn("w:fldCharType"), kind)
            r._r.append(f)
        else:
            it = OxmlElement("w:instrText")
            it.set(qn("xml:space"), "preserve")
            it.text = txt
            r._r.append(it)


doc = Document()
st = doc.styles["Normal"]
st.font.name = FONT
st.font.size = Pt(12)
st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
for name, size in (("Heading 1", 12), ("Heading 2", 12), ("Heading 3", 12)):
    hs = doc.styles[name]
    hs.font.name, hs.font.size, hs.font.bold, hs.font.italic = FONT, Pt(size), True, False
    hs.font.color.rgb = None
    hs.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    hs.element.rPr.rFonts.set(qn("w:ascii"), FONT)
    hs.element.rPr.rFonts.set(qn("w:hAnsi"), FONT)
sec0 = doc.sections[0]
setup_section(sec0)
add_page_number(sec0)

lines = open("paper/manuscript_v3.md", encoding="utf-8").read().split("\n")
i, front, in_land = 0, False, False


def table_info(k):
    """(columns, longest cell text in columns 3+) of the next table, looking ahead from line k."""
    while k < len(lines) and not lines[k].startswith("|"):
        if lines[k].startswith(("#", "![")):
            return 0, 0
        k += 1
    if k >= len(lines):
        return 0, 0
    rows = []
    while k < len(lines) and lines[k].startswith("|"):
        if not re.match(r"^\|[-| :]+\|$", lines[k]):
            rows.append([c.strip() for c in lines[k].strip().strip("|").split("|")])
        k += 1
    return len(rows[0]), max((len(c) for r in rows for c in r[2:]), default=0)


def is_wide(nc, longest):
    return nc >= 8 and longest > 14          # many columns holding long entries (e.g. 'mean [lo, hi]')


def switch(landscape):
    global in_land
    return                                   # V3: portrait only (wide tables use a smaller font)
    sec = doc.add_section(WD_SECTION.NEW_PAGE)
    setup_section(sec, landscape)
    in_land = landscape


while i < len(lines):
    l = lines[i]
    if not l.strip() or l.strip() == "---":
        i += 1
        continue
    if l.strip() == "[[PAGEBREAK]]":
        doc.add_page_break()
    elif l.startswith("# "):
        p = doc.add_paragraph()
        emit(p, l[2:].strip(), 14, True)
        fmt_par(p, WD_ALIGN_PARAGRAPH.CENTER, 1.15, 12, 0)
        front = True
    elif l.startswith("## ") or l.startswith("### "):
        front = False
        lvl = 1 if l.startswith("## ") else 2
        h = doc.add_heading(l[3 + (lvl - 1):].strip(), lvl)
        fmt_par(h, WD_ALIGN_PARAGRAPH.LEFT, 1.15, 6, 14 if lvl == 1 else 10, True)
    elif l.startswith("$$"):
        body = l.strip().strip("$")
        m = re.search(r"\\tag\{(\d+)\}", body)
        num = m.group(1) if m else None
        body = re.sub(r"\\tag\{\d+\}", "", body)
        p = doc.add_paragraph()
        ts = p.paragraph_format.tab_stops
        ts.add_tab_stop(Cm(TEXT_W / 2), WD_TAB_ALIGNMENT.CENTER)
        ts.add_tab_stop(Cm(TEXT_W), WD_TAB_ALIGNMENT.RIGHT)
        set_run_font(p.add_run("\t"))
        emit(p, tex(body).strip(), None, False, italic=True)
        set_run_font(p.add_run("\t(" + num + ")" if num else ""))
        fmt_par(p, WD_ALIGN_PARAGRAPH.LEFT, 1.5, 6, 6)
    elif l.startswith("!["):
        m = re.match(r"!\[(.*)\]\((.*)\)", l)
        path = "paper/" + m.group(2)
        w, h = Image.open(path).size
        width = min(15.8, 20.5 * w / h)
        doc.add_picture(path, width=Cm(width))
        pic = doc.paragraphs[-1]
        fmt_par(pic, WD_ALIGN_PARAGRAPH.CENTER, 1.0, 2, 6, True)
        cm = re.match(r"^(Fig\. \d+\.)\s*(.*)$", m.group(1), re.S)
        p = doc.add_paragraph()
        if cm:
            emit(p, cm.group(1), 10.5, True)
            runs(p, " " + cm.group(2), size=10.5)
        else:
            runs(p, m.group(1), size=10.5)
        fmt_par(p, WD_ALIGN_PARAGRAPH.CENTER if len(m.group(1)) < 110 else WD_ALIGN_PARAGRAPH.JUSTIFY, 1.15, 12)
    elif l.startswith("```"):
        i += 1
        block = []
        while i < len(lines) and not lines[i].startswith("```"):
            block.append(lines[i])
            i += 1
        t = doc.add_table(rows=1, cols=1)
        tblPr = t._tbl.tblPr
        bs = OxmlElement("w:tblBorders")
        for side in ("w:top", "w:left", "w:bottom", "w:right"):
            border(bs, side, sz=6)
        tblPr.append(bs)
        cp = t.cell(0, 0).paragraphs[0]
        for k, bl in enumerate(block):
            r = cp.add_run(bl)
            set_run_font(r, 8.5, code=True)
            if k < len(block) - 1:
                r.add_break()
        fmt_par(cp, WD_ALIGN_PARAGRAPH.LEFT, 1.0, 0)
        sp = doc.add_paragraph()
        fmt_par(sp, WD_ALIGN_PARAGRAPH.LEFT, 1.0, 6)
    elif l.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            if not re.match(r"^\|[-| :]+\|$", lines[i]):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
            i += 1
        i -= 1
        nc = len(rows[0])
        if is_wide(nc, max((len(c) for r in rows for c in r[2:]), default=0)) and not in_land:
            switch(True)
        fs = 10.5 if nc <= 3 else 9.5 if nc <= 5 else 8.5 if nc <= 7 else 7.5
        t = doc.add_table(rows=len(rows), cols=nc)
        t.autofit = True
        table_rules(t)
        repeat_header(t.rows[0])
        for ri, row in enumerate(rows):
            no_split(t.rows[ri])
            for ci in range(nc):
                c = t.cell(ri, ci)
                c.text = ""
                runs(c.paragraphs[0], row[ci] if ci < len(row) else "", size=fs, bold=(ri == 0))
                fmt_par(c.paragraphs[0], WD_ALIGN_PARAGRAPH.LEFT, 1.0, 1, keep_next=(ri < 2))
        sp = doc.add_paragraph()
        fmt_par(sp, WD_ALIGN_PARAGRAPH.LEFT, 1.0, 0)
        sp.paragraph_format.space_after = Pt(0)
        r_ = sp.add_run(" ")
        r_.font.size = Pt(4)
        nxt = i + 1
        while nxt < len(lines) and not lines[nxt].strip():
            nxt += 1
        if in_land and not (nxt < len(lines) and lines[nxt].startswith("|")):
            switch(False)
    elif l.startswith("**Table "):
        m = re.match(r"^\*\*(Table [A-Z]?\d+)\*\*\s*(.*)$", l)
        if is_wide(*table_info(i + 1)) or m.group(1) == "Table 1":
            if not in_land:
                switch(True)
        p = doc.add_paragraph()
        emit(p, m.group(1), 10.5, True)
        runs(p, " " + m.group(2), size=10.5)
        fmt_par(p, WD_ALIGN_PARAGRAPH.LEFT, 1.15, 4, 8, True)
    elif l.startswith("> "):
        p = doc.add_paragraph()
        runs(p, l[2:], size=9.5, italic=True)
        fmt_par(p, WD_ALIGN_PARAGRAPH.LEFT, 1.15, 8)
    elif re.match(r"^\[\d+\] ", l):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(1.0)
        p.paragraph_format.first_line_indent = Cm(-1.0)
        runs(p, l, size=11)
        fmt_par(p, WD_ALIGN_PARAGRAPH.LEFT, 1.15, 4)
        p.paragraph_format.left_indent = Cm(1.0)
        p.paragraph_format.first_line_indent = Cm(-1.0)
    elif re.match(r"^\d+\. ", l):
        p = doc.add_paragraph()
        runs(p, l)
        fmt_par(p, WD_ALIGN_PARAGRAPH.JUSTIFY, 1.5, 3)
        p.paragraph_format.left_indent = Cm(0.9)
        p.paragraph_format.first_line_indent = Cm(-0.9)
    elif l.startswith("- "):
        p = doc.add_paragraph(style="List Bullet")
        runs(p, l[2:])
        fmt_par(p, WD_ALIGN_PARAGRAPH.JUSTIFY, 1.5, 2)
    elif l.startswith("☐"):
        p = doc.add_paragraph()
        runs(p, l)
        fmt_par(p, WD_ALIGN_PARAGRAPH.LEFT, 1.5, 4)
    else:
        p = doc.add_paragraph()
        runs(p, l)
        al = WD_ALIGN_PARAGRAPH.CENTER if front else (WD_ALIGN_PARAGRAPH.LEFT if "`" in l else WD_ALIGN_PARAGRAPH.JUSTIFY)
        fmt_par(p, al, 1.15 if front else 1.5, 6 if front else 4)
    i += 1
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "paper/manuscript_v3.docx"      # optional output path (e.g. when the default file is open in Word)
doc.save(OUT)
print("saved", OUT)
