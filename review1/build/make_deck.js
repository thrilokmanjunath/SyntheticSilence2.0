// Builds review1/SyntheticSilence_RI_Review1.pptx
// Numbers come from paper/journal/data.py and docs/VERDICT_EVALUATION.md; do not edit them here by hand.
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const sharp = require("sharp");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const fa = require("react-icons/fa");
const { applyTheme } = require(
  "C:/Users/piush/AppData/Local/Claude-Data/claude_pzs8sxrjxfjjc/local-agent-mode-sessions/skills-plugin/" +
  "982a9f52-e4e9-47aa-b35f-151150a3306e/3143d2dd-1b5e-4d00-bb2a-bbef6ecbe46a/skills/pptx/scripts/apply_theme.js");

const ROOT = path.resolve(__dirname, "..");
const ASSETS = path.join(ROOT, "assets");
const FIGS = path.resolve(ROOT, "..", "paper", "out", "journal_figs");
const OUT = path.join(ROOT, "SyntheticSilence_RI_Review1.pptx");

const THEME = {
  name: "Synthetic Silence",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "0F1B2D", lt1: "FFFFFF", dk2: "1B2B45", lt2: "EEF3F7",
    accent1: "0E8F8A", accent2: "D98E04", accent3: "C0392B", accent4: "5B6B80", accent5: "3C7DD9", accent6: "7A5CB5",
    hlink: "0E8F8A", folHlink: "5B6B80",
  },
};
const HEX = THEME.colors;

// ---------- helpers ----------
async function icon(Comp, hex, px = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + hex, size: px }));
  const buf = await sharp(Buffer.from(svg)).resize(px, px).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}
function blend(fromHex, toHex, t) {
  const f = (h) => [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  const a = f(fromHex), b = f(toHex);
  return a.map((v, i) => Math.round(v + (b[i] - v) * t)).map((v) => v.toString(16).padStart(2, "0")).join("").toUpperCase();
}

async function main() {
  // cropped screenshots of the real extension (stub backend, fixed demo data)
  const shotLight = path.join(ASSETS, "popup-light.png");
  await sharp(shotLight).extract({ left: 0, top: 0, width: 420, height: 660 }).toFile(path.join(ASSETS, "shot_top.png"));
  await sharp(shotLight).extract({ left: 0, top: 530, width: 420, height: 570 }).toFile(path.join(ASSETS, "shot_claim.png"));

  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
  pres.title = "Synthetic Silence 2.0: Research Implementation Review 1";
  pres.author = "Piush Kole, Thrilok M";
  pres.company = "Department of Computer Science, Christ University";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;
  const FORM = "+mj-lt"; // heading font for formulas

  // ---------- layouts ----------
  pres.defineSlideMaster({
    title: "TITLE_DARK",
    background: { color: C.text1 },
    objects: [],
    slideNumber: undefined,
  });
  pres.defineSlideMaster({
    title: "CONTENT",
    background: { color: C.background1 },
    margin: [0.5, 0.6, 0.6, 0.6],
    objects: [
      {
        placeholder: {
          options: { name: "title", type: "title", x: 0.6, y: 0.4, w: 12.1, h: 0.95, fontSize: 30, bold: true, color: C.text1, margin: 0, align: "left", valign: "middle" },
          text: "",
        },
      },
      { text: { text: "Synthetic Silence 2.0  |  Research Implementation Review 1", options: { x: 0.6, y: 7.08, w: 8, h: 0.3, fontSize: 10, color: C.accent4, margin: 0 } } },
    ],
    slideNumber: { x: 12.1, y: 7.08, w: 0.63, h: 0.3, fontSize: 10, color: C.accent4, align: "right", margin: 0 },
  });
  pres.defineSlideMaster({
    title: "CLOSE_DARK",
    background: { color: C.text1 },
    objects: [
      {
        placeholder: {
          options: { name: "title", type: "title", x: 0.6, y: 0.45, w: 12.1, h: 0.95, fontSize: 30, bold: true, color: C.background1, margin: 0, align: "left", valign: "middle" },
          text: "",
        },
      },
    ],
    slideNumber: { x: 12.1, y: 7.08, w: 0.63, h: 0.3, fontSize: 10, color: C.background2, align: "right", margin: 0 },
  });

  const ic = {
    quote: await icon(fa.FaQuoteLeft, "FFFFFF"),
    eye: await icon(fa.FaEyeSlash, "FFFFFF"),
    warn: await icon(fa.FaExclamationTriangle, "FFFFFF"),
    search: await icon(fa.FaSearch, "FFFFFF"),
    check: await icon(fa.FaCheck, "FFFFFF"),
    scale: await icon(fa.FaBalanceScale, "FFFFFF"),
    flask: await icon(fa.FaFlask, "FFFFFF"),
    chrome: await icon(fa.FaChrome, "FFFFFF"),
    shield: await icon(fa.FaShieldAlt, "FFFFFF"),
    chart: await icon(fa.FaChartBar, "FFFFFF"),
    cube: await icon(fa.FaCube, "FFFFFF"),
    dice: await icon(fa.FaDiceFive, "FFFFFF"),
    ruler: await icon(fa.FaRulerCombined, "FFFFFF"),
    wave: await icon(fa.FaWaveSquare, "FFFFFF"),
    table: await icon(fa.FaTable, "FFFFFF"),
    sync: await icon(fa.FaSyncAlt, "FFFFFF"),
    pen: await icon(fa.FaPenFancy, "FFFFFF"),
    globe: await icon(fa.FaGlobe, "FFFFFF"),
    sort: await icon(fa.FaSortAmountDown, "FFFFFF"),
    layer: await icon(fa.FaLayerGroup, "FFFFFF"),
    desktop: await icon(fa.FaDesktop, "FFFFFF"),
  };

  function circleIcon(slide, x, y, d, fillScheme, img, name) {
    slide.addShape(pres.ShapeType.ellipse, { x, y, w: d, h: d, fill: { color: fillScheme }, line: { color: fillScheme, width: 0 }, objectName: name + " circle" });
    const p = d * 0.22;
    slide.addImage({ data: img, x: x + p, y: y + p, w: d - 2 * p, h: d - 2 * p, altText: name, objectName: name + " icon" });
  }
  function card(slide, x, y, w, h, name, fill = C.background2) {
    slide.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: { color: fill, width: 0 }, objectName: name });
  }
  function T(slide, text, o) {
    slide.addText(text, Object.assign({ isTextBox: true, margin: 0, valign: "top", fontSize: 14, color: C.text1 }, o));
  }
  function content(title, section) {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
    s.addText(title, { placeholder: "title" });
    return s;
  }

  // ======================================================================
  // 1. Title
  // ======================================================================
  pres.addSection({ title: "Opening" });
  let s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Opening" });
  T(s, "RESEARCH IMPLEMENTATION REVIEW 1", { x: 0.7, y: 0.8, w: 7.6, h: 0.35, fontSize: 14, bold: true, color: C.accent1, charSpacing: 4 });
  T(s, "Synthetic Silence 2.0", { x: 0.7, y: 1.4, w: 7.8, h: 1.1, fontSize: 54, bold: true, color: C.background1, fontFace: FORM, valign: "middle" });
  T(s, "Auditing language-model answers against sources: deterministic verdict rules, provable properties, and a validation on FEVER",
    { x: 0.7, y: 2.7, w: 7.6, h: 1.5, fontSize: 22, color: C.background2 });
  T(s, [
    { text: "Piush Kole  |  Thrilok M", options: { bold: true, fontSize: 20, color: C.background1, breakLine: true } },
    { text: "Department of Computer Science, Christ University", options: { fontSize: 16, color: C.background2 } },
  ], { x: 0.7, y: 5.2, w: 7.6, h: 1.0 });
  // verdict chip motif
  const chips = [["supported", C.accent1], ["refuted", C.accent3], ["mixed", C.accent2], ["insufficient", C.accent4]];
  chips.forEach(([t, col], i) => {
    s.addShape(pres.ShapeType.roundRect, { x: 0.7 + i * 1.62, y: 4.45, w: 1.5, h: 0.4, rectRadius: 0.2, fill: { color: col }, line: { color: col, width: 0 }, objectName: "chip " + t });
    T(s, t, { x: 0.7 + i * 1.62, y: 4.45, w: 1.5, h: 0.4, fontSize: 14, bold: true, color: C.background1, align: "center", valign: "middle" });
  });
  s.addShape(pres.ShapeType.roundRect, { x: 8.95, y: 0.95, w: 3.78, h: 5.55, rectRadius: 0.12, fill: { color: C.background2 }, line: { color: C.accent1, width: 2 }, objectName: "screenshot frame" });
  s.addImage({ path: path.join(ASSETS, "shot_claim.png"), x: 9.05, y: 1.05, w: 3.58, h: 4.86, altText: "Claim card in the extension showing a verdict meter and sources", objectName: "extension screenshot" });
  T(s, "Real Chrome run, demo data", { x: 9.05, y: 6.0, w: 3.58, h: 0.35, fontSize: 12, color: C.accent4, align: "center" });
  s.addNotes("About 30 seconds. Introduce the team and the one-line idea: we turn an LLM answer into per-claim verdicts, and every true or false verdict points to a quoted sentence in a source. The screenshot is the working Chrome extension. Today: problem, literature, method, statistics, implementation, results, comparison.");

  // ======================================================================
  // 2. Problem
  // ======================================================================
  pres.addSection({ title: "Problem and Background" });
  s = content("People read LLM answers with no way to check them", "Problem and Background");
  const probs = [
    [ic.quote, C.accent1, "Fluent and specific", "Names, dates and figures make an invented fact look like a recalled one."],
    [ic.eye, C.accent2, "No marker", "A reader cannot tell recall from invention. Larger models can repeat common misconceptions more often (Lin et al., 2022)."],
    [ic.warn, C.accent3, "Silence on failure", "A failed search, a missing source and a disagreeing source must not look like the same outcome."],
  ];
  probs.forEach(([img, col, head, body], i) => {
    const x = 0.6 + i * 4.1;
    card(s, x, 1.6, 3.9, 3.1, "problem card " + (i + 1));
    circleIcon(s, x + 0.3, 1.9, 0.75, col, img, head);
    T(s, head, { x: x + 0.3, y: 2.85, w: 3.3, h: 0.45, fontSize: 20, bold: true });
    T(s, body, { x: x + 0.3, y: 3.35, w: 3.3, h: 1.3, fontSize: 15 });
  });
  card(s, 0.6, 5.0, 12.1, 1.6, "problem statement", C.text1);
  T(s, [
    { text: "Problem statement", options: { bold: true, fontSize: 14, color: C.accent1, breakLine: true } },
    { text: "Given an answer written by a language model, return one verdict per claim that a reader can trace to a quoted sentence in a source, and keep \u201Cno evidence\u201D apart from \u201Cthe check failed\u201D.", options: { fontSize: 20, color: C.background1 } },
  ], { x: 0.95, y: 5.2, w: 11.4, h: 1.25, valign: "middle" });
  s.addNotes("About 1 minute. Three points. One: fluent specifics look true. Two: the reader has no marker. Three: when a checker fails silently, silence looks like 'no problem found'. Our problem statement is the dark box: per-claim verdict, traceable to a quote, with failure kept separate from absence.");

  // ======================================================================
  // 3. Objectives
  // ======================================================================
  s = content("Five objectives, each tied to something we can test", "Problem and Background");
  const objs = [
    ["1", "Verdict procedure", "Per-source stances with a verbatim quote; five outcomes."],
    ["2", "Provable properties", "Prove them for the rules and two earlier scores; check against the code."],
    ["3", "Validation on FEVER", "Confusion matrices, Wilson intervals, paired exact tests."],
    ["4", "Explicit failure", "An outage is an error for that claim, never \u201Cno sources\u201D."],
    ["5", "Working tool", "Chrome extension on a FastAPI backend, plus a cross-model audit protocol."],
  ];
  objs.forEach(([n, head, body], i) => {
    const y = 1.6 + i * 1.04;
    s.addShape(pres.ShapeType.ellipse, { x: 0.6, y: y + 0.08, w: 0.7, h: 0.7, fill: { color: C.accent1 }, line: { color: C.accent1, width: 0 }, objectName: "objective number " + n });
    T(s, n, { x: 0.6, y: y + 0.08, w: 0.7, h: 0.7, fontSize: 22, bold: true, color: C.background1, align: "center", valign: "middle" });
    T(s, [
      { text: head, options: { bold: true, fontSize: 18, breakLine: true } },
      { text: body, options: { fontSize: 15, color: C.accent4 } },
    ], { x: 1.55, y: y, w: 6.2, h: 0.9, valign: "middle" });
  });
  card(s, 8.2, 1.6, 4.5, 5.0, "research questions card", C.text1);
  T(s, "Research questions", { x: 8.55, y: 1.85, w: 3.8, h: 0.4, fontSize: 20, bold: true, color: C.accent1 });
  T(s, [
    { text: "RQ1  Does the retrieval source or the aggregation rule matter more for decisive claims?", options: { breakLine: true, paraSpaceAfter: 12 } },
    { text: "RQ2  Can a pooled entailment score abstain when sources do not mention a claim?", options: { breakLine: true, paraSpaceAfter: 12 } },
    { text: "RQ3  Does a density or entropy score track whether evidence supports a claim?", options: {} },
  ], { x: 8.55, y: 2.45, w: 3.8, h: 3.9, fontSize: 18, color: C.background1 });
  s.addNotes("About 1 minute. Five objectives map to the five contributions in the paper. The three research questions on the right are answered later by the FEVER validation and by the propositions: RQ1 and RQ2 empirically, RQ3 by proof plus the earlier study.");

  // ======================================================================
  // 4. Literature survey
  // ======================================================================
  s = content("Literature: no quote-backed audit at reading time", "Problem and Background");
  const H = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: HEX.dk1 }, fontSize: 14 } });
  const rowsLit = [
    ["Guo et al., 2022", "Survey: claim detection, retrieval, verdict, justification", "Pipeline view; no deployed audit"],
    ["Thorne et al., 2018 (FEVER)", "Wikipedia claims labelled SUPPORTS, REFUTES, NEI", "Fixed corpus; claims given, not extracted"],
    ["Schlichtkrull et al., 2023 (AVeriTeC)", "Real-world claims with open-web evidence", "A dataset, not a reader-facing verdict"],
    ["Manakul et al., 2023 (SelfCheckGPT)", "Flags hallucination by sampling consistency, no evidence", "No source sentence to show the reader"],
    ["Min et al., 2023 (FActScore)", "Share of atomic facts a knowledge source supports", "A score, not a quote-backed verdict"],
    ["Ji et al., 2023; Lin et al., 2022", "Hallucination survey; TruthfulQA misconceptions", "Shows the need, not a tool"],
    ["Our earlier study", "Density signal: AUROC 0.546 on FEVER, 0.275 on AVeriTeC", "Does not track support, hence this work"],
  ].map((r, i) => r.map((c, j) => ({ text: c, options: { fontSize: 14, bold: j === 0, fill: { color: i === 6 ? blend("FFFFFF", HEX.accent1, 0.14) : (i % 2 ? "FFFFFF" : HEX.lt2) }, color: C.text1 } })));
  s.addTable([[H("Work"), H("What it does"), H("Gap for a reader-side audit")], ...rowsLit], {
    x: 0.6, y: 1.6, w: 12.1, colW: [3.5, 4.9, 3.7], rowH: 0.62, border: { type: "solid", pt: 0.5, color: "D5DEE8" }, valign: "middle", margin: [0.04, 0.12, 0.04, 0.12], objectName: "literature table",
  });
  s.addNotes("About 1.5 minutes. Walk down the table. The survey gives the pipeline. FEVER and AVeriTeC give labelled data. SelfCheckGPT and FActScore are the closest work on LLM factuality: one uses no evidence, the other returns a score. None returns a verdict with a quote the reader can find. The last row is our own earlier study, which motivates the change of approach on the next slide. LLM-as-judge bias (Zheng et al., 2023) is why we hold the checker fixed.");

  // ======================================================================
  // 5. Gap: earlier density signal
  // ======================================================================
  s = content("Earlier density signal did not generalise", "Problem and Background");
  s.addChart(pres.charts.BAR, [{
    name: "AUROC",
    labels: ["FEVER (E0)", "AVeriTeC, overall", "AVeriTeC, insufficiency", "Matched controls (F2)", "Chance level"],
    values: [0.546, 0.355, 0.275, 0.335, 0.5],
  }], {
    x: 0.6, y: 1.55, w: 6.9, h: 5.3, barDir: "col", barGapWidthPct: 55,
    chartColors: [HEX.accent1, HEX.accent3, HEX.accent3, HEX.accent3, HEX.accent4], invertedColors: [HEX.accent1],
    showTitle: true, title: "AUROC of the density signal for evidence insufficiency", titleFontSize: 14, titleColor: HEX.dk1, titleFontFace: "+mn-lt",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 14, dataLabelColor: HEX.dk1, dataLabelFontFace: "+mn-lt", dataLabelFormatCode: "0.000",
    catAxisLabelColor: HEX.dk1, catAxisLabelFontSize: 12, catAxisLabelFontFace: "+mn-lt",
    valAxisLabelColor: HEX.accent4, valAxisLabelFontSize: 12, valAxisLabelFontFace: "+mn-lt", valAxisMinVal: 0, valAxisMaxVal: 1, valAxisMajorUnit: 0.25,
    valGridLine: { color: "D5DEE8", size: 0.75 }, catGridLine: { style: "none" }, showLegend: false,
  });
  card(s, 7.9, 1.6, 4.8, 1.55, "reading card", C.background2);
  T(s, [
    { text: "Reading the chart", options: { bold: true, fontSize: 16, color: C.accent1, breakLine: true } },
    { text: "Below 0.5 means the signal points the wrong way. Cross-manifold tests fell to chance.", options: { fontSize: 15 } },
  ], { x: 8.15, y: 1.75, w: 4.3, h: 1.3 });
  card(s, 7.9, 3.35, 4.8, 3.25, "approach card", C.text1);
  T(s, [
    { text: "What we do instead", options: { bold: true, fontSize: 16, color: C.accent1, breakLine: true, paraSpaceAfter: 6 } },
    { text: "Read what each source says about the claim", options: { bullet: true, breakLine: true, paraSpaceAfter: 6 } },
    { text: "Require a verbatim quote for every counted source", options: { bullet: true, breakLine: true, paraSpaceAfter: 6 } },
    { text: "Decide with deterministic rules we can prove things about", options: { bullet: true, breakLine: true, paraSpaceAfter: 6 } },
    { text: "Keep density and entropy as research-mode signals only", options: { bullet: true } },
  ], { x: 8.15, y: 3.55, w: 4.3, h: 2.9, fontSize: 15, color: C.background1 });
  s.addNotes("About 1 minute. This is the research gap, from our own earlier work. The density signal had AUROC 0.546 on FEVER, which is weak, then 0.275 on AVeriTeC, which is inverted, and 0.335 even with matched controls. Cross-manifold tests collapsed to chance. So a density score is not a safe basis for telling a reader whether a claim is supported. We keep it in research mode and build the verdict from source stance.");

  // ======================================================================
  // 6. Methodology pipeline
  // ======================================================================
  pres.addSection({ title: "Method" });
  s = content("Method: six steps from answer to traceable verdict", "Method");
  const steps = [
    ["1", "Extract", "LLM splits the answer into self-contained claims", ic.pen],
    ["2", "Retrieve", "Wikipedia and OpenAlex, merged and deduplicated", ic.globe],
    ["3", "Rank", "Cosine similarity to the claim; keep the top 6", ic.sort],
    ["4", "Stance", "Per source: supports, refutes, neutral, irrelevant, plus a quote", ic.quote],
    ["5", "Verdict", "Rules R1 to R5 over counted sources", ic.scale],
    ["6", "Show", "Side panel: sources, quotes, page highlights", ic.desktop],
  ];
  const bw = 1.82, gap = 0.236;
  steps.forEach(([n, head, body, img], i) => {
    const x = 0.6 + i * (bw + gap);
    card(s, x, 1.65, bw, 3.05, "step card " + n);
    circleIcon(s, x + 0.12, 1.8, 0.62, i === 4 ? C.accent2 : C.accent1, img, head);
    T(s, n, { x: x + bw - 0.5, y: 1.85, w: 0.35, h: 0.45, fontSize: 24, bold: true, color: C.accent4, align: "right" });
    T(s, head, { x: x + 0.15, y: 2.6, w: bw - 0.3, h: 0.4, fontSize: 18, bold: true });
    T(s, body, { x: x + 0.15, y: 3.05, w: bw - 0.3, h: 1.6, fontSize: 15 });
    if (i < 5) s.addShape(pres.ShapeType.rightArrow, { x: x + bw + 0.02, y: 3.0, w: gap - 0.04, h: 0.3, fill: { color: C.accent4 }, line: { color: C.accent4, width: 0 }, objectName: "arrow " + n });
  });
  s.addShape(pres.ShapeType.roundRect, { x: 0.6, y: 5.0, w: 5.9, h: 1.65, rectRadius: 0.08, fill: { color: C.background1 }, line: { color: C.accent4, width: 1.5, dashType: "dash" }, objectName: "research mode box" });
  T(s, [
    { text: "Research mode only", options: { bold: true, fontSize: 16, color: C.accent4, breakLine: true } },
    { text: "Density \u03C1 (kNN plus Mahalanobis) and entropy U are computed beside the verdict, marked NOT CALIBRATED, and never decide it.", options: { fontSize: 14 } },
  ], { x: 0.85, y: 5.15, w: 5.4, h: 1.4, valign: "middle" });
  s.addShape(pres.ShapeType.roundRect, { x: 6.8, y: 5.0, w: 5.9, h: 1.65, rectRadius: 0.08, fill: { color: C.accent3 }, line: { color: C.accent3, width: 0 }, objectName: "failure semantics box" });
  T(s, [
    { text: "Failure semantics", options: { bold: true, fontSize: 16, color: C.background1, breakLine: true } },
    { text: "If every retriever fails, or the stream drops, that claim is an error with a retry. It is never shown as \u201Cno sources\u201D.", options: { fontSize: 14, color: C.background1 } },
  ], { x: 7.05, y: 5.15, w: 5.4, h: 1.4, valign: "middle" });
  s.addNotes("About 1.5 minutes. Walk left to right. Extraction keeps names, numbers and dates as written. Two retrievers run together. Ranking uses sentence-embedding cosine similarity and keeps six. The stance call returns one stance, a confidence and a quote per source; a stance without a verbatim quote is downgraded to neutral. Then five deterministic rules. The dashed box is the earlier research signal, shown only in research mode. The red box is the failure rule: outage is an error, not silence.");

  // ======================================================================
  // 7. Verdict rules
  // ======================================================================
  s = content("Verdict rules: five outcomes, decided by counted sources", "Method");
  card(s, 0.6, 1.6, 6.7, 1.55, "definitions card");
  T(s, [
    { text: "P: sources that support, confidence \u2265 0.5, quote verified in the source", options: { breakLine: true, fontFace: FORM } },
    { text: "N: sources that refute, same tests", options: { breakLine: true, fontFace: FORM } },
    { text: "Q(T): |T| \u2265 2, or |T| = 1 with confidence \u2265 0.8", options: { fontFace: FORM, bold: true } },
  ], { x: 0.85, y: 1.7, w: 6.3, h: 1.35, fontSize: 15, valign: "middle", paraSpaceAfter: 4 });
  const vChip = (t, col) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: col }, align: "center", fontSize: 14 } });
  const cell = (t, o = {}) => ({ text: t, options: Object.assign({ fontSize: 14, fill: { color: "FFFFFF" } }, o) });
  s.addTable([
    [H("Rule"), H("Condition (first that applies)"), H("Verdict")],
    [cell("R1", { bold: true }), cell("no sources retrieved (n = 0)"), vChip("no sources", HEX.accent4)],
    [cell("R2", { bold: true }), cell("P and N both non-empty, and Q(P) or Q(N)"), vChip("mixed", HEX.accent2)],
    [cell("R3", { bold: true }), cell("Q(P)"), vChip("supported", HEX.accent1)],
    [cell("R4", { bold: true }), cell("Q(N)"), vChip("refuted", HEX.accent3)],
    [cell("R5", { bold: true }), cell("otherwise"), vChip("insufficient", HEX.accent4)],
  ], { x: 0.6, y: 3.4, w: 6.7, colW: [0.8, 3.9, 2.0], rowH: 0.52, border: { type: "solid", pt: 0.5, color: "D5DEE8" }, valign: "middle", margin: [0.04, 0.1, 0.04, 0.1], objectName: "rules table" });
  s.addImage({ path: path.join(FIGS, "regions.png"), x: 7.65, y: 1.6, w: 5.05, h: 3.32, altText: "Verdict regions by number of counted supporting sources and strongest confidence", objectName: "verdict regions figure" });
  T(s, "Verdict by number of counted supporting sources and strongest confidence, no counted refutation. One source qualifies only at confidence 0.8 or more.", { x: 7.65, y: 5.0, w: 5.05, h: 0.75, fontSize: 12, color: C.accent4 });
  card(s, 7.65, 5.85, 5.05, 0.8, "why callout", C.text1);
  T(s, "Why: one weak source cannot say \u201Cbacked up\u201D", { x: 7.85, y: 5.85, w: 4.7, h: 0.8, fontSize: 16, bold: true, color: C.background1, valign: "middle" });
  s.addNotes("About 1 minute. Counted sets P and N need confidence at least 0.5 and a verified quote. Q says when a side qualifies: two counted sources, or one with confidence 0.8. The five rules are tried in order. The figure shows the regions. The practical point: a single weak source can never produce 'supported'.");

  // ======================================================================
  // 8. Statistical / data science concepts
  // ======================================================================
  pres.addSection({ title: "Statistics and Theory" });
  s = content("Statistical and data-science concepts applied", "Statistics and Theory");
  const stats = [
    [ic.ruler, C.accent1, "Cosine similarity", "Ranks sources by closeness to the claim; keeps the top 6."],
    [ic.cube, C.accent5, "kNN + Mahalanobis", "Distance of a claim from 10,000 FEVER claim embeddings (research mode)."],
    [ic.layer, C.accent6, "Ledoit\u2013Wolf shrinkage", "Stabilises the covariance; condition number \u2264 1 + (1\u2212\u03B4)p/\u03B4."],
    [ic.wave, C.accent2, "Softmax entropy U", "Evenness of source matches (\u03C4\u00A0=\u00A00.1); high when many match alike."],
    [ic.table, C.accent1, "Confusion, macro-F1", "Per-class precision and recall; abstention shown as NEI recall."],
    [ic.shield, C.accent5, "Wilson 95% interval", "Honest error bars for proportions at n\u00A0=\u00A0100 (about \u00B110\u00A0points)."],
    [ic.dice, C.accent6, "Exact McNemar test", "Paired test on discordant claims; every variant sees the same 100 claims."],
    [ic.sync, C.accent2, "Paired bootstrap", "4,000 resamples for each difference; Bonferroni across six tests."],
  ];
  stats.forEach(([img, col, head, body], i) => {
    const x = 0.6 + (i % 4) * 3.07, y = 1.6 + Math.floor(i / 4) * 2.7;
    card(s, x, y, 2.95, 2.5, "stat card " + (i + 1));
    circleIcon(s, x + 0.2, y + 0.2, 0.6, col, img, head);
    T(s, head, { x: x + 0.2, y: y + 0.92, w: 2.55, h: 0.55, fontSize: 16, bold: true });
    T(s, body, { x: x + 0.2, y: y + 1.45, w: 2.55, h: 1.0, fontSize: 14 });
  });
  s.addNotes("About 1 minute. Eight tools, two groups. First four are the modelling side: cosine ranking, kNN plus Mahalanobis density with Ledoit-Wolf shrinkage, and softmax entropy. The last four are the evaluation side: confusion matrix with macro-F1, Wilson intervals, exact McNemar test on paired claims, and a paired bootstrap, with a Bonferroni threshold of 0.0083 because we ran six comparisons.");

  // ======================================================================
  // 9. Provable properties
  // ======================================================================
  s = content("Five properties, proved and then checked against the code", "Statistics and Theory");
  const props = [
    ["Theorem 1", "Verdict rules", "Exhaustive, exclusive, order-invariant, symmetric, monotone. Every true, false or mixed verdict has a verified quote."],
    ["Prop. 2", "Entropy U", "Non-decreasing in \u03C4, and U \u2265 1 \u2212 \u03B4/(\u03C4 ln N): many sources matching alike give high U, agree or not."],
    ["Prop. 3", "Single-query density", "With one query, \u03C1 \u2248 (kNN distance + 1)/2, so the Mahalanobis term cannot change an AUROC."],
    ["Prop. 4", "Shrinkage", "Shrunk covariance is positive definite, with condition number \u2264 1 + (1\u2212\u03B4)p/\u03B4."],
    ["Prop. 5", "Wilson interval", "The Wilson limits form one interval inside [0, 1] that contains the estimate."],
  ];
  props.forEach(([tag, head, body], i) => {
    const y = 1.6 + i * 1.04;
    card(s, 0.6, y, 8.2, 0.92, "property card " + (i + 1));
    s.addShape(pres.ShapeType.roundRect, { x: 0.75, y: y + 0.2, w: 1.15, h: 0.52, rectRadius: 0.1, fill: { color: C.accent1 }, line: { color: C.accent1, width: 0 }, objectName: "tag " + tag });
    T(s, tag, { x: 0.75, y: y + 0.2, w: 1.15, h: 0.52, fontSize: 14, bold: true, color: C.background1, align: "center", valign: "middle" });
    T(s, [
      { text: head + "  ", options: { bold: true, fontSize: 15 } },
      { text: body, options: { fontSize: 14 } },
    ], { x: 2.1, y: y + 0.06, w: 6.55, h: 0.8, valign: "middle" });
  });
  const big = [["27,930", "source configurations tested exhaustively for Theorem 1"], ["15,000", "random configurations of 4 to 7 sources"], ["34", "paper tests pass; no counterexample found"]];
  big.forEach(([num, label], i) => {
    const y = 1.6 + i * 1.75;
    card(s, 9.1, y, 3.6, 1.6, "check stat " + (i + 1), C.text1);
    T(s, num, { x: 9.3, y: y + 0.12, w: 3.2, h: 0.75, fontSize: 40, bold: true, color: C.accent1, fontFace: FORM, valign: "middle" });
    T(s, label, { x: 9.3, y: y + 0.9, w: 3.2, h: 0.65, fontSize: 14, color: C.background1 });
  });
  s.addNotes("About 1 minute. Each property is proved in the paper. Theorem 1 is the audit property: the system cannot assert true, false or disputed without a quote in a source. Props 2 to 4 explain why the earlier scores behave as they do: entropy rewards redundancy, and the single-query density collapses to a nearest-neighbour distance. We also test every statement against the deployed code, so the proofs and the code cannot drift apart. These checks are not proofs; they are drift alarms.");

  // ======================================================================
  // 10. Implementation
  // ======================================================================
  pres.addSection({ title: "Implementation and Results" });
  s = content("Working Chrome extension on a FastAPI backend", "Implementation and Results");
  s.addImage({ path: path.join(ASSETS, "shot_top.png"), x: 0.6, y: 1.6, w: 3.28, h: 5.15, altText: "Extension side panel with input box and verdict summary", objectName: "extension screenshot top" });
  T(s, "Real Chrome 155 run with a stub backend (fixed demo data)", { x: 0.6, y: 6.78, w: 3.4, h: 0.25, fontSize: 10, color: C.accent4 });
  const colX = [4.3, 8.55], colTitle = ["Extension", "Backend"];
  const colItems = [
    ["Popup and side panel", "Right-click or Alt+Shift+S on any text", "Claims stream in as each one finishes", "Highlight claims on the page, no DOM changes", "History, Markdown and JSON export"],
    ["FastAPI, NDJSON streaming", "Wikipedia and OpenAlex retrieval", "gpt-4o-mini at temperature 0, JSON repair and retry", "Result cache; typed API from OpenAPI", "Budget errors reported, not hidden"],
  ];
  colX.forEach((x, k) => {
    card(s, x, 1.6, 4.05, 3.35, colTitle[k] + " card");
    T(s, colTitle[k], { x: x + 0.25, y: 1.75, w: 3.5, h: 0.4, fontSize: 18, bold: true, color: C.accent1 });
    T(s, colItems[k].map((t, i, a) => ({ text: t, options: { bullet: true, breakLine: i < a.length - 1, paraSpaceAfter: 5 } })), { x: x + 0.25, y: 2.25, w: 3.6, h: 2.6, fontSize: 15 });
  });
  const tests = [["117", "backend tests pass"], ["44", "extension unit tests pass"], ["35", "real-Chrome end-to-end checks pass"]];
  tests.forEach(([num, label], i) => {
    const x = 4.3 + i * 2.8;
    card(s, x, 5.2, 2.65, 1.5, "test stat " + (i + 1), C.text1);
    T(s, num, { x: x + 0.15, y: 5.28, w: 2.35, h: 0.7, fontSize: 38, bold: true, color: C.accent1, fontFace: FORM, valign: "middle", align: "center" });
    T(s, label, { x: x + 0.15, y: 6.0, w: 2.35, h: 0.6, fontSize: 13, color: C.background1, align: "center" });
  });
  s.addNotes("About 1.5 minutes. Show the extension live if the review allows: paste text, press Ctrl+Enter, watch claims stream in. Left: real screenshot from our end-to-end run in real Chrome, with a stub backend so the output is deterministic. The demo claims show all three states: backed up, could not be checked because the search budget was used up, and no sources found. The last two are different states on purpose. Tests: backend 117, extension unit 44, and the real-Chrome end-to-end run. Live verdicts with the real model need OpenRouter credit.");

  // ======================================================================
  // 11. Experimental setup + confusion matrices
  // ======================================================================
  s = content("Confusion matrices on 100 balanced FEVER claims", "Implementation and Results");
  const setup = [["100", "claims scored"], ["33 / 36 / 31", "SUPPORTS / REFUTES / NEI"], ["3", "variants, same claims"], ["seed 42", "gpt-4o-mini, temp 0"]];
  setup.forEach(([num, label], i) => {
    const x = 0.6 + i * 3.07;
    card(s, x, 1.55, 2.95, 1.05, "setup chip " + (i + 1));
    T(s, num, { x: x + 0.15, y: 1.6, w: 2.65, h: 0.55, fontSize: 24, bold: true, color: C.accent1, fontFace: FORM, align: "center", valign: "middle" });
    T(s, label, { x: x + 0.15, y: 2.15, w: 2.65, h: 0.4, fontSize: 13, align: "center" });
  });
  const CONF = {
    "Pooled + OpenAlex (baseline)": [[15, 9, 9, 0], [3, 31, 2, 0], [2, 24, 5, 0]],
    "Pooled + Wikipedia": [[24, 8, 1, 0], [4, 31, 1, 0], [6, 25, 0, 0]],
    "Stance + Wikipedia (first prompt)": [[22, 2, 8, 1], [13, 12, 10, 1], [9, 3, 19, 0]],
  };
  const gold = ["SUPPORTS", "REFUTES", "NEI"], pred = ["S", "R", "N", "M"];
  Object.entries(CONF).forEach(([name, m], k) => {
    const x = 0.6 + k * 4.1;
    T(s, name, { x, y: 2.85, w: 3.9, h: 0.4, fontSize: 16, bold: true });
    const hdr = [{ text: "gold \\ pred", options: { fontSize: 12, bold: true, color: C.background1, fill: { color: HEX.dk1 }, align: "center" } }, ...pred.map((p) => ({ text: p, options: { fontSize: 14, bold: true, color: C.background1, fill: { color: HEX.dk1 }, align: "center" } }))];
    const body = m.map((row, i) => {
      const sum = row.reduce((a, b) => a + b, 0);
      return [{ text: gold[i], options: { fontSize: 13, bold: true, fill: { color: HEX.lt2 }, color: C.text1 } }, ...row.map((v, j) => {
        const share = v / sum;
        const diag = j === i;
        const fill = blend("FFFFFF", diag ? HEX.accent1 : HEX.accent3, Math.min(1, share * 1.15));
        return { text: String(v), options: { fontSize: 18, bold: true, align: "center", fill: { color: fill }, color: share * 1.15 > 0.55 ? C.background1 : C.text1 } };
      })];
    });
    s.addTable([hdr, ...body], { x, y: 3.3, w: 3.9, colW: [1.3, 0.65, 0.65, 0.65, 0.65], rowH: 0.72, border: { type: "solid", pt: 0.75, color: "FFFFFF" }, valign: "middle", margin: [0.02, 0.06, 0.02, 0.06], objectName: "confusion matrix " + (k + 1) });
  });
  T(s, "Teal: correct cells. Red: wrong cells. Shade is the share of the gold row. S, R, N, M = SUPPORTS, REFUTES, NEI, MIXED. Rows sum to 33, 36, 31.", { x: 0.6, y: 6.5, w: 12.1, h: 0.45, fontSize: 12, color: C.accent4 });
  s.addNotes("About 1 minute. Same 100 claims for every variant; they come from the FEVER development split, balanced, seed 42. The baseline OpenAlex run scored 100 of 150 sampled claims because the anonymous OpenAlex budget ran out, so all variants are reported on those 100. Read the matrices by row. Pooled with Wikipedia gets the SUPPORTS and REFUTES rows mostly right but puts 25 of 31 NEI claims in REFUTES. The stance variant spreads NEI correctly but loses REFUTES: 13 of 36 called SUPPORTS.");

  // ======================================================================
  // 12. Results
  // ======================================================================
  s = content("Results: retrieval helped, pooled never abstained", "Implementation and Results");
  s.addChart(pres.charts.BAR, [
    { name: "Overall accuracy", labels: ["Pooled + OpenAlex", "Pooled + Wikipedia", "Stance + Wikipedia"], values: [51.0, 55.0, 53.0] },
    { name: "SUPPORTS/REFUTES accuracy", labels: ["Pooled + OpenAlex", "Pooled + Wikipedia", "Stance + Wikipedia"], values: [66.7, 79.7, 49.3] },
  ], {
    x: 0.6, y: 1.55, w: 5.6, h: 4.15, barDir: "col", barGrouping: "clustered", barGapWidthPct: 60,
    chartColors: [HEX.accent4, HEX.accent1],
    showTitle: true, title: "Accuracy (%) on 100 FEVER claims", titleFontSize: 14, titleColor: HEX.dk1, titleFontFace: "+mn-lt",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 13, dataLabelColor: HEX.dk1, dataLabelFontFace: "+mn-lt", dataLabelFormatCode: "0.0",
    catAxisLabelColor: HEX.dk1, catAxisLabelFontSize: 12, catAxisLabelFontFace: "+mn-lt",
    valAxisLabelColor: HEX.accent4, valAxisLabelFontSize: 12, valAxisLabelFontFace: "+mn-lt", valAxisMinVal: 0, valAxisMaxVal: 100, valAxisMajorUnit: 25,
    valGridLine: { color: "D5DEE8", size: 0.75 }, catGridLine: { style: "none" },
    showLegend: true, legendPos: "b", legendFontSize: 12, legendColor: HEX.dk1, legendFontFace: "+mn-lt",
  });
  const rr = (a, b, c, d, e, hl) => [a, b, c, d, e].map((t, j) => ({ text: t, options: { fontSize: 13, bold: j === 0, fill: { color: hl ? blend("FFFFFF", HEX.accent1, 0.14) : "FFFFFF" } } }));
  s.addTable([
    ["Variant", "Accuracy (95% CI)", "Macro-F1", "Decisive (95% CI)", "NEI recall"].map((t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: HEX.dk1 }, fontSize: 13 } })),
    rr("Pooled + OpenAlex", "51.0 (41.3\u201360.6)", "0.466", "66.7 (54.9\u201376.6)", "16.1%"),
    rr("Pooled + Wikipedia", "55.0 (45.2\u201364.4)", "0.445", "79.7 (68.8\u201387.5)", "0.0%", true),
    rr("Stance + Wikipedia", "53.0 (43.3\u201362.5)", "0.528", "49.3 (37.8\u201360.8)", "61.3%"),
  ], { x: 6.5, y: 1.6, w: 6.2, colW: [1.3, 1.55, 0.8, 1.55, 1.0], rowH: 0.78, border: { type: "solid", pt: 0.5, color: "D5DEE8" }, valign: "middle", margin: [0.03, 0.06, 0.03, 0.06], objectName: "results table" });
  T(s, "Percent except macro-F1. Decisive = the 69 SUPPORTS and REFUTES claims.", { x: 6.5, y: 4.8, w: 6.2, h: 0.5, fontSize: 12, color: C.accent4 });
  const callouts = [["66.7 \u2192 79.7%", "decisive accuracy with Wikipedia (suggestive, p = 0.064)", C.accent1], ["0%  vs  61.3%", "NEI recall: pooled score vs stance variant", C.accent2]];
  callouts.forEach(([num, label, col], i) => {
    const x = 0.6 + i * 6.15;
    card(s, x, 5.85, 5.95, 1.05, "callout " + (i + 1), C.text1);
    T(s, num, { x: x + 0.2, y: 5.85, w: 2.6, h: 1.05, fontSize: 26, bold: true, color: col, fontFace: FORM, valign: "middle" });
    T(s, label, { x: x + 2.85, y: 5.85, w: 2.95, h: 1.05, fontSize: 14, color: C.background1, valign: "middle" });
  });
  s.addNotes("About 1.5 minutes. Overall accuracy is flat, between 51 and 55 percent, and the intervals overlap heavily; with 100 claims that is about plus or minus 10 points. The interesting differences are in the decisive claims and in abstention. Wikipedia retrieval lifts decisive accuracy from 66.7 to 79.7, but the paired test gives p = 0.064, so we call it suggestive, and FEVER is built from Wikipedia so a Wikipedia retriever is expected to help. The pooled score never says not enough info; the per-source variant does 61 percent of the time.");

  // ======================================================================
  // 13. Comparative analysis
  // ======================================================================
  pres.addSection({ title: "Analysis" });
  s = content("Comparison: retrieval mattered more than the rule", "Analysis");
  T(s, "Paired tests on the same claims (exact McNemar)", { x: 0.6, y: 1.55, w: 6.4, h: 0.4, fontSize: 16, bold: true });
  const pc = (t, hl, b) => ({ text: t, options: { fontSize: 13, bold: !!b, fill: { color: hl ? blend("FFFFFF", HEX.accent1, 0.14) : "FFFFFF" } } });
  s.addTable([
    ["A vs B", "Claims", "A only / B only", "Diff, points (95% CI)", "p"].map((t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: HEX.dk1 }, fontSize: 13 } })),
    [pc("PW vs PO", 0, 1), pc("decisive 69"), pc("14 / 5"), pc("+13.0 (+1.4, +24.6)"), pc("0.064")],
    [pc("SW vs PW", 1, 1), pc("decisive 69", 1), pc("5 / 26", 1), pc("\u221230.4 (\u221244.9, \u221215.9)", 1), pc("0.0002", 1, 1)],
    [pc("SW vs PO", 0, 1), pc("decisive 69"), pc("11 / 23"), pc("\u221217.4 (\u221233.3, 0.0)"), pc("0.058")],
    [pc("SW vs PW", 0, 1), pc("all 100"), pc("24 / 26"), pc("\u22122.0 (\u221216.0, +12.0)"), pc("0.888")],
  ], { x: 0.6, y: 2.0, w: 6.5, colW: [1.1, 1.05, 1.3, 2.25, 0.8], rowH: 0.55, border: { type: "solid", pt: 0.5, color: "D5DEE8" }, valign: "middle", margin: [0.03, 0.06, 0.03, 0.06], objectName: "paired tests table" });
  T(s, "PO pooled + OpenAlex; PW pooled + Wikipedia; SW stance + Wikipedia. Six tests were run; the Bonferroni threshold is 0.0083, which only the shaded row meets.", { x: 0.6, y: 4.85, w: 6.5, h: 0.75, fontSize: 12, color: C.accent4 });
  card(s, 0.6, 5.7, 6.5, 0.95, "comparison takeaway", C.accent1);
  T(s, "The aggregation rule changed decisive accuracy significantly only for the first stance prompt, and for the worse.", { x: 0.85, y: 5.7, w: 6.0, h: 0.95, fontSize: 15, bold: true, color: C.background1, valign: "middle" });
  T(s, "Design comparison with related audits", { x: 7.4, y: 1.55, w: 5.3, h: 0.4, fontSize: 16, bold: true });
  const dc = (t, o = {}) => ({ text: t, options: Object.assign({ fontSize: 13, fill: { color: "FFFFFF" } }, o) });
  s.addTable([
    ["", "SelfCheckGPT", "FActScore", "This work"].map((t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: HEX.dk1 }, fontSize: 13 } })),
    [dc("External evidence", { bold: true }), dc("No"), dc("Yes"), dc("Yes", { fill: { color: blend("FFFFFF", HEX.accent1, 0.14) } })],
    [dc("Unit checked", { bold: true }), dc("Sentence"), dc("Atomic fact"), dc("Claim", { fill: { color: blend("FFFFFF", HEX.accent1, 0.14) } })],
    [dc("Output", { bold: true }), dc("Consistency score"), dc("Share supported"), dc("Verdict plus quote", { fill: { color: blend("FFFFFF", HEX.accent1, 0.14) }, bold: true })],
  ], { x: 7.4, y: 2.0, w: 5.3, colW: [1.4, 1.3, 1.25, 1.35], rowH: 0.62, border: { type: "solid", pt: 0.5, color: "D5DEE8" }, valign: "middle", margin: [0.03, 0.06, 0.03, 0.06], objectName: "design comparison table" });
  T(s, "Not compared numerically: the methods use different data and tasks. We claim a difference in design, not in accuracy.", { x: 7.4, y: 4.65, w: 5.3, h: 0.7, fontSize: 12, color: C.accent4 });
  card(s, 7.4, 5.4, 5.3, 1.25, "earlier work comparison");
  T(s, [
    { text: "Against our earlier density signal", options: { bold: true, fontSize: 14, color: C.accent1, breakLine: true } },
    { text: "AUROC 0.546 (FEVER) and 0.275 (AVeriTeC) there; here, verdicts that carry quotes.", options: { fontSize: 14 } },
  ], { x: 7.6, y: 5.45, w: 4.9, h: 1.15, valign: "middle" });
  s.addNotes("About 1.5 minutes. Left: the paired comparisons, which are the fair way to compare variants on the same claims. Only one passes the Bonferroni threshold: the first stance prompt is worse than the pooled score on decisive claims. Wikipedia against OpenAlex is suggestive but not significant. Right: a design comparison with the two closest related methods. We do not claim better accuracy than them; we did not run them on the same data. The claim is about design: external evidence, claim-level unit, verdict with a quote.");

  // ======================================================================
  // 14. Findings and diagnosis
  // ======================================================================
  s = content("Analysis: what we found, and what we got wrong", "Analysis");
  const finds = [
    ["+13.0 pts", "Retrieval source", "Wikipedia over OpenAlex on decisive claims. Suggestive (p = 0.064); FEVER is Wikipedia-derived."],
    ["0% recall", "Pooled score cannot abstain", "It called 25 of 31 NEI claims refuted. One score cannot split \u201Cnot mentioned\u201D from \u201Ccontradicted\u201D."],
    ["p = 0.0002", "First stance prompt", "Abstains (61.3% NEI recall) but is much worse on decisive claims than the pooled score."],
  ];
  finds.forEach(([num, head, body], i) => {
    const x = 0.6 + i * 4.1;
    card(s, x, 1.6, 3.9, 2.85, "finding card " + (i + 1));
    T(s, num, { x: x + 0.25, y: 1.7, w: 3.4, h: 0.8, fontSize: 34, bold: true, color: C.accent1, fontFace: FORM, valign: "middle" });
    T(s, head, { x: x + 0.25, y: 2.5, w: 3.4, h: 0.4, fontSize: 17, bold: true });
    T(s, body, { x: x + 0.25, y: 2.95, w: 3.4, h: 1.45, fontSize: 16 });
  });
  card(s, 0.6, 4.7, 12.1, 1.95, "diagnosis card", C.text1);
  T(s, [
    { text: "Failure analysis: 13 of 36 REFUTES claims were called supported", options: { bold: true, fontSize: 17, color: C.accent2, breakLine: true, paraSpaceAfter: 4 } },
    { text: "Cause 1: the stance call judged the normalised claim, which had dropped the detail that made it false.", options: { bullet: true, breakLine: true } },
    { text: "Cause 2: the prompt accepted near misses (1945 for 1946; a TV series for a radio station).", options: { bullet: true, breakLine: true } },
    { text: "Both fixed with a regression test. The corrected variant is not yet shown to beat pooled, so the default stays pooled.", options: { bullet: true, bold: true } },
  ], { x: 0.9, y: 4.8, w: 11.5, h: 1.75, fontSize: 14, color: C.background1, valign: "middle" });
  s.addNotes("About 1 minute. Three findings, one admission. Retrieval source mattered; the pooled score cannot abstain; the first per-source prompt abstains but is worse on decisive claims. We inspected the 13 refuted claims called supported and found two causes that were ours: the stance call saw the normalised claim, and the prompt was too lenient. We fixed both and added a regression test, but a re-run on a fresh sample was cut off when the API account ran out of credit, so we draw no conclusion about the corrected prompt and keep pooled as the default.");

  // ======================================================================
  // 15. Limitations, next steps, conclusion
  // ======================================================================
  pres.addSection({ title: "Closing" });
  s = pres.addSlide({ masterName: "CLOSE_DARK", sectionTitle: "Closing" });
  s.addText("Conclusion, limits and next steps", { placeholder: "title" });
  T(s, "Every verdict traces to a quoted sentence, and absence is kept apart from failure.", { x: 0.6, y: 1.6, w: 12.1, h: 0.9, fontSize: 22, bold: true, color: C.accent1, fontFace: FORM, valign: "middle" });
  const closeCols = [
    ["Limits", C.accent3, ["100 claims: intervals about \u00B110 points", "FEVER is Wikipedia-derived: compare variants, not absolutes", "Corrected stance prompt not yet evaluated", "Cross-model audit specified, not run (API credit)"]],
    ["Next steps", C.accent1, ["Evaluate the corrected prompt on a 150-claim fresh sample", "Run the 40-prompt audit on seven commercial models (about US$1.6)", "Compare verdicts with human judgements", "Fit the conformal calibration interface (not fitted today)"]],
  ];
  closeCols.forEach(([head, col, items], k) => {
    const x = 0.6 + k * 6.15;
    s.addShape(pres.ShapeType.roundRect, { x, y: 2.8, w: 5.95, h: 3.3, rectRadius: 0.08, fill: { color: C.text2 }, line: { color: C.text2, width: 0 }, objectName: head + " card" });
    s.addShape(pres.ShapeType.ellipse, { x: x + 0.3, y: 3.05, w: 0.28, h: 0.28, fill: { color: col }, line: { color: col, width: 0 }, objectName: head + " marker" });
    T(s, head, { x: x + 0.75, y: 2.98, w: 4.5, h: 0.42, fontSize: 20, bold: true, color: C.background1, valign: "middle" });
    T(s, items.map((t, i, a) => ({ text: t, options: { bullet: true, breakLine: i < a.length - 1, paraSpaceAfter: 7 } })), { x: x + 0.3, y: 3.6, w: 5.4, h: 2.4, fontSize: 16, color: C.background1 });
  });
  T(s, "Thank you. Questions?", { x: 0.6, y: 6.3, w: 12.1, h: 0.6, fontSize: 22, bold: true, color: C.background1, valign: "middle" });
  s.addNotes("About 30 seconds. One-sentence conclusion first. Then be direct about the limits: small sample, Wikipedia-derived benchmark, corrected prompt not evaluated, cross-model audit built and tested but not run because of API credit. Next steps are concrete. Invite questions. Likely questions: why FEVER, why not a bigger sample, why keep the density score, how are quotes verified. Answers are in the paper: Sections 4, 5 and 6 and the Limitations section.");

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
}
main().catch((e) => { console.error(e); process.exit(1); });
