"""Builds review1/Research_Work_Diary.docx (print on A4, guide signs each week)."""
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = Path(__file__).resolve().parents[1] / "Research_Work_Diary.docx"

INK = RGBColor(0x0F, 0x1B, 0x2D)
TEAL = RGBColor(0x0E, 0x8F, 0x8A)
SLATE = RGBColor(0x5B, 0x6B, 0x80)

TITLE = ("Auditing Language Model Answers Against Sources: Deterministic Verdict Rules, "
         "Provable Properties, and a Validation on FEVER")
AUTHORS = [("Piush Kole", "piushkole@msds.christuniversity.in"), ("Thrilok M", "thrilok.m@msds.christuniversity.in")]

# (week label, [(date, work done, evidence)])
WEEKS = [
    ("Research phase, up to 8 October 2026",
     "Dates of individual steps in this phase are not recorded in the repository; it was committed on 8 October 2026.",
     [
         ("Phase 1", "Stated the hypothesis that evidence insufficiency appears as a density shift in representation space. "
                     "Built the kNN claim-space density pipeline (density, entropy, engine modules).",
          "backend/app/services/algo/density.py, engine.py, uncertainty.py"),
         ("Phase 2", "E0 on FEVER: modest association, AUROC 0.5463. E1 on AVeriTeC: the signal inverted, AUROC 0.2754 for "
                     "insufficiency (0.3545 overall). Post-hoc diagnostics of domain, geometry and style confounds. Froze the original evaluations.",
          "docs/E0_GATE_REPORT.md, docs/E1_GATE_REPORT.md, results/E1_post_analysis, results/FINAL_RESEARCH_FREEZE"),
         ("Phase 3", "F1 cross-manifold test: both cross-domain signals fell to chance. F2 matched negative controls "
                     "(29 pairs, matched on length and lexical diversity): inversion persisted, AUROC 0.3353. Stopped optimising and wrote up the bounded conclusion.",
          "results/F1_cross_manifold, results/F2_matched_controls, results/FINAL_PAPER_PACKAGE"),
         ("8 Oct 2026", "Committed the research package and the first paper drafts to the repository.",
          "Commits 52c60f6 and c7f8c57"),
     ]),
    ("Week of 12 to 18 October 2026",
     "From the earlier result we changed the question: give the reader a per-claim verdict backed by a quote, and build a working tool.",
     [
         ("13 Oct 2026", "Cloned the repository and reviewed it; the backend pipeline was not wired. Built the Chrome extension "
                         "(popup and side panel, Manifest V3, TypeScript) and wired the FastAPI backend: OpenRouter LLM provider, routes, "
                         "claim extraction, retrieval and verdict pipeline. Added unit and integration tests.",
          "extension/, backend/app/, backend/tests/"),
         ("13 Oct 2026", "Wrote the verdict-evaluation harness on FEVER (balanced sample, seed 42, Wilson intervals, exact McNemar, "
                         "paired bootstrap). The baseline run with OpenAlex stopped after 100 of 150 claims because the anonymous request budget was used up; "
                         "added a Wikipedia retriever and a composite retriever so the system reports exhaustion as an error, not as 'no sources'.",
          "backend/experiments/verdict_eval.py, scripts/eval_verdict.py, results/verdict_eval/"),
         ("13 Oct 2026", "Implemented per-source stance with a verbatim-quote check and five deterministic verdict rules. Ran three variants on the same 100 claims. "
                         "Found that 13 of 36 REFUTES claims were called supported; traced it to two causes (a normalised claim that dropped the key detail, "
                         "and a lenient prompt), fixed both and added a regression test.",
          "backend/app/services/algo/stance.py, verdict.py, docs/VERDICT_EVALUATION.md"),
         ("13 Oct 2026", "Added a result cache, streaming (NDJSON) results, a typed API contract generated from OpenAPI, a real-Chrome end-to-end test (35 checks) "
                         "and a 40-prompt cross-model audit harness. The audit has not been run: the model account returned HTTP 402 (no credit).",
          "extension/e2e/chrome-e2e.mjs, scripts/eval_llm_responses.py, data/llm_eval/prompts.json"),
         ("14 Oct 2026", "Proved five properties (verdict rules, entropy, single-query density, shrinkage, Wilson interval) and checked each against the deployed code "
                         "(27,930 exhaustive and 15,000 random source configurations). Drafted the IEEE paper and the journal-format paper (TACL style) with figures, "
                         "confusion matrices, proofs and verified references.",
          "paper/test_propositions.py, paper/out/*.pdf"),
         ("15 Oct 2026", "Committed the extension, backend services, evaluation harness and journal paper to the repository.",
          "Commit ffde438"),
     ]),
    ("Week of 26 October to 1 November 2026",
     "Preparation for Research Implementation Review 1.",
     [
         ("27 Oct 2026", "Re-ran the full test suites: backend 117 passed, extension 44 unit tests and 35 real-Chrome end-to-end checks passed, "
                         "paper checks 34 passed. Captured screenshots of the extension from the real-Chrome run.",
          "backend/tests, extension/test, extension/e2e, paper/"),
         ("27 Oct 2026", "Prepared the Review 1 slide deck (15 slides with speaker notes), this work diary, and the print copy of the research article.",
          "review1/"),
     ]),
]

CHALLENGES = [
    ("Anonymous OpenAlex search budget used up (HTTP 429), so the baseline run stopped at 100 of 150 claims.",
     "Reported all variants on the 100 scored claims; added a Wikipedia retriever; made exhaustion an explicit error state."),
    ("First per-source stance prompt lost accuracy on decisive claims (13 of 36 REFUTES called supported).",
     "Found two causes in our own code and prompt; fixed both; added a regression test; drew no conclusion about the fixed prompt until it is re-evaluated."),
    ("Model account ran out of credit (HTTP 402) during the fresh-sample re-run and before the cross-model audit.",
     "Kept the incomplete runs for transparency only; wrote the audit protocol and script so it can run once credit is added."),
    ("Earlier density score did not behave as its name suggests.",
     "Proved that a single-query density score reduces to a nearest-neighbour distance and that the entropy score rewards redundant sources."),
]

PLAN = [
    "Add model credit and re-evaluate the corrected stance prompt on a fresh 150-claim sample.",
    "Run the 40-prompt cross-model audit on seven commercial models and fill Table III of the paper.",
    "Compare verdicts with human judgements on a sample of audited answers.",
    "Compile the journal paper with the official TACL style file and resolve reviewer comments from Review 1.",
]


def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def borders(table, color="9AA7B5", sz="4"):
    tbl = table._tbl
    tblPr = tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), sz)
        e.set(qn("w:space"), "0")
        e.set(qn("w:color"), color)
        b.append(e)
    tblPr.append(b)


def no_split(row):
    trPr = row._tr.get_or_add_trPr()
    e = OxmlElement("w:cantSplit")
    trPr.append(e)


def repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    e = OxmlElement("w:tblHeader")
    e.set(qn("w:val"), "true")
    trPr.append(e)


def set_widths(table, widths_cm):
    table.autofit = False
    tblPr = table._tbl.tblPr
    lay = OxmlElement("w:tblLayout")
    lay.set(qn("w:type"), "fixed")
    tblPr.append(lay)
    for row in table.rows:
        for i, w in enumerate(widths_cm):
            row.cells[i].width = Cm(w)


def para(doc_or_cell, text="", size=11, bold=False, color=INK, align=None, space_after=4, italic=False, font=None):
    p = doc_or_cell.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.bold = bold
    r.italic = italic
    r.font.color.rgb = color
    if font:
        r.font.name = font
        r._element.rPr.rFonts.set(qn("w:eastAsia"), font)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(0)
    if align:
        p.alignment = align
    return p


def cell_text(cell, text, size=10, bold=False, color=INK):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.bold = bold
    r.font.color.rgb = color
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP


def heading(doc, text, size=15, space_before=0):
    p = para(doc, text, size=size, bold=True, color=INK, space_after=6, font="Cambria")
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.keep_with_next = True
    return p


def sign_block(doc, label="Guide signature"):
    t = doc.add_table(rows=1, cols=3)
    set_widths(t, [6.0, 5.5, 5.5])
    for c, txt in zip(t.rows[0].cells, [f"{label}:", "Date:", "Remarks (if any):"]):
        cell_text(c, txt, size=10, bold=True, color=SLATE)
    t.rows[0].height = Cm(1.3)
    borders(t, color="C5CED8")


def main():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.orientation = WD_ORIENT.PORTRAIT
    sec.left_margin = sec.right_margin = Cm(2.0)
    sec.top_margin, sec.bottom_margin = Cm(2.0), Cm(1.8)
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(11)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")

    # footer with page number
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = fp.add_run("Research Work Diary  |  Piush Kole, Thrilok M  |  Page ")
    r.font.size = Pt(9)
    r.font.color.rgb = SLATE
    for tag, txt in (("begin", None), (None, "PAGE"), ("end", None)):
        run = fp.add_run()
        run.font.size = Pt(9)
        run.font.color.rgb = SLATE
        if tag:
            f = OxmlElement("w:fldChar")
            f.set(qn("w:fldCharType"), tag)
            run._r.append(f)
        else:
            it = OxmlElement("w:instrText")
            it.set(qn("xml:space"), "preserve")
            it.text = txt
            run._r.append(it)

    # ---------------- cover ----------------
    for _ in range(3):
        para(doc, "", space_after=12)
    para(doc, "CHRIST UNIVERSITY", size=14, bold=True, color=TEAL, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    para(doc, "Department of Computer Science", size=13, color=SLATE, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=36)
    para(doc, "RESEARCH WORK DIARY", size=28, bold=True, color=INK, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6, font="Cambria")
    para(doc, "Research Implementation, Review 1", size=14, color=SLATE, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=36)
    para(doc, "Project title", size=11, bold=True, color=TEAL, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    para(doc, "Synthetic Silence 2.0", size=20, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2, font="Cambria")
    para(doc, TITLE, size=12, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=36, italic=True)
    t = doc.add_table(rows=len(AUTHORS) + 1, cols=2)
    set_widths(t, [5.0, 12.0])
    for i, (n, e) in enumerate(AUTHORS):
        cell_text(t.rows[i].cells[0], "Student" if i == 0 else "Student", size=11, bold=True, color=SLATE)
        cell_text(t.rows[i].cells[1], f"{n}    {e}", size=11)
    cell_text(t.rows[-1].cells[0], "Research guide", size=11, bold=True, color=SLATE)
    cell_text(t.rows[-1].cells[1], "", size=11)
    for row in t.rows:
        row.height = Cm(1.0)
    borders(t, color="C5CED8")
    para(doc, "", space_after=24)
    sign_block(doc, "Guide signature")
    doc.add_page_break()

    # ---------------- project summary ----------------
    heading(doc, "1. Project summary")
    para(doc, "People read answers written by language models in their web browser, where a specific falsehood looks like a specific fact. "
              "This project builds and validates an audit that splits an answer into claims, retrieves sources, records what each source says about "
              "each claim together with a verbatim quote, and maps these per-source stances to one of five verdicts by deterministic rules.", space_after=6)
    heading(doc, "Objectives", size=12)
    for o in [
        "A verdict procedure over per-source stances with a verbatim quote requirement and five outcomes.",
        "Proofs of five properties of the rules and of two scores from earlier work, each checked against the code.",
        "A validation on FEVER with confusion matrices, Wilson intervals and paired exact tests.",
        "Explicit failure semantics: an outage is an error for that claim, never an empty result.",
        "A working Chrome extension on a FastAPI backend, and a cross-model audit protocol.",
    ]:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(2)
        rr = p.add_run(o)
        rr.font.size = Pt(11)
    heading(doc, "Where the work stands", size=12, space_before=8)
    para(doc, "The extension and backend work and are tested (backend 117, extension 44 unit tests and 35 real-Chrome end-to-end checks). "
              "On 100 balanced FEVER claims, Wikipedia retrieval raised accuracy on SUPPORTS and REFUTES claims from 66.7% to 79.7% (paired p = 0.064), "
              "a pooled entailment score never abstained, and a first per-source variant abstained but was significantly worse on decisive claims. "
              "The cross-model audit is specified and tested but has not been run.", space_after=6)

    # ---------------- weekly logs ----------------
    for wi, (label, intro, rows) in enumerate(WEEKS, start=1):
        doc.add_page_break() if wi > 0 else None
        heading(doc, f"{wi + 1}. {label}")
        para(doc, intro, size=10, italic=True, color=SLATE, space_after=6)
        tbl = doc.add_table(rows=1, cols=3)
        hdr = tbl.rows[0]
        for c, txt in zip(hdr.cells, ["Date", "Work done", "Evidence in the repository"]):
            cell_text(c, txt, size=10, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
            shade(c, "0F1B2D")
        repeat_header(hdr)
        for d, w, e in rows:
            row = tbl.add_row()
            no_split(row)
            cell_text(row.cells[0], d, size=10, bold=True)
            cell_text(row.cells[1], w, size=10)
            cell_text(row.cells[2], e, size=9, color=SLATE)
        set_widths(tbl, [2.4, 9.8, 4.8])
        borders(tbl)
        para(doc, "", space_after=0, size=6)
        heading(doc, "Guide meeting and remarks for this period", size=11)
        mt = doc.add_table(rows=3, cols=2)
        set_widths(mt, [4.0, 13.0])
        for r_, lbl in zip(mt.rows, ["Meeting date", "Points discussed", "Guide remarks"]):
            cell_text(r_.cells[0], lbl, size=10, bold=True, color=SLATE)
            r_.height = Cm(1.0)
        borders(mt, color="C5CED8")
        para(doc, "", space_after=0, size=6)
        sign_block(doc, "Guide signature")

    # ---------------- challenges and plan ----------------
    doc.add_page_break()
    heading(doc, f"{len(WEEKS) + 2}. Problems met and how they were handled")
    ct = doc.add_table(rows=1, cols=2)
    for c, txt in zip(ct.rows[0].cells, ["Problem", "What we did"]):
        cell_text(c, txt, size=10, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
        shade(c, "0F1B2D")
    for a, b in CHALLENGES:
        row = ct.add_row()
        no_split(row)
        cell_text(row.cells[0], a, size=10)
        cell_text(row.cells[1], b, size=10)
    set_widths(ct, [8.0, 9.0])
    borders(ct)
    para(doc, "", space_after=8)
    heading(doc, f"{len(WEEKS) + 3}. Plan before Research Implementation Review 2")
    for i, item in enumerate(PLAN, 1):
        p = doc.add_paragraph(style="List Number")
        p.paragraph_format.space_after = Pt(3)
        rr = p.add_run(item)
        rr.font.size = Pt(11)
    para(doc, "", space_after=10)
    heading(doc, "Declaration and guide approval", size=12)
    para(doc, "We confirm that the entries above describe work carried out by us on this project.", size=10.5, space_after=10)
    dt = doc.add_table(rows=2, cols=3)
    set_widths(dt, [5.67, 5.67, 5.66])
    for c, txt in zip(dt.rows[0].cells, ["Piush Kole (signature)", "Thrilok M (signature)", "Research guide (signature, date)"]):
        cell_text(c, txt, size=10, bold=True, color=SLATE)
    dt.rows[1].height = Cm(2.0)
    borders(dt, color="C5CED8")

    doc.save(OUT)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
