"""Builds review1/SyntheticSilence_RI_Review1_Christ.pptx on the Christ University template.

Template = Synthetic_Silence_Final_Presentation.pptx (master, logo, footer band, Urbanist font are kept;
its 25 slides are removed). Everything added here is a native, editable shape, table or chart.
Numbers come from paper/journal/data.py and docs/VERDICT_EVALUATION.md; do not edit them here by hand.
"""
import copy
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE, PP_PLACEHOLDER
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT.parent / "Synthetic_Silence_Final_Presentation.pptx"
OUT = ROOT / "SyntheticSilence_RI_Review1_Christ.pptx"
ASSETS = ROOT / "assets"
FIGS = ROOT.parent / "paper" / "out" / "journal_figs"

FONT = "Urbanist"


def rgb(h):
    return RGBColor.from_string(h)


BLUE, GOLD, NAVY = "0C5394", "D2AE6C", "1A2332"
TINT, MUTED, WHITE = "EAF1F8", "5B6B80", "FFFFFF"
RED, GREEN, SLATE, PALEGOLD, GRID = "C0392B", "2E7D5B", "64748B", "F6EBD0", "D5DEE8"


def blend(a, b, t):
    fa = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
    fb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
    return "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(fa, fb))


# ---------------------------------------------------------------- text helpers
def fill_tf(tf, paras, size=14, color=NAVY, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
            margins=(0, 0, 0, 0)):
    """paras: list of str | dict(t=str|[(text, overrides)], size, color, bold, italic, align, bullet, after, before)."""
    tf.word_wrap = True
    tf.auto_size = None
    tf.vertical_anchor = anchor
    tf.margin_left, tf.margin_top, tf.margin_right, tf.margin_bottom = [Inches(m) for m in margins]
    first = True
    for p in paras:
        if isinstance(p, str):
            p = {"t": p}
        para = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        para.alignment = p.get("align", align)
        if "after" in p:
            para.space_after = Pt(p["after"])
        if "before" in p:
            para.space_before = Pt(p["before"])
        runs = p["t"] if isinstance(p["t"], list) else [(p["t"], {})]
        for text, ov in runs:
            r = para.add_run()
            r.text = text
            f = r.font
            f.name = FONT
            f.size = Pt(ov.get("size", p.get("size", size)))
            f.bold = ov.get("bold", p.get("bold", bold))
            f.italic = ov.get("italic", p.get("italic", False))
            f.color.rgb = rgb(ov.get("color", p.get("color", color)))
        if p.get("bullet"):
            pPr = para._p.get_or_add_pPr()
            pPr.set("marL", "200000")
            pPr.set("indent", "-200000")
            bu = etree.SubElement(pPr, qn("a:buChar"))
            bu.set("char", "•")


def tb(slide, x, y, w, h, paras, name=None, **kw):
    s = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        s.name = name
    fill_tf(s.text_frame, paras if isinstance(paras, list) else [paras], **kw)
    return s


def box(slide, x, y, w, h, fill, paras=None, name=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.07,
        line=None, margins=(0.2, 0.12, 0.2, 0.12), **kw):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        s.name = name
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    s.shadow.inherit = False
    s.fill.solid()
    s.fill.fore_color.rgb = rgb(fill)
    if line:
        s.line.color.rgb = rgb(line[0])
        s.line.width = Pt(line[1])
        if len(line) > 2:
            s.line.dash_style = line[2]
    else:
        s.line.fill.background()
    if paras is not None:
        fill_tf(s.text_frame, paras if isinstance(paras, list) else [paras], margins=margins, **kw)
    return s


def badge(slide, x, y, d, text, fill=GOLD, color=NAVY, size=16, name=None):
    return box(slide, x, y, d, d, fill, [{"t": text, "bold": True, "size": size, "color": color, "align": PP_ALIGN.CENTER}],
               name=name, shape=MSO_SHAPE.OVAL, margins=(0, 0, 0, 0), anchor=MSO_ANCHOR.MIDDLE)


def arrow(slide, x, y, w, h, color=GOLD, name="arrow"):
    s = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x), Inches(y), Inches(w), Inches(h))
    s.name = name
    s.shadow.inherit = False
    s.fill.solid()
    s.fill.fore_color.rgb = rgb(color)
    s.line.fill.background()
    return s


# ---------------------------------------------------------------- table helpers
def _border(cell, color=GRID, w=6350):
    tcPr = cell._tc.get_or_add_tcPr()
    for i, tag in enumerate(("a:lnL", "a:lnR", "a:lnT", "a:lnB")):
        for old in tcPr.findall(qn(tag)):
            tcPr.remove(old)
        ln = etree.Element(qn(tag), w=str(w), cap="flat", cmpd="sng", algn="ctr")
        sf = etree.SubElement(ln, qn("a:solidFill"))
        etree.SubElement(sf, qn("a:srgbClr"), val=color)
        etree.SubElement(ln, qn("a:prstDash"), val="solid")
        tcPr.insert(i, ln)


def put(cell, text, size=13, bold=False, color=NAVY, fill=WHITE, align=PP_ALIGN.LEFT, border=GRID,
        margins=(0.1, 0.04, 0.1, 0.04)):
    cell.fill.solid()
    cell.fill.fore_color.rgb = rgb(fill)
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    cell.margin_left, cell.margin_top, cell.margin_right, cell.margin_bottom = [Inches(m) for m in margins]
    tf = cell.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text
    r.font.name, r.font.size, r.font.bold = FONT, Pt(size), bold
    r.font.color.rgb = rgb(color)
    _border(cell, border)


def table(slide, x, y, colw, rowh, name):
    gf = slide.shapes.add_table(len(rowh), len(colw), Inches(x), Inches(y), Inches(sum(colw)), Inches(sum(rowh)))
    gf.name = name
    t = gf.table
    for i, w in enumerate(colw):
        t.columns[i].width = Inches(w)
    for i, h in enumerate(rowh):
        t.rows[i].height = Inches(h)
    tblPr = t._tbl.tblPr
    for a in ("bandRow", "firstRow"):
        tblPr.set(a, "0")
    return t


def head_row(t, labels, size=13, aligns=None):
    for j, lab in enumerate(labels):
        put(t.cell(0, j), lab, size=size, bold=True, color=NAVY, fill=GOLD, border=WHITE,
            align=(aligns[j] if aligns else PP_ALIGN.LEFT))


# ---------------------------------------------------------------- deck scaffolding
prs = Presentation(str(TEMPLATE))
lst = prs.slides._sldIdLst
for sid in list(lst):
    prs.part.drop_rel(sid.rId)
    lst.remove(sid)

L_TITLE, L_TITLE_ONLY, L_BLANK = prs.slide_layouts[0], prs.slide_layouts[4], prs.slide_layouts[10]


def add_number(slide, layout):
    for ph in layout.placeholders:
        if ph.placeholder_format.type == PP_PLACEHOLDER.SLIDE_NUMBER:
            slide.shapes._spTree.append(copy.deepcopy(ph._element))


def content(title, notes):
    s = prs.slides.add_slide(L_TITLE_ONLY)
    t = s.shapes.title
    t.left, t.top, t.width, t.height = Inches(0.45), Inches(0.42), Inches(12.4), Inches(0.8)
    fill_tf(t.text_frame, [{"t": title.upper(), "size": 28, "bold": True, "color": GOLD}], anchor=MSO_ANCHOR.MIDDLE)
    add_number(s, L_TITLE_ONLY)
    s.notes_slide.notes_text_frame.text = notes
    return s


def bullets(items, size=14, color=NAVY, after=5, bold=False):
    return [{"t": t, "bullet": True, "size": size, "color": color, "after": after, "bold": bold} for t in items]


def card(slide, x, y, w, h, kind, paras, name, **kw):
    fills = {"light": TINT, "blue": BLUE, "dark": NAVY, "red": RED, "gold": PALEGOLD}
    return box(slide, x, y, w, h, fills[kind], paras, name=name, **kw)


def hd(text, kind="light", size=16):
    return {"t": text, "bold": True, "size": size, "color": {"light": BLUE, "gold": BLUE}.get(kind, GOLD), "after": 4}


# ================================================================ 1. title
s = prs.slides.add_slide(L_TITLE)
ph = {p.placeholder_format.idx: p for p in s.placeholders}
tb(s, 0.45, 1.72, 12.4, 0.4, [{"t": "RESEARCH IMPLEMENTATION REVIEW 1", "size": 16, "bold": True, "color": BLUE,
                              "align": PP_ALIGN.CENTER}], name="Review label")
ph[0].left, ph[0].top, ph[0].width, ph[0].height = Inches(0.45), Inches(2.1), Inches(12.4), Inches(0.95)
fill_tf(ph[0].text_frame, [{"t": "SYNTHETIC SILENCE 2.0", "size": 48, "bold": True, "color": GOLD, "align": PP_ALIGN.CENTER}],
        anchor=MSO_ANCHOR.MIDDLE)
ph[1].left, ph[1].top, ph[1].width, ph[1].height = Inches(1.4), Inches(3.05), Inches(10.5), Inches(0.95)
fill_tf(ph[1].text_frame, [{"t": "Auditing language-model answers against sources: deterministic verdict rules, "
                                  "provable properties and a validation on FEVER",
                            "size": 19, "bold": True, "color": BLUE, "align": PP_ALIGN.CENTER}], anchor=MSO_ANCHOR.TOP)
chips = [("supported", GREEN, WHITE), ("refuted", RED, WHITE), ("mixed", GOLD, NAVY), ("insufficient", SLATE, WHITE)]
x0 = (13.333 - (4 * 1.65 + 3 * 0.15)) / 2
for i, (t, col, tc) in enumerate(chips):
    box(s, x0 + i * 1.8, 4.1, 1.65, 0.4, col, [{"t": t, "size": 13, "bold": True, "color": tc, "align": PP_ALIGN.CENTER}],
        name="Verdict chip " + t, radius=0.5, anchor=MSO_ANCHOR.MIDDLE, margins=(0, 0, 0, 0))
tb(s, 0.45, 4.7, 12.4, 0.4, [{"t": "Piush Kole (2548421)   |   Thrilok M (2548430)", "size": 20, "bold": True, "color": BLUE,
                             "align": PP_ALIGN.CENTER}], name="Authors")
tb(s, 0.45, 5.15, 12.4, 0.4, [{"t": "Guided by: Dr. Deepa BG.", "size": 18, "bold": True, "color": BLUE,
                              "align": PP_ALIGN.CENTER}], name="Guide")
tb(s, 0.45, 5.6, 12.4, 0.35, [{"t": "Department of Computer Science, Christ University", "size": 14, "color": MUTED,
                              "align": PP_ALIGN.CENTER}], name="Department")
add_number(s, L_TITLE)
s.notes_slide.notes_text_frame.text = (
    "About 30 seconds. Introduce the team and the one-line idea: we turn an LLM answer into per-claim verdicts, and every "
    "true or false verdict points to a quoted sentence in a source. Today: problem, literature, method, statistics, "
    "implementation, results, comparison.")

# ================================================================ 2. problem
s = content("The problem: no way to check an LLM answer",
            "About 1 minute. Three points. One: fluent specifics look true. Two: the reader has no marker. Three: when a checker "
            "fails silently, silence looks like 'no problem found'. Our problem statement is the dark box: per-claim verdict, "
            "traceable to a quote, with failure kept separate from absence.")
probs = [("1", "Fluent and specific", "Names, dates and figures make an invented fact look like a recalled one."),
         ("2", "No marker", "A reader cannot tell recall from invention. Larger models can repeat common misconceptions "
                            "more often (Lin et al., 2022)."),
         ("3", "Silence on failure", "A failed search, a missing source and a disagreeing source must not look like the "
                                     "same outcome.")]
for i, (n, head, body) in enumerate(probs):
    x = 0.6 + i * 4.1
    card(s, x, 1.45, 3.9, 3.3, "light", [hd(head, size=19), {"t": body, "size": 15}], "Problem card " + n,
         margins=(0.3, 1.05, 0.3, 0.2))
    badge(s, x + 0.3, 1.7, 0.7, n, name="Problem number " + n, size=22)
card(s, 0.6, 5.0, 12.1, 1.75, "dark",
     [{"t": "PROBLEM STATEMENT", "bold": True, "size": 14, "color": GOLD, "after": 4},
      {"t": "Given an answer written by a language model, return one verdict per claim that a reader can trace to a quoted "
            "sentence in a source, and keep “no evidence” apart from “the check failed”.",
       "size": 19, "color": WHITE}], "Problem statement", anchor=MSO_ANCHOR.MIDDLE, margins=(0.35, 0.1, 0.35, 0.1))

# ================================================================ 3. objectives
s = content("Objectives and research questions",
            "About 1 minute. Five objectives map to the five contributions in the paper. The three research questions on the "
            "right are answered later by the FEVER validation and by the propositions: RQ1 and RQ2 empirically, RQ3 by proof "
            "plus the earlier study.")
objs = [("1", "Verdict procedure", "Per-source stances with a verbatim quote; five outcomes."),
        ("2", "Provable properties", "Prove them for the rules and two earlier scores; check against the code."),
        ("3", "Validation on FEVER", "Confusion matrices, Wilson intervals, paired exact tests."),
        ("4", "Explicit failure", "An outage is an error for that claim, never “no sources”."),
        ("5", "Working tool", "Chrome extension on a FastAPI backend, plus a cross-model audit protocol.")]
for i, (n, head, body) in enumerate(objs):
    y = 1.5 + i * 1.04
    badge(s, 0.6, y + 0.1, 0.68, n, fill=BLUE, color=WHITE, size=20, name="Objective number " + n)
    tb(s, 1.55, y, 6.3, 0.9, [{"t": head, "bold": True, "size": 18, "color": BLUE, "after": 1},
                             {"t": body, "size": 14, "color": MUTED}], name="Objective " + n, anchor=MSO_ANCHOR.MIDDLE)
card(s, 8.2, 1.5, 4.5, 5.15, "dark",
     [{"t": "RESEARCH QUESTIONS", "bold": True, "size": 18, "color": GOLD, "after": 12},
      {"t": [("RQ1  ", {"bold": True, "color": GOLD}), ("Does the retrieval source or the aggregation rule matter more for "
                                                       "decisive claims?", {})], "size": 16, "color": WHITE, "after": 14},
      {"t": [("RQ2  ", {"bold": True, "color": GOLD}), ("Can a pooled entailment score abstain when sources do not mention a "
                                                       "claim?", {})], "size": 16, "color": WHITE, "after": 14},
      {"t": [("RQ3  ", {"bold": True, "color": GOLD}), ("Does a density or entropy score track whether evidence supports a "
                                                       "claim?", {})], "size": 16, "color": WHITE}],
     "Research questions", margins=(0.3, 0.3, 0.3, 0.2))

# ================================================================ 4. literature
s = content("Literature survey and existing work",
            "About 1.5 minutes. Walk down the table. The survey gives the pipeline. FEVER and AVeriTeC give labelled data. "
            "SelfCheckGPT and FActScore are the closest work on LLM factuality: one uses no evidence, the other returns a score. "
            "None returns a verdict with a quote the reader can find. The last row is our own earlier study, which motivates the "
            "change of approach on the next slide. LLM-as-judge bias (Zheng et al., 2023) is why we hold the checker fixed.")
lit = [("Guo et al., 2022", "Survey: claim detection, retrieval, verdict, justification", "Pipeline view; no deployed audit"),
       ("Thorne et al., 2018 (FEVER)", "Wikipedia claims labelled SUPPORTS, REFUTES, NEI", "Fixed corpus; claims given, not extracted"),
       ("Schlichtkrull et al., 2023 (AVeriTeC)", "Real-world claims with open-web evidence", "A dataset, not a reader-facing verdict"),
       ("Manakul et al., 2023 (SelfCheckGPT)", "Flags hallucination by sampling consistency, no evidence", "No source sentence to show the reader"),
       ("Min et al., 2023 (FActScore)", "Share of atomic facts a knowledge source supports", "A score, not a quote-backed verdict"),
       ("Ji et al., 2023; Lin et al., 2022", "Hallucination survey; TruthfulQA misconceptions", "Shows the need, not a tool"),
       ("Our earlier study", "Density signal: AUROC 0.546 on FEVER, 0.275 on AVeriTeC", "Does not track support, hence this work")]
t = table(s, 0.6, 1.45, [3.6, 4.8, 3.7], [0.5] + [0.66] * 7, "Literature table")
head_row(t, ["Work", "What it does", "Gap for a reader-side audit"], size=14)
for i, row in enumerate(lit):
    for j, c in enumerate(row):
        put(t.cell(i + 1, j), c, size=13, bold=(j == 0), fill=PALEGOLD if i == 6 else (WHITE if i % 2 == 0 else TINT))

# ================================================================ 5. gap chart
s = content("Research gap: the density signal did not generalise",
            "About 1 minute. This is the research gap, from our own earlier work. The density signal had AUROC 0.546 on FEVER, "
            "which is weak, then 0.275 on AVeriTeC, which is inverted, and 0.335 even with matched controls. Cross-manifold tests "
            "collapsed to chance. So a density score is not a safe basis for telling a reader whether a claim is supported. We keep "
            "it in research mode and build the verdict from source stance.")


def style_axes(chart, vmax, unit, fmt, lab=12):
    chart.font.name, chart.font.size = FONT, Pt(lab)
    chart.font.color.rgb = rgb(NAVY)
    va = chart.value_axis
    va.minimum_scale, va.maximum_scale, va.major_unit = 0, vmax, unit
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = rgb(GRID)
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(lab)
    va.tick_labels.font.color.rgb = rgb(MUTED)
    va.tick_labels.number_format = fmt
    va.tick_labels.number_format_is_linked = False
    ca = chart.category_axis
    ca.has_major_gridlines = False
    ca.format.line.color.rgb = rgb(GRID)
    ca.tick_labels.font.size = Pt(lab)


def chart_title(chart, text):
    chart.has_title = True
    tf = chart.chart_title.text_frame
    tf.text = text
    r = tf.paragraphs[0].runs[0]
    r.font.name, r.font.size, r.font.bold = FONT, Pt(14), True
    r.font.color.rgb = rgb(BLUE)
    chart.chart_title.include_in_layout = False


cd = CategoryChartData()
cd.categories = ["FEVER (E0)", "AVeriTeC overall", "AVeriTeC insufficiency", "Matched controls (F2)", "Chance level"]
cd.add_series("AUROC", [0.546, 0.355, 0.275, 0.335, 0.5])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.45), Inches(7.0), Inches(5.35), cd)
gf.name = "AUROC chart"
ch = gf.chart
ch.has_legend = False
style_axes(ch, 1.0, 0.25, "0.00")
chart_title(ch, "AUROC of the density signal for evidence insufficiency")
pl = ch.plots[0]
pl.gap_width = 55
pl.vary_by_categories = False
for i, col in enumerate([BLUE, RED, RED, RED, SLATE]):
    pt = pl.series[0].points[i]
    pt.format.fill.solid()
    pt.format.fill.fore_color.rgb = rgb(col)
pl.has_data_labels = True
dl = pl.data_labels
dl.number_format, dl.number_format_is_linked = "0.000", False
dl.position = XL_LABEL_POSITION.OUTSIDE_END
dl.font.size, dl.font.bold, dl.font.name = Pt(13), True, FONT
card(s, 7.95, 1.45, 4.75, 1.65, "light",
     [hd("Reading the chart"), {"t": "Below 0.5 means the signal points the wrong way. Cross-manifold tests fell to chance.",
                                "size": 14}], "Reading card", anchor=MSO_ANCHOR.MIDDLE)
card(s, 7.95, 3.3, 4.75, 3.5, "dark",
     [{"t": "WHAT WE DO INSTEAD", "bold": True, "size": 15, "color": GOLD, "after": 8}]
     + bullets(["Read what each source says about the claim", "Require a verbatim quote for every counted source",
                "Decide with deterministic rules we can prove things about",
                "Keep density and entropy as research-mode signals only"], size=14, color=WHITE, after=7),
     "Approach card", margins=(0.3, 0.25, 0.25, 0.15))

# ================================================================ 6. method
s = content("Methodology: from answer to traceable verdict",
            "About 1.5 minutes. Walk left to right. Extraction keeps names, numbers and dates as written. Two retrievers run "
            "together. Ranking uses sentence-embedding cosine similarity and keeps six. The stance call returns one stance, a "
            "confidence and a quote per source; a stance without a verbatim quote is downgraded to neutral. Then five "
            "deterministic rules. The dashed box is the earlier research signal, shown only in research mode. The red box is the "
            "failure rule: outage is an error, not silence.")
steps = [("1", "Extract", "LLM splits the answer into self-contained claims"),
         ("2", "Retrieve", "Wikipedia and OpenAlex, merged and deduplicated"),
         ("3", "Rank", "Cosine similarity to the claim; keep the top 6"),
         ("4", "Stance", "Per source: supports, refutes, neutral, irrelevant, plus a quote"),
         ("5", "Verdict", "Rules R1 to R5 over counted sources"),
         ("6", "Show", "Side panel: sources, quotes, page highlights")]
bw, gap = 1.8, 0.262
for i, (n, head, body) in enumerate(steps):
    x = 0.6 + i * (bw + gap)
    card(s, x, 1.5, bw, 3.25, "blue",
         [{"t": head, "bold": True, "size": 18, "color": GOLD, "after": 6}, {"t": body, "size": 14, "color": WHITE}],
         "Step card " + n, margins=(0.18, 0.95, 0.15, 0.1))
    badge(s, x + 0.18, 1.7, 0.62, n, name="Step number " + n, size=20)
    if i < 5:
        arrow(s, x + bw + 0.03, 3.0, gap - 0.06, 0.3, name="Arrow " + n)
box(s, 0.6, 5.0, 5.95, 1.75, WHITE,
    [{"t": "Research mode only", "bold": True, "size": 16, "color": MUTED, "after": 4},
     {"t": "Density ρ (kNN plus Mahalanobis) and entropy U are computed beside the verdict, marked NOT CALIBRATED, "
           "and never decide it.", "size": 14}],
    name="Research mode box", line=(MUTED, 1.5, 4), anchor=MSO_ANCHOR.MIDDLE, margins=(0.3, 0.1, 0.3, 0.1))
card(s, 6.75, 5.0, 5.95, 1.75, "red",
     [{"t": "Failure semantics", "bold": True, "size": 16, "color": WHITE, "after": 4},
      {"t": "If every retriever fails, or the stream drops, that claim is an error with a retry. It is never shown as "
            "“no sources”.", "size": 14, "color": WHITE}],
     "Failure semantics box", anchor=MSO_ANCHOR.MIDDLE, margins=(0.3, 0.1, 0.3, 0.1))

# ================================================================ 7. verdict rules
s = content("Verdict rules: five outcomes from counted sources",
            "About 1 minute. Counted sets P and N need confidence at least 0.5 and a verified quote. Q says when a side qualifies: "
            "two counted sources, or one with confidence 0.8. The five rules are tried in order. The figure shows the regions. "
            "The practical point: a single weak source can never produce 'supported'.")
card(s, 0.6, 1.45, 6.9, 1.6, "light",
     [{"t": "P: sources that support, confidence ≥ 0.5, quote verified in the source", "size": 14, "after": 3},
      {"t": "N: sources that refute, same tests", "size": 14, "after": 3},
      {"t": "Q(T): |T| ≥ 2, or |T| = 1 with confidence ≥ 0.8", "size": 14, "bold": True, "color": BLUE}],
     "Definitions card", anchor=MSO_ANCHOR.MIDDLE, margins=(0.25, 0.1, 0.2, 0.1))
t = table(s, 0.6, 3.3, [0.85, 4.05, 2.0], [0.5] + [0.58] * 5, "Rules table")
head_row(t, ["Rule", "Condition (first that applies)", "Verdict"], size=14)
rules = [("R1", "no sources retrieved (n = 0)", "no sources", SLATE, WHITE),
         ("R2", "P and N both non-empty, and Q(P) or Q(N)", "mixed", GOLD, NAVY),
         ("R3", "Q(P)", "supported", GREEN, WHITE),
         ("R4", "Q(N)", "refuted", RED, WHITE),
         ("R5", "otherwise", "insufficient", SLATE, WHITE)]
for i, (r, c, v, col, tc) in enumerate(rules):
    put(t.cell(i + 1, 0), r, size=14, bold=True)
    put(t.cell(i + 1, 1), c, size=13)
    put(t.cell(i + 1, 2), v, size=14, bold=True, color=tc, fill=col, align=PP_ALIGN.CENTER)
pic = s.shapes.add_picture(str(FIGS / "regions.png"), Inches(7.8), Inches(1.45), width=Inches(4.9))
pic.name = "Verdict regions figure"
pic._element.nvPicPr.cNvPr.set("descr", "Verdict regions by number of counted supporting sources and strongest confidence")
tb(s, 7.8, 1.45 + pic.height / 914400 + 0.05, 4.9, 0.75,
   "Verdict by number of counted supporting sources and strongest confidence, no counted refutation. One source qualifies "
   "only at confidence 0.8 or more.", size=11, color=MUTED, name="Figure caption")
card(s, 7.8, 5.95, 4.9, 0.8, "dark",
     [{"t": "Why: one weak source cannot say “backed up”", "bold": True, "size": 15, "color": WHITE}],
     "Why callout", anchor=MSO_ANCHOR.MIDDLE, margins=(0.25, 0.05, 0.2, 0.05))

# ================================================================ 8. statistical concepts
s = content("Statistical and data-science concepts applied",
            "About 1 minute. Eight tools, two groups. The top row is the modelling side: cosine ranking, kNN plus Mahalanobis "
            "density with Ledoit-Wolf shrinkage, and softmax entropy. The bottom row is the evaluation side: confusion matrix "
            "with macro-F1, Wilson intervals, exact McNemar test on paired claims, and a paired bootstrap, with a Bonferroni "
            "threshold of 0.0083 because we ran six comparisons.")
stats = [("Cosine similarity", "Ranks sources by closeness to the claim; keeps the top 6."),
         ("kNN + Mahalanobis", "Distance of a claim from 10,000 FEVER claim embeddings (research mode)."),
         ("Ledoit–Wolf shrinkage", "Stabilises the covariance; condition number ≤ 1 + (1−δ)p/δ."),
         ("Softmax entropy U", "Evenness of source matches (τ = 0.1); high when many match alike."),
         ("Confusion, macro-F1", "Per-class precision and recall; abstention shown as NEI recall."),
         ("Wilson 95% interval", "Honest error bars for proportions at n = 100 (about ±10 points)."),
         ("Exact McNemar test", "Paired test on discordant claims; every variant sees the same 100 claims."),
         ("Paired bootstrap", "4,000 resamples for each difference; Bonferroni across six tests.")]
for i, (head, body) in enumerate(stats):
    x, y = 0.6 + (i % 4) * 3.07, 1.45 + (i // 4) * 2.7
    kind = "blue" if i < 4 else "light"
    card(s, x, y, 2.95, 2.5, kind,
         [{"t": ["MODELLING", "EVALUATION"][i // 4], "size": 10, "bold": True, "color": GOLD if kind == "blue" else MUTED, "after": 4},
          hd(head, kind, 16), {"t": body, "size": 13, "color": WHITE if kind == "blue" else NAVY}],
         "Concept card " + str(i + 1), margins=(0.22, 0.2, 0.2, 0.1))

# ================================================================ 9. properties
s = content("Five properties, proved and checked against code",
            "About 1 minute. Each property is proved in the paper. Theorem 1 is the audit property: the system cannot assert true, "
            "false or disputed without a quote in a source. Props 2 to 4 explain why the earlier scores behave as they do: entropy "
            "rewards redundancy, and the single-query density collapses to a nearest-neighbour distance. We also test every "
            "statement against the deployed code, so the proofs and the code cannot drift apart. These checks are not proofs; "
            "they are drift alarms.")
props = [("Theorem 1", "Verdict rules", "Exhaustive, exclusive, order-invariant, symmetric, monotone. Every true, false or mixed verdict has a verified quote."),
         ("Prop. 2", "Entropy U", "Non-decreasing in τ, and U ≥ 1 − δ/(τ ln N): many sources matching alike give high U, agree or not."),
         ("Prop. 3", "Single-query density", "With one query, ρ ≈ (kNN distance + 1)/2, so the Mahalanobis term cannot change an AUROC."),
         ("Prop. 4", "Shrinkage", "Shrunk covariance is positive definite, with condition number ≤ 1 + (1−δ)p/δ."),
         ("Prop. 5", "Wilson interval", "The Wilson limits form one interval inside [0, 1] that contains the estimate.")]
for i, (tag, head, body) in enumerate(props):
    y = 1.45 + i * 1.04
    card(s, 0.6, y, 8.3, 0.94, "light", None, "Property card " + str(i + 1))
    box(s, 0.75, y + 0.21, 1.2, 0.52, BLUE, [{"t": tag, "bold": True, "size": 13, "color": WHITE, "align": PP_ALIGN.CENTER}],
        name="Tag " + tag, radius=0.2, anchor=MSO_ANCHOR.MIDDLE, margins=(0, 0, 0, 0))
    tb(s, 2.1, y + 0.04, 6.7, 0.86, [{"t": [(head + "  ", {"bold": True, "color": BLUE, "size": 14}), (body, {})], "size": 12.5}],
       name="Property text " + str(i + 1), anchor=MSO_ANCHOR.MIDDLE)
big = [("27,930", "source configurations tested exhaustively for Theorem 1"),
       ("15,000", "random configurations of 4 to 7 sources"),
       ("34", "paper tests pass; no counterexample found")]
for i, (num, label) in enumerate(big):
    y = 1.45 + i * 1.78
    card(s, 9.2, y, 3.5, 1.65, "dark",
         [{"t": num, "bold": True, "size": 36, "color": GOLD, "align": PP_ALIGN.CENTER, "after": 2},
          {"t": label, "size": 13, "color": WHITE, "align": PP_ALIGN.CENTER}],
         "Check stat " + str(i + 1), anchor=MSO_ANCHOR.MIDDLE, margins=(0.2, 0.05, 0.2, 0.05))

# ================================================================ 10. implementation
s = content("Implementation: Chrome extension and FastAPI backend",
            "About 1.5 minutes. Show the extension live if the review allows: paste text, press Ctrl+Enter, watch claims stream in. "
            "Left: real screenshot from our end-to-end run in real Chrome, with a stub backend so the output is deterministic. The "
            "demo claims show all three states: backed up, could not be checked because the search budget was used up, and no "
            "sources found. The last two are different states on purpose. Tests: backend 117, extension unit 44, and the "
            "real-Chrome end-to-end run. Live verdicts with the real model need OpenRouter credit.")
pic = s.shapes.add_picture(str(ASSETS / "shot_top.png"), Inches(0.6), Inches(1.45), height=Inches(4.85))
pic.name = "Extension screenshot"
pic._element.nvPicPr.cNvPr.set("descr", "Extension side panel with input box and verdict summary")
tb(s, 0.6, 6.35, 3.4, 0.5, "Real Chrome 155 run, stub backend with fixed demo data", size=10, color=MUTED, name="Screenshot caption")
colx = [4.25, 8.5]
heads = ["EXTENSION", "BACKEND"]
items = [["Popup and side panel", "Right-click or Alt+Shift+S on any text", "Claims stream in as each one finishes",
          "Highlight claims on the page, no DOM changes", "History, Markdown and JSON export"],
         ["FastAPI, NDJSON streaming", "Wikipedia and OpenAlex retrieval", "gpt-4o-mini at temperature 0, JSON repair and retry",
          "Result cache; typed API from OpenAPI", "Budget errors reported, not hidden"]]
for k in range(2):
    card(s, colx[k], 1.45, 4.1, 3.35, "light",
         [{"t": heads[k], "bold": True, "size": 16, "color": BLUE, "after": 8}] + bullets(items[k], size=13.5, after=5),
         heads[k].title() + " card", margins=(0.25, 0.2, 0.2, 0.1))
tests = [("117", "backend tests pass"), ("44", "extension unit tests pass"), ("35", "real-Chrome end-to-end checks pass")]
for i, (num, label) in enumerate(tests):
    card(s, 4.25 + i * 2.85, 5.05, 2.7, 1.7, "dark",
         [{"t": num, "bold": True, "size": 34, "color": GOLD, "align": PP_ALIGN.CENTER, "after": 1},
          {"t": label, "size": 12.5, "color": WHITE, "align": PP_ALIGN.CENTER}],
         "Test stat " + str(i + 1), anchor=MSO_ANCHOR.MIDDLE, margins=(0.1, 0.05, 0.1, 0.05))

# ================================================================ 11. confusion matrices
s = content("Results: confusion matrices on 100 FEVER claims",
            "About 1 minute. Same 100 claims for every variant; they come from the FEVER development split, balanced, seed 42. "
            "The baseline OpenAlex run scored 100 of 150 sampled claims because the anonymous OpenAlex budget ran out, so all "
            "variants are reported on those 100. Read the matrices by row. Pooled with Wikipedia gets the SUPPORTS and REFUTES "
            "rows mostly right but puts 25 of 31 NEI claims in REFUTES. The stance variant spreads NEI correctly but loses "
            "REFUTES: 13 of 36 called SUPPORTS.")
setup = [("100", "claims scored"), ("33 / 36 / 31", "SUPPORTS / REFUTES / NEI"), ("3", "variants, same claims"),
         ("seed 42", "gpt-4o-mini, temp 0")]
for i, (num, label) in enumerate(setup):
    card(s, 0.6 + i * 3.07, 1.4, 2.95, 1.05, "blue",
         [{"t": num, "bold": True, "size": 22, "color": GOLD, "align": PP_ALIGN.CENTER},
          {"t": label, "size": 12, "color": WHITE, "align": PP_ALIGN.CENTER}],
         "Setup chip " + str(i + 1), anchor=MSO_ANCHOR.MIDDLE, margins=(0.1, 0.03, 0.1, 0.03))
CONF = {"Pooled + OpenAlex (baseline)": [[15, 9, 9, 0], [3, 31, 2, 0], [2, 24, 5, 0]],
        "Pooled + Wikipedia": [[24, 8, 1, 0], [4, 31, 1, 0], [6, 25, 0, 0]],
        "Stance + Wikipedia (first prompt)": [[22, 2, 8, 1], [13, 12, 10, 1], [9, 3, 19, 0]]}
gold_lab, pred = ["SUPPORTS", "REFUTES", "NEI"], ["S", "R", "N", "M"]
for k, (name, m) in enumerate(CONF.items()):
    x = 0.6 + k * 4.1
    tb(s, x, 2.7, 3.9, 0.4, [{"t": name, "bold": True, "size": 15, "color": BLUE}], name="Matrix title " + str(k + 1))
    t = table(s, x, 3.15, [1.3, 0.65, 0.65, 0.65, 0.65], [0.5] + [0.72] * 3, "Confusion matrix " + str(k + 1))
    for j, lab in enumerate(["gold \\ pred"] + pred):
        put(t.cell(0, j), lab, size=12 if j == 0 else 14, bold=True, color=WHITE, fill=NAVY, align=PP_ALIGN.CENTER, border=WHITE)
    for i, row in enumerate(m):
        tot = sum(row)
        put(t.cell(i + 1, 0), gold_lab[i], size=12, bold=True, fill=TINT, border=WHITE)
        for j, v in enumerate(row):
            share = min(1, v / tot * 1.15)
            put(t.cell(i + 1, j + 1), str(v), size=17, bold=True, align=PP_ALIGN.CENTER, border=WHITE,
                fill=blend(WHITE, BLUE if i == j else RED, share), color=WHITE if share > 0.55 else NAVY)
tb(s, 0.6, 6.0, 12.1, 0.8,
   "Blue: correct cells. Red: wrong cells. Shade is the share of the gold row. S, R, N, M = SUPPORTS, REFUTES, NEI, MIXED. "
   "Rows sum to 33, 36, 31.", size=12, color=MUTED, name="Matrix legend")

# ================================================================ 12. results
s = content("Results and analysis: accuracy and abstention",
            "About 1.5 minutes. Overall accuracy is flat, between 51 and 55 percent, and the intervals overlap heavily; with 100 "
            "claims that is about plus or minus 10 points. The interesting differences are in the decisive claims and in "
            "abstention. Wikipedia retrieval lifts decisive accuracy from 66.7 to 79.7, but the paired test gives p = 0.064, so we "
            "call it suggestive, and FEVER is built from Wikipedia so a Wikipedia retriever is expected to help. The pooled score "
            "never says not enough info; the per-source variant does 61 percent of the time.")
cd = CategoryChartData()
cd.categories = ["Pooled + OpenAlex", "Pooled + Wikipedia", "Stance + Wikipedia"]
cd.add_series("Overall accuracy", [51.0, 55.0, 53.0])
cd.add_series("SUPPORTS/REFUTES accuracy", [66.7, 79.7, 49.3])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.4), Inches(5.7), Inches(4.2), cd)
gf.name = "Accuracy chart"
ch = gf.chart
style_axes(ch, 100, 25, "0", 11)
chart_title(ch, "Accuracy (%) on 100 FEVER claims")
ch.has_legend = True
ch.legend.position, ch.legend.include_in_layout = XL_LEGEND_POSITION.BOTTOM, False
ch.legend.font.size, ch.legend.font.name = Pt(11), FONT
pl = ch.plots[0]
pl.gap_width, pl.overlap = 60, -5
for ser, col in zip(pl.series, [SLATE, BLUE]):
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = rgb(col)
pl.has_data_labels = True
dl = pl.data_labels
dl.number_format, dl.number_format_is_linked = "0.0", False
dl.position = XL_LABEL_POSITION.OUTSIDE_END
dl.font.size, dl.font.bold, dl.font.name = Pt(12), True, FONT
t = table(s, 6.55, 1.45, [1.55, 1.5, 0.8, 1.5, 0.8], [0.5, 0.75, 0.75, 0.75], "Results table")
head_row(t, ["Variant", "Accuracy (95% CI)", "Macro-F1", "Decisive (95% CI)", "NEI recall"], size=12)
res = [("Pooled + OpenAlex", "51.0 (41.3–60.6)", "0.466", "66.7 (54.9–76.6)", "16.1%"),
       ("Pooled + Wikipedia", "55.0 (45.2–64.4)", "0.445", "79.7 (68.8–87.5)", "0.0%"),
       ("Stance + Wikipedia", "53.0 (43.3–62.5)", "0.528", "49.3 (37.8–60.8)", "61.3%")]
for i, row in enumerate(res):
    for j, c in enumerate(row):
        put(t.cell(i + 1, j), c, size=12, bold=(j == 0), fill=PALEGOLD if i == 1 else WHITE, margins=(0.07, 0.03, 0.07, 0.03))
tb(s, 6.55, 4.35, 6.15, 0.6, "Percent except macro-F1. Decisive = the 69 SUPPORTS and REFUTES claims.", size=11, color=MUTED,
   name="Table note")
for i, (num, label, col) in enumerate([("66.7 → 79.7%", "decisive accuracy with Wikipedia (suggestive, p = 0.064)", GOLD),
                                       ("0%  vs  61.3%", "NEI recall: pooled score vs stance variant", GOLD)]):
    x = 0.6 + i * 6.15
    card(s, x, 5.8, 5.95, 1.0, "dark", None, "Callout " + str(i + 1))
    tb(s, x + 0.2, 5.8, 2.75, 1.0, [{"t": num, "bold": True, "size": 22, "color": col}], name="Callout number " + str(i + 1),
       anchor=MSO_ANCHOR.MIDDLE)
    tb(s, x + 3.0, 5.8, 2.8, 1.0, [{"t": label, "size": 13, "color": WHITE}], name="Callout label " + str(i + 1),
       anchor=MSO_ANCHOR.MIDDLE)

# ================================================================ 13. comparative analysis
s = content("Comparative analysis",
            "About 1.5 minutes. Left: the paired comparisons, which are the fair way to compare variants on the same claims. Only "
            "one passes the Bonferroni threshold: the first stance prompt is worse than the pooled score on decisive claims. "
            "Wikipedia against OpenAlex is suggestive but not significant. Right: a design comparison with the two closest related "
            "methods. We do not claim better accuracy than them; we did not run them on the same data. The claim is about design: "
            "external evidence, claim-level unit, verdict with a quote.")
tb(s, 0.6, 1.4, 6.6, 0.4, [{"t": "Paired tests on the same claims (exact McNemar)", "bold": True, "size": 15, "color": BLUE}],
   name="Paired tests heading")
t = table(s, 0.6, 1.85, [1.15, 1.1, 1.3, 2.25, 0.8], [0.5] + [0.55] * 4, "Paired tests table")
head_row(t, ["A vs B", "Claims", "A only / B only", "Diff, points (95% CI)", "p"], size=12)
pt_rows = [("PW vs PO", "decisive 69", "14 / 5", "+13.0 (+1.4, +24.6)", "0.064", False),
           ("SW vs PW", "decisive 69", "5 / 26", "−30.4 (−44.9, −15.9)", "0.0002", True),
           ("SW vs PO", "decisive 69", "11 / 23", "−17.4 (−33.3, 0.0)", "0.058", False),
           ("SW vs PW", "all 100", "24 / 26", "−2.0 (−16.0, +12.0)", "0.888", False)]
for i, row in enumerate(pt_rows):
    for j in range(5):
        put(t.cell(i + 1, j), row[j], size=12, bold=(j == 0 or (row[5] and j == 4)), fill=PALEGOLD if row[5] else WHITE,
            margins=(0.07, 0.03, 0.07, 0.03))
tb(s, 0.6, 4.65, 6.6, 0.8,
   "PO pooled + OpenAlex; PW pooled + Wikipedia; SW stance + Wikipedia. Six tests were run; the Bonferroni threshold is "
   "0.0083, which only the shaded row meets.", size=11, color=MUTED, name="Paired tests note")
card(s, 0.6, 5.55, 6.6, 1.2, "blue",
     [{"t": "The aggregation rule changed decisive accuracy significantly only for the first stance prompt, and for the worse.",
       "bold": True, "size": 14, "color": WHITE}], "Comparison takeaway", anchor=MSO_ANCHOR.MIDDLE, margins=(0.3, 0.1, 0.3, 0.1))
tb(s, 7.5, 1.4, 5.2, 0.4, [{"t": "Design comparison with related audits", "bold": True, "size": 15, "color": BLUE}],
   name="Design comparison heading")
t = table(s, 7.5, 1.85, [1.25, 1.5, 1.2, 1.25], [0.5] + [0.62] * 3, "Design comparison table")
head_row(t, ["", "SelfCheckGPT", "FActScore", "This work"], size=12)
dc = [("External evidence", "No", "Yes", "Yes"), ("Unit checked", "Sentence", "Atomic fact", "Claim"),
      ("Output", "Consistency score", "Share supported", "Verdict plus quote")]
for i, row in enumerate(dc):
    for j, c in enumerate(row):
        put(t.cell(i + 1, j), c, size=12, bold=(j in (0, 3)), fill=PALEGOLD if j == 3 else WHITE, margins=(0.07, 0.03, 0.07, 0.03))
tb(s, 7.5, 4.35, 5.2, 0.9,
   "Not compared numerically: the methods use different data and tasks. We claim a difference in design, not in accuracy.",
   size=11, color=MUTED, name="Design comparison note")
card(s, 7.5, 5.3, 5.2, 1.45, "light",
     [hd("Against our earlier density signal", size=14),
      {"t": "AUROC 0.546 (FEVER) and 0.275 (AVeriTeC) there; here, verdicts that carry quotes.", "size": 13}],
     "Earlier work comparison", anchor=MSO_ANCHOR.MIDDLE, margins=(0.25, 0.1, 0.2, 0.1))

# ================================================================ 14. findings
s = content("Findings and failure diagnosis",
            "About 1 minute. Three findings, one admission. Retrieval source mattered; the pooled score cannot abstain; the first "
            "per-source prompt abstains but is worse on decisive claims. We inspected the 13 refuted claims called supported and "
            "found two causes that were ours: the stance call saw the normalised claim, and the prompt was too lenient. We fixed "
            "both and added a regression test, but a re-run on a fresh sample was cut off when the API account ran out of credit, "
            "so we draw no conclusion about the corrected prompt and keep pooled as the default.")
finds = [("+13.0 pts", "Retrieval source", "Wikipedia over OpenAlex on decisive claims. Suggestive (p = 0.064); FEVER is Wikipedia-derived."),
         ("0% recall", "Pooled score cannot abstain", "It called 25 of 31 NEI claims refuted. One score cannot split “not mentioned” from “contradicted”."),
         ("p = 0.0002", "First stance prompt", "Abstains (61.3% NEI recall) but is much worse on decisive claims than the pooled score.")]
for i, (num, head, body) in enumerate(finds):
    card(s, 0.6 + i * 4.1, 1.45, 3.9, 2.95, "light",
         [{"t": num, "bold": True, "size": 30, "color": BLUE, "after": 2}, hd(head, size=16), {"t": body, "size": 14}],
         "Finding card " + str(i + 1), margins=(0.28, 0.2, 0.25, 0.1))
card(s, 0.6, 4.65, 12.1, 2.1, "dark",
     [{"t": "FAILURE ANALYSIS: 13 of 36 REFUTES claims were called supported", "bold": True, "size": 16, "color": GOLD, "after": 6}]
     + bullets(["Cause 1: the stance call judged the normalised claim, which had dropped the detail that made it false.",
                "Cause 2: the prompt accepted near misses (1945 for 1946; a TV series for a radio station).",
                "Both fixed with a regression test. The corrected variant is not yet shown to beat pooled, so the default stays pooled."],
               size=14, color=WHITE, after=5),
     "Diagnosis card", anchor=MSO_ANCHOR.MIDDLE, margins=(0.35, 0.1, 0.3, 0.1))

# ================================================================ 15. conclusion
s = content("Conclusion, limits and next steps",
            "About 30 seconds. One-sentence conclusion first. Then be direct about the limits: small sample, Wikipedia-derived "
            "benchmark, corrected prompt not evaluated, cross-model audit built and tested but not run because of API credit. Next "
            "steps are concrete. Invite questions. Likely questions: why FEVER, why not a bigger sample, why keep the density "
            "score, how are quotes verified. Answers are in the paper: Sections 4, 5 and 6 and the Limitations section.")
tb(s, 0.6, 1.4, 12.1, 0.9, [{"t": "Every verdict traces to a quoted sentence, and absence is kept apart from failure.",
                            "bold": True, "size": 22, "color": BLUE}], name="Conclusion statement", anchor=MSO_ANCHOR.MIDDLE)
cols = [("LIMITS", RED, ["100 claims: intervals about ±10 points", "FEVER is Wikipedia-derived: compare variants, not absolutes",
                          "Corrected stance prompt not yet evaluated", "Cross-model audit specified, not run (API credit)"]),
        ("NEXT STEPS", BLUE, ["Evaluate the corrected prompt on a 150-claim fresh sample",
                              "Run the 40-prompt audit on seven commercial models (about US$1.6)",
                              "Compare verdicts with human judgements", "Fit the conformal calibration interface (not fitted today)"])]
for k, (head, col, its) in enumerate(cols):
    x = 0.6 + k * 6.15
    card(s, x, 2.5, 5.95, 3.9, "light", None, head.title() + " card")
    badge(s, x + 0.3, 2.78, 0.3, "", fill=col, name=head.title() + " marker")
    tb(s, x + 0.75, 2.7, 4.8, 0.45, [{"t": head, "bold": True, "size": 18, "color": col}], name=head.title() + " heading",
       anchor=MSO_ANCHOR.MIDDLE)
    tb(s, x + 0.3, 3.4, 5.4, 3.2, bullets(its, size=15, after=11), name=head.title() + " list")

# ================================================================ 16. references
s = content("References", "Not presented. Full bibliography is in the journal article.")
refs = [("Guo, Schlichtkrull and Vlachos (2022).", "A Survey on Automated Fact-Checking. TACL 10:178–206."),
        ("Thorne et al. (2018).", "FEVER: A Large-scale Dataset for Fact Extraction and VERification. NAACL 2018."),
        ("Schlichtkrull, Guo and Vlachos (2023).", "AVeriTeC: A Dataset for Real-world Claim Verification with Evidence from the Web. NeurIPS 36."),
        ("Manakul, Liusie and Gales (2023).", "SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection. EMNLP 2023."),
        ("Min et al. (2023).", "FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation. EMNLP 2023."),
        ("Ji et al. (2023).", "Survey of Hallucination in Natural Language Generation. ACM Computing Surveys 55(12)."),
        ("Lin, Hilton and Evans (2022).", "TruthfulQA: Measuring How Models Mimic Human Falsehoods. ACL 2022."),
        ("Zheng et al. (2023).", "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. NeurIPS 36."),
        ("Ledoit and Wolf (2004).", "A Well-Conditioned Estimator for Large-Dimensional Covariance Matrices. J. Multivariate Analysis 88(2)."),
        ("Wilson (1927).", "Probable Inference, the Law of Succession, and Statistical Inference. JASA 22(158).")]
tb(s, 0.8, 1.45, 11.7, 5.3,
   [{"t": [(a + " ", {"bold": True}), (b, {})], "size": 14, "after": 9} for a, b in refs], name="Reference list")

# ================================================================ 17. thank you
s = prs.slides.add_slide(L_BLANK)
tb(s, 0.45, 2.6, 12.4, 0.9, [{"t": "Thank you for your attention.", "size": 40, "bold": True, "color": GOLD,
                             "align": PP_ALIGN.CENTER}], name="Thank you")
tb(s, 0.45, 3.7, 12.4, 0.5, [{"t": "Questions?", "size": 24, "bold": True, "color": BLUE, "align": PP_ALIGN.CENTER}],
   name="Questions")
tb(s, 0.45, 4.5, 12.4, 0.8,
   [{"t": "piushkole@msds.christuniversity.in   |   thrilok.m@msds.christuniversity.in", "size": 14, "color": MUTED,
     "align": PP_ALIGN.CENTER}], name="Contacts")
add_number(s, L_BLANK)

prs.core_properties.title = "Synthetic Silence 2.0: Research Implementation Review 1"
prs.core_properties.author = "Piush Kole, Thrilok M"
prs.save(str(OUT))
print("wrote", OUT, len(prs.slides), "slides")
