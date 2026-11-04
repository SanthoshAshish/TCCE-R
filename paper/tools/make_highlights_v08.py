"""Write the separate, editable highlights file (paper/submission/highlights_v0.8.docx) from the Highlights block of
paper/manuscript_v0.8.md and report the bullet count and character counts.   python paper/tools/make_highlights_v08.py"""
import os
import re

from docx import Document
from docx.shared import Pt

md = open("paper/manuscript_v0.8.md", encoding="utf-8").read()
block = md.split("**Highlights**")[1].split("[[PAGEBREAK]]")[0]
bullets = [re.sub(r"^- ", "", l).strip() for l in block.strip().split("\n") if l.strip()]
os.makedirs("paper/submission", exist_ok=True)
doc = Document()
doc.styles["Normal"].font.name = "Times New Roman"
doc.styles["Normal"].font.size = Pt(12)
h = doc.add_paragraph()
h.add_run("Highlights").bold = True
for b in bullets:
    doc.add_paragraph(b, style="List Bullet")
doc.save("paper/submission/highlights_v0.8.docx")
print(len(bullets), "bullets; characters:", [len(b) for b in bullets])
assert 3 <= len(bullets) <= 5 and all(len(b) <= 85 for b in bullets)
