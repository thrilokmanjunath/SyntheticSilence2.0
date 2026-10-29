"""
Builds the IEEE-style draft from paper/content.py.

    python paper/build_paper.py             # writes paper/out/*.docx and *.tex

Outputs
  SyntheticSilence_IEEE_Draft.docx   two-column Word document in IEEE conference layout
  SyntheticSilence_IEEE_Draft.tex    IEEEtran source (compile with pdflatex; not compiled by this script)
  figs/pipeline.png                  Figure 1

The cross-model audit table is filled from the newest results/llm_eval/*/summary.json. Without one it
is written with empty cells and a caption that says the audit has not been run.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

from docx import Document  # noqa: E402
from docx.enum.section import WD_SECTION  # noqa: E402
from docx.enum.table import WD_TABLE_ALIGNMENT  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Inches, Pt  # noqa: E402

import content as C  # noqa: E402
import mathtext  # noqa: E402
from figures import pipeline_figure  # noqa: E402

OUT = HERE / "out"
FIGS = OUT / "figs"
FONT = "Times New Roman"

DISPLAY_NAMES = {
    "openai/gpt-4o": "GPT-4o",
    "anthropic/claude-sonnet-4.5": "Claude Sonnet 4.5",
    "google/gemini-2.5-pro": "Gemini 2.5 Pro",
    "google/gemini-2.5-flash": "Gemini 2.5 Flash",
    "meta-llama/llama-3.3-70b-instruct": "Llama 3.3 70B",
    "deepseek/deepseek-chat": "DeepSeek Chat",
    "mistralai/mistral-large": "Mistral Large",
}
# Percent columns; the caption says so. "Ans. ref." is the share of answers with a refuted claim.
AUDIT_HEADER = ["Model", "Claims", "Supp.", "Refut.", "Unsett.", "No src.", "Ans. ref."]
CI_CELL = re.compile(r"^(\d+(?:\.\d+)?) \(([^)]*)\)$")


# ---------------------------------------------------------------- shared helpers

def roman(n: int) -> str:
    out, table = "", [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    for value, sym in table:
        while n >= value:
            out += sym
            n -= value
    return out


CITE_RE = re.compile(r"\[@([^\]]+)\]")


class Numbering:
    """Assigns reference numbers in order of first citation."""

    def __init__(self) -> None:
        self.order: List[str] = []

    def number(self, key: str) -> int:
        if key not in C.REFERENCES:
            raise KeyError(f"unknown citation key: {key}")
        if key not in self.order:
            self.order.append(key)
        return self.order.index(key) + 1

    def keys_in(self, text: str) -> List[List[str]]:
        return [[k.strip().lstrip("@") for k in m.group(1).split(";")] for m in CITE_RE.finditer(text)]


def latest_audit() -> Optional[dict]:
    runs = sorted((REPO / "results" / "llm_eval").glob("*/summary.json"), key=lambda p: p.stat().st_mtime)
    if not runs:
        return None
    data = json.loads(runs[-1].read_text(encoding="utf-8"))
    return data if data.get("models") else None


def audit_rows(audit: Optional[dict]) -> List[List[str]]:
    if audit is None:
        names = list(DISPLAY_NAMES.values())
        return [[n, "--", "--", "--", "--", "--", "--"] for n in names]

    def pct(x):
        return "--" if x is None else f"{x * 100:.1f}"

    rows = []
    for model, s in audit["models"].items():
        r = s["claim_rates"]
        rows.append([
            DISPLAY_NAMES.get(model, model), str(s["claims_checked"]), pct(r["supported"]["rate"]),
            pct(r["refuted"]["rate"]), pct(r["insufficient"]["rate"]), pct(r["no_sources"]["rate"]),
            pct(s["responses_with_refuted"]["rate"]),
        ])
    return rows


def audit_caption(audit: Optional[dict]) -> str:
    if audit is None:
        return "Cross-model evidence audit (not yet run; cells are intentionally empty)"
    m = audit["meta"]
    return f"Cross-model evidence audit, {m['prompts']} prompts, checker {m['checker_model']}"


def audit_note(audit: Optional[dict]) -> str:
    if audit is None:
        return ("Produced by scripts/eval\\_llm\\_responses.py. Rates are shares of each model's checked claims; "
                "the last column is the share of answers with at least one refuted claim.")
    return "Rates are shares of each model's checked claims; verdicts are agreement with sources, not truth."


# ---------------------------------------------------------------- Word

def set_cell_border(cell, **edges) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.find(qn("w:tcBorders"))
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge, size in edges.items():
        el = borders.find(qn(f"w:{edge}"))
        if el is None:
            el = OxmlElement(f"w:{edge}")
            borders.append(el)
        el.set(qn("w:val"), "single" if size else "nil")
        el.set(qn("w:sz"), str(size or 0))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "000000")


def fmt(run, size=10, bold=False, italic=False, caps=False, sub=False, sup=False) -> None:
    run.font.name = FONT
    run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.small_caps = caps
    run.font.subscript = sub
    run.font.superscript = sup


def para_fmt(p, align=None, before=0, after=0, left=None, first=None, keep=False) -> None:
    pf = p.paragraph_format
    pf.space_before, pf.space_after = Pt(before), Pt(after)
    pf.line_spacing = 1.0
    if align is not None:
        p.alignment = align
    if left is not None:
        pf.left_indent = Inches(left)
    if first is not None:
        pf.first_line_indent = Inches(first)
    if keep:
        pf.keep_with_next = True


def add_math_runs(p, latex: str, size=10, base_italic=False, base_bold=False) -> None:
    for text, style in mathtext.parse(latex):
        if text == "\n":
            p.add_run().add_break()
            continue
        r = p.add_run(text)
        fmt(r, size=size, bold=base_bold or "b" in style, italic=base_italic or "i" in style,
            sub="sub" in style, sup="sup" in style)


def add_rich(p, text: str, nums: Numbering, size=10, bold=False, italic=False) -> None:
    """Adds text containing [@cites], $math$, ``quotes'' and \\_ escapes."""
    text = text.replace("``", "\u201c").replace("''", "\u201d").replace("\\_", "_").replace("--", "\u2013")

    def cite(m: re.Match) -> str:
        keys = [k.strip().lstrip("@") for k in m.group(1).split(";")]
        return ", ".join(f"[{nums.number(k)}]" for k in keys)

    text = CITE_RE.sub(cite, text)
    for piece in re.split(r"(\$[^$]*\$)", text):
        if not piece:
            continue
        if piece.startswith("$") and piece.endswith("$") and len(piece) > 1:
            add_math_runs(p, piece[1:-1], size=size, base_italic=italic, base_bold=bold)
        else:
            r = p.add_run(piece)
            fmt(r, size=size, bold=bold, italic=italic)


def set_columns(section, count: int, space_twips: int = 360) -> None:
    sect_pr = section._sectPr
    cols = sect_pr.find(qn("w:cols"))
    if cols is None:
        cols = OxmlElement("w:cols")
        sect_pr.append(cols)
    cols.set(qn("w:num"), str(count))
    cols.set(qn("w:space"), str(space_twips))


def build_docx(path: Path, nums: Numbering, audit: Optional[dict]) -> None:
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = FONT
    st.font.size = Pt(10)

    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    sec.left_margin = sec.right_margin = Inches(0.625)
    sec.top_margin, sec.bottom_margin = Inches(0.75), Inches(1.0)

    # ---- title block (single column)
    p = doc.add_paragraph()
    para_fmt(p, WD_ALIGN_PARAGRAPH.CENTER, before=6, after=10)
    fmt(p.add_run(C.TITLE), size=22)

    table = doc.add_table(rows=1, cols=len(C.AUTHORS))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for cell, author in zip(table.rows[0].cells, C.AUTHORS):
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        fmt(cell.paragraphs[0].add_run(author["name"]), size=11)
        for line, italic in ((author["line1"], True), (author["line2"], True), (author["email"], False)):
            q = cell.add_paragraph()
            q.alignment = WD_ALIGN_PARAGRAPH.CENTER
            fmt(q.add_run(line), size=9, italic=italic)
            para_fmt(q, WD_ALIGN_PARAGRAPH.CENTER)
    sp = doc.add_paragraph()
    para_fmt(sp, after=6)

    # ---- body (two columns)
    body = doc.add_section(WD_SECTION.CONTINUOUS)
    set_columns(body, 2)

    p = doc.add_paragraph()
    para_fmt(p, WD_ALIGN_PARAGRAPH.JUSTIFY, after=6)
    fmt(p.add_run("Abstract\u2014"), size=9, bold=True, italic=True)
    fmt(p.add_run(C.ABSTRACT), size=9, bold=True)

    p = doc.add_paragraph()
    para_fmt(p, WD_ALIGN_PARAGRAPH.JUSTIFY, after=8)
    fmt(p.add_run("Index Terms\u2014"), size=9, bold=True, italic=True)
    fmt(p.add_run(", ".join(C.KEYWORDS)), size=9, bold=True)

    eq_no = 0
    fig_no = 0
    for idx, (numeral, title, blocks) in enumerate(C.SECTIONS, start=1):
        h = doc.add_paragraph()
        para_fmt(h, WD_ALIGN_PARAGRAPH.CENTER, before=8, after=4, keep=True)
        fmt(h.add_run(f"{numeral}. {title}".upper()), size=10, caps=False)

        for block in blocks:
            kind = block[0]
            if kind == "p":
                q = doc.add_paragraph()
                para_fmt(q, WD_ALIGN_PARAGRAPH.JUSTIFY, after=4, first=0.17)
                add_rich(q, block[1], nums)
            elif kind == "sub":
                q = doc.add_paragraph()
                para_fmt(q, WD_ALIGN_PARAGRAPH.LEFT, before=4, after=2, keep=True)
                fmt(q.add_run(block[1]), size=10, italic=True)
            elif kind == "list":
                for item in block[1]:
                    q = doc.add_paragraph()
                    para_fmt(q, WD_ALIGN_PARAGRAPH.JUSTIFY, after=2, left=0.22, first=-0.17)
                    fmt(q.add_run("\u2022\u2002"), size=10)
                    add_rich(q, item, nums)
            elif kind == "eq":
                lines = [s.strip() for s in block[1].split("\\qquad")]
                eq_no += 1
                for n, line in enumerate(lines):
                    q = doc.add_paragraph()
                    para_fmt(q, WD_ALIGN_PARAGRAPH.LEFT, before=2 if n == 0 else 0, after=2)
                    stops = q.paragraph_format.tab_stops
                    stops.add_tab_stop(Inches(1.72), WD_TAB_ALIGNMENT.CENTER)
                    stops.add_tab_stop(Inches(3.45), WD_TAB_ALIGNMENT.RIGHT)
                    fmt(q.add_run("\t"))
                    add_math_runs(q, line)
                    if n == len(lines) - 1:
                        fmt(q.add_run(f"\t({eq_no})"), size=10)
            elif kind == "fig":
                fig_no += 1
                q = doc.add_paragraph()
                para_fmt(q, WD_ALIGN_PARAGRAPH.CENTER, before=4, after=2, keep=True)
                q.add_run().add_picture(str(FIGS / block[1]), width=Inches(3.3))
                c = doc.add_paragraph()
                para_fmt(c, WD_ALIGN_PARAGRAPH.JUSTIFY, after=6)
                fmt(c.add_run(f"Fig. {fig_no}. "), size=8)
                add_rich(c, block[2], nums, size=8)
            elif kind in ("table", "audit_table"):
                if kind == "table":
                    _, numeral_t, caption, header, rows, note = block
                else:
                    numeral_t, header = block[1], AUDIT_HEADER
                    caption, rows, note = audit_caption(audit), audit_rows(audit), audit_note(audit)
                add_table(doc, numeral_t, caption, header, rows, note, nums)

    # ---- acknowledgment and references
    h = doc.add_paragraph()
    para_fmt(h, WD_ALIGN_PARAGRAPH.CENTER, before=8, after=4, keep=True)
    fmt(h.add_run("ACKNOWLEDGMENT"), size=10)
    q = doc.add_paragraph()
    para_fmt(q, WD_ALIGN_PARAGRAPH.JUSTIFY, after=4, first=0.17)
    fmt(q.add_run(C.ACKNOWLEDGMENT))

    h = doc.add_paragraph()
    para_fmt(h, WD_ALIGN_PARAGRAPH.CENTER, before=8, after=4, keep=True)
    fmt(h.add_run("REFERENCES"), size=10)
    for n, key in enumerate(nums.order, start=1):
        q = doc.add_paragraph()
        para_fmt(q, WD_ALIGN_PARAGRAPH.JUSTIFY, after=2, left=0.3, first=-0.3)
        fmt(q.add_run(f"[{n}]\t"), size=8)
        q.paragraph_format.tab_stops.add_tab_stop(Inches(0.3))
        fmt(q.add_run(C.REFERENCES[key].replace("--", "\u2013")), size=8)

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))


def add_table(doc, numeral: str, caption: str, header: List[str], rows: List[List[str]], note: str,
              nums: Numbering) -> None:
    cap = doc.add_paragraph()
    para_fmt(cap, WD_ALIGN_PARAGRAPH.CENTER, before=6, after=0, keep=True)
    fmt(cap.add_run(f"TABLE {numeral}"), size=8, caps=True)
    cap2 = doc.add_paragraph()
    para_fmt(cap2, WD_ALIGN_PARAGRAPH.CENTER, after=3, keep=True)
    r = cap2.add_run(caption.upper())
    fmt(r, size=7.5)

    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    # Narrow cell padding: Word's default would split short headers across lines.
    tbl_pr = t._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for side in ("left", "right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), "40")
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tbl_pr.append(mar)
    width = 3.45
    first = 0.95 if len(header) >= 6 else (1.15 if len(header) <= 4 else 0.95)
    other = (width - first) / (len(header) - 1)
    for ci in range(len(header)):
        for row in t.rows:
            row.cells[ci].width = Inches(first if ci == 0 else other)

    def fill(cell, text, bold=False, align=WD_ALIGN_PARAGRAPH.CENTER):
        p = cell.paragraphs[0]
        para_fmt(p, align, keep=True)
        text = text.replace("--", "\u2013")
        m = CI_CELL.match(text)
        if m:  # value on one line, its interval on the next, so columns stay narrow
            fmt(p.add_run(m.group(1)), size=7, bold=bold)
            p.add_run().add_break()
            fmt(p.add_run(f"({m.group(2)})"), size=7, bold=bold)
        else:
            fmt(p.add_run(text), size=7, bold=bold)

    for ci, label in enumerate(header):
        fill(t.rows[0].cells[ci], label, bold=True, align=WD_ALIGN_PARAGRAPH.LEFT if ci == 0 else WD_ALIGN_PARAGRAPH.CENTER)
        set_cell_border(t.rows[0].cells[ci], top=8, bottom=6)
    for ri, row in enumerate(rows, start=1):
        for ci, text in enumerate(row):
            fill(t.rows[ri].cells[ci], text, align=WD_ALIGN_PARAGRAPH.LEFT if ci == 0 else WD_ALIGN_PARAGRAPH.CENTER)
            if ri == len(rows):
                set_cell_border(t.rows[ri].cells[ci], bottom=8)

    n = doc.add_paragraph()
    para_fmt(n, WD_ALIGN_PARAGRAPH.JUSTIFY, before=2, after=6)
    add_rich(n, note, nums, size=7)


# ---------------------------------------------------------------- LaTeX

TEX_SPECIAL = {"&": "\\&", "#": "\\#"}


def tex_text(text: str, nums: Numbering) -> str:
    """Text with [@cites] and $math$ -> LaTeX. Math segments pass through untouched."""
    def cite(m: re.Match) -> str:
        keys = [k.strip().lstrip("@") for k in m.group(1).split(";")]
        for k in keys:
            nums.number(k)
        return "\\cite{" + ",".join(keys) + "}"

    text = CITE_RE.sub(cite, text)
    out = []
    for piece in re.split(r"(\$[^$]*\$)", text):
        if piece.startswith("$") and piece.endswith("$") and len(piece) > 1:
            out.append(piece)
            continue
        piece = re.sub(r"(?<!\\)%", r"\\%", piece)
        for k, v in TEX_SPECIAL.items():
            piece = piece.replace(k, v)
        out.append(piece)
    return "".join(out)


def tex_cell(text: str) -> str:
    m = CI_CELL.match(text)
    if m:
        return f"\\shortstack{{{m.group(1)}\\\\({m.group(2)})}}"
    text = re.sub(r"(?<!\\)%", r"\\%", text).replace("&", "\\&")
    return text if "\\_" in text else text.replace("_", "\\_")


def build_tex(path: Path, nums: Numbering, audit: Optional[dict]) -> None:
    L: List[str] = []
    L += [
        "% IEEEtran conference draft generated by paper/build_paper.py. Compile with: pdflatex, pdflatex.",
        "\\documentclass[conference]{IEEEtran}",
        "\\usepackage{amsmath,amssymb,graphicx,booktabs,cite}",
        "\\usepackage[T1]{fontenc}",
        "\\begin{document}",
        "\\title{" + C.TITLE + "}",
    ]
    blocks_a = "\n\\and\n".join(
        f"\\IEEEauthorblockN{{{a['name']}}}\n\\IEEEauthorblockA{{{a['line1']}\\\\ {a['line2']}\\\\ {{{a['email']}}}}}"
        for a in C.AUTHORS)
    L += ["\\author{", blocks_a, "}", "\\maketitle", ""]
    L += ["\\begin{abstract}", tex_text(C.ABSTRACT, nums), "\\end{abstract}", ""]
    L += ["\\begin{IEEEkeywords}", ", ".join(C.KEYWORDS), "\\end{IEEEkeywords}", ""]

    for numeral, title, blocks in C.SECTIONS:
        L.append(f"\\section{{{title}}}")
        for block in blocks:
            kind = block[0]
            if kind == "p":
                L += [tex_text(block[1], nums), ""]
            elif kind == "sub":
                L += [f"\\subsection{{{block[1].split('. ', 1)[1]}}}", ""]
            elif kind == "list":
                L += ["\\begin{itemize}"] + [f"\\item {tex_text(i, nums)}" for i in block[1]] + ["\\end{itemize}", ""]
            elif kind == "eq":
                lines = [s.strip() for s in block[1].split("\\qquad")]
                if len(lines) == 1:
                    L += ["\\begin{equation}", lines[0], "\\end{equation}", ""]
                else:
                    L += ["\\begin{equation}", "\\begin{aligned}", " \\\\\n".join(lines), "\\end{aligned}",
                          "\\end{equation}", ""]
            elif kind == "fig":
                L += ["\\begin{figure}[t]", "\\centering",
                      f"\\includegraphics[width=\\columnwidth]{{figs/{block[1]}}}",
                      f"\\caption{{{tex_text(block[2], nums)}}}", "\\end{figure}", ""]
            elif kind in ("table", "audit_table"):
                if kind == "table":
                    _, numeral_t, caption, header, rows, note = block
                else:
                    numeral_t, header = block[1], AUDIT_HEADER
                    caption, rows, note = audit_caption(audit), audit_rows(audit), audit_note(audit)
                spec = "l" + "c" * (len(header) - 1)
                L += ["\\begin{table}[t]", "\\caption{" + tex_text(caption, nums) + "}", "\\centering",
                      "\\footnotesize", f"\\begin{{tabular}}{{{spec}}}", "\\toprule",
                      " & ".join(tex_cell(h) for h in header) + " \\\\", "\\midrule"]
                for row in rows:
                    L.append(" & ".join(tex_cell(c) for c in row) + " \\\\")
                L += ["\\bottomrule", "\\end{tabular}", "\\par\\vspace{2pt}{\\scriptsize " + tex_text(note, nums) + "}",
                      "\\end{table}", ""]

    L += ["\\section*{Acknowledgment}", tex_text(C.ACKNOWLEDGMENT, nums), ""]
    L += ["\\begin{thebibliography}{99}"]
    for key in nums.order:
        L.append(f"\\bibitem{{{key}}} {C.REFERENCES[key]}")
    L += ["\\end{thebibliography}", "\\end{document}", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    pipeline_figure(FIGS / "pipeline.png")
    audit = latest_audit()

    # Numbering is decided by order of first citation in document order; build once to fix it.
    nums = Numbering()
    build_docx(OUT / "SyntheticSilence_IEEE_Draft.docx", nums, audit)
    tex_nums = Numbering()
    for key in nums.order:          # same numbering for both outputs
        tex_nums.number(key)
    build_tex(OUT / "SyntheticSilence_IEEE_Draft.tex", tex_nums, audit)
    print("references:", len(nums.order))
    print("audit table:", "filled from results" if audit else "empty (audit not run)")
    print("wrote", OUT / "SyntheticSilence_IEEE_Draft.docx")
    print("wrote", OUT / "SyntheticSilence_IEEE_Draft.tex")


if __name__ == "__main__":
    main()
